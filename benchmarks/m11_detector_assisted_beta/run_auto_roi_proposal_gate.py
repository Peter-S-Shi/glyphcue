"""M11 Research Gate -- Auto-ROI proposal (PROTOTYPE, research-only).

Throwaway research prototype. Nothing here is wired into production, the
UI, or the Hybrid candidate; it only answers one question.

THE QUESTION. 870460d left one residual risk: a hand-drawn ROI that
physically crops an unusually wide or tall caption makes that caption
undetectable for its whole duration. This does not pad or repair the
user's ROI. It asks whether the SOFTWARE can propose a subtitle ROI in
the first place, leaving the user to confirm or nudge it -- moving the
human from "point the way" to "correct the way when needed".

Existing stack only: PyAV, the existing PaddleOCR text detector, NumPy
and the existing fixture/replay infrastructure. No new CV model, no
tracker, no new heavy dependency.

THE RULE, declared before use and fixture-independent. It never sees a
fixture id, the ground-truth ROI, or any known caption timestamp; ground
truth is used only to SCORE a proposal after it exists.

  1. PROBE the processing window on the FULL FRAME at 1 fps -- sparse on
     purpose, since this is a preflight, not a second OCR pass.
  2. Collect the detector's caption LINE boxes, in frame fractions.
  3. Quantize each box by its vertical centre into bands of 1/20 of the
     frame height -- a fixed quantization, not a fitted one.
  4. Keep a band when it is BOTH:
       * persistent -- it contributes a box in at least half the probe
         frames, which incidental scene text does not sustain; and
       * wide -- its median box spans at least 15% of the frame width,
         which a logo or a timestamp does not.
     Two structural properties of subtitles, declared once.
  5. Discard bands in the upper half of the frame. Subtitles sit in the
     lower half; a burned-in header or title does not. One structural
     convention, no fitted number.
  6. The proposal spans the FULL FRAME WIDTH, and vertically the union
     of the surviving bands' boxes grown by 0.25 of their median line
     height -- reusing the frozen PADDING_TO_LINE_HEIGHT magnitude
     rather than inventing a new one.

     Refusing to constrain width is the substantive decision here, and
     it follows from what a sparse preflight can and cannot know. Where
     a caption sits vertically is stable across a whole video; how WIDE
     it is is not -- on sample_d the captions range from 23% to 96% of
     frame width. A probe that samples one frame per second will
     routinely never see the widest caption, so any proposal built from
     the horizontal union of what it happened to sample will crop the
     caption it missed, which is precisely the failure this gate exists
     to prevent. Constraining only the axis the probe can actually
     resolve is the honest form of the rule.

  HOW THE RULE WAS FORMED. Three formulations were tried on sample_d,
  the calibration fixture, before anything was frozen or sample_a and
  sample_b were run at all. (a) Union every surviving band: 98.5% of the
  frame, worthless, because the fixture carries persistent wide text near
  the top. (b) Pick one contiguous band cluster, scored by how much its
  line widths vary, since captions reflow while station graphics are
  geometrically static: this chose a sensible-looking 9.6% box but
  cropped every state, because a two-line caption straddles two
  non-adjacent bands and because the sparse probe had never sampled the
  96%-wide caption. (c) The rule above. Both earlier failures are
  reported rather than hidden; the frozen rule is (c).

SCORING, deliberately two independent things:

  * COVERAGE. For every real state in the frozen ground truth, the true
    spatial envelope of its caption is measured on the FULL frame at
    that state's own midpoint. The proposal must contain every one of
    them. Any real caption cropped is a correctness FAIL -- especially
    sample_b's two-line 81%/76%-width caption, the one a hand-drawn
    tight ROI destroyed.
  * NON-TRIVIALITY. A proposal equal to the whole frame would score
    perfect coverage and be worthless. Area ratio, size and position are
    reported, and a rule that is only reliable at near-full-frame is a
    FAIL on value even with perfect coverage.

VERDICT: FAIL, and the reason is a chicken-and-egg the approach cannot
escape with this stack.

  fixture   proposal                  area    coverage
  sample_d  full width x y[.728,.991] 26.3%   PASS, all 7 states
  sample_a  full width x y[.794,.914] 12.0%   FAIL, crops state 2's top
  sample_b  full width x y[.769,.867]  9.8%   FAIL, crops states 1-2 below

Cost was never the problem: 10 probe frames and 10 detector calls per
fixture, about a minute each, mostly decode. Correctness was.

WHY. To propose an ROI you must detect WITHOUT one -- and that is
exactly when the detector can least see captions. The detector
downscales its input to a fixed side length, so a full 1728-wide frame
is reduced far more than a cropped caption band, and caption text drops
below its effective resolution. Measured directly, same frames, same
detector, caption band only:

    sample_b state 3   full frame 0 lines   ROI crop 2 lines
    sample_b state 5   full frame 0 lines   ROI crop 2 lines
    sample_b state 4   full frame 1 line    ROI crop 2 lines
    sample_a state 6   full frame 1 line    ROI crop 2 lines

The probe systematically recovers only the more prominent line of a
two-line caption, so the vertical band it infers is too short, so the
proposal crops the other line -- which is the same class of harm as the
hand-drawn ROI this was meant to remove. Sampling more frames does not
help: every probe frame is under-resolved in the same way.

So the exit is the one declared in advance: keep the user's coarse ROI
plus the Hybrid candidate, accept the ROI-outside residual risk, and do
not carry auto-ROI further. Anything that would fix it -- probing at
native resolution in tiles, or a second detector pass at higher side
length -- is a materially larger detector bill and a change to the
detector configuration this gate was forbidden to touch.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_auto_roi_proposal_gate [fixture...]
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import numpy as np

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource
from glyphcue.application.detector_assisted_signature import (
    MAX_LINES,
    detected_lines_from_polygons,
)

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import _CORPUS_DIR

# --- the rule's constants, declared once and frozen ------------------
PROBE_FPS = 1.0
BAND_FRACTION = 1.0 / 20.0
MIN_PERSISTENCE_RATIO = 0.5
MIN_WIDTH_FRACTION = 0.15
MARGIN_TO_LINE_HEIGHT = 0.25


def _boxes_in_frame(detector, frame) -> list[tuple[float, float, float, float]]:
    """Detected caption lines on the WHOLE frame, in frame fractions."""
    height, width = frame.shape[:2]
    polygons = [np.asarray(p, dtype=np.float64) for p in (detector(frame) or [])]
    return [
        (box[0] / width, box[1] / height, box[2] / width, box[3] / height)
        for box in detected_lines_from_polygons(polygons)[:MAX_LINES]
    ]


def propose_roi(detector, video, window) -> tuple[dict[str, Any], int, float]:
    """The declared rule. Returns (proposal, probe_frames, seconds)."""
    started = time.monotonic()
    interval = 1.0 / PROBE_FPS
    next_probe = window[0]
    probes = 0
    observed: list[tuple[int, tuple[float, float, float, float]]] = []
    source = PyAvMediaFrameSource()
    source.open(video)
    try:
        for timestamp, frame in source.frames(*window):
            if timestamp < next_probe:
                continue
            next_probe += interval
            for box in _boxes_in_frame(detector, frame):
                observed.append((probes, box))
            probes += 1
    finally:
        source.close()

    bands: dict[int, list[tuple[int, tuple[float, float, float, float]]]] = {}
    for probe_index, box in observed:
        centre = (box[1] + box[3]) / 2.0
        bands.setdefault(int(centre / BAND_FRACTION), []).append((probe_index, box))

    kept = []
    for band, entries in bands.items():
        persistence = len({index for index, _ in entries})
        widths = [b[2] - b[0] for _, b in entries]
        if (
            persistence >= MIN_PERSISTENCE_RATIO * probes
            and float(np.median(widths)) >= MIN_WIDTH_FRACTION
        ):
            kept.append(band)

    chosen = [band for band in sorted(kept) if (band + 0.5) * BAND_FRACTION > 0.5]
    boxes = [box for band in chosen for _, box in bands[band]]
    elapsed = time.monotonic() - started
    if not boxes:
        return ({"found": False}, probes, elapsed)

    margin = MARGIN_TO_LINE_HEIGHT * float(
        np.median([box[3] - box[1] for box in boxes])
    )
    x0, x1 = 0.0, 1.0
    y0 = max(0.0, min(b[1] for b in boxes) - margin)
    y1 = min(1.0, max(b[3] for b in boxes) + margin)
    return (
        {
            "found": True,
            "roi": (x0, y0, x1 - x0, y1 - y0),
            "bands_kept": chosen,
            "all_kept_bands": sorted(kept),
            "bands_seen": len(bands),
            "boxes_used": len(boxes),
        },
        probes,
        elapsed,
    )


def state_envelopes(detector, video, states, caption_band) -> list[tuple | None]:
    """The true spatial envelope of each real caption, measured on the
    FULL frame at that state's own midpoint.

    `caption_band` is the vertical span of the fixture's ground-truth
    ROI, used ONLY to say which of the frame's text is the caption --
    these videos also carry persistent header text, and unioning that in
    would make every envelope the whole frame. Horizontal extent is left
    completely free, so a caption WIDER than the ground-truth ROI is
    still measured at its true width. This is scoring, applied after the
    proposal exists; the rule never sees it.
    """
    envelopes: list[tuple | None] = []
    source = PyAvMediaFrameSource()
    source.open(video)
    try:
        for low, high in states:
            midpoint = (low + high) / 2.0
            found = None
            for _timestamp, frame in source.frames(midpoint, midpoint + 0.25):
                boxes = [
                    box
                    for box in _boxes_in_frame(detector, frame)
                    if caption_band[0] <= (box[1] + box[3]) / 2.0 <= caption_band[1]
                ]
                if boxes:
                    found = (
                        min(b[0] for b in boxes),
                        min(b[1] for b in boxes),
                        max(b[2] for b in boxes),
                        max(b[3] for b in boxes),
                    )
                break
            envelopes.append(found)
    finally:
        source.close()
    return envelopes


def _contains(roi, envelope, tolerance=1e-6) -> bool:
    x, y, width, height = roi
    return (
        envelope[0] >= x - tolerance
        and envelope[1] >= y - tolerance
        and envelope[2] <= x + width + tolerance
        and envelope[3] <= y + height + tolerance
    )


def _fixtures():
    sample_d = _CORPUS_DIR / "sample_d_alpha_window_ground_truth.json"
    generalization = _CORPUS_DIR / "generalization_gate_ground_truth.json"
    if not sample_d.exists() or not generalization.exists():
        return None
    data = json.loads(sample_d.read_text(encoding="utf-8"))
    out = [
        {
            "name": "sample_d",
            "video": _CORPUS_DIR / data["video_path"],
            "window": (data["window_start_seconds"], data["window_end_seconds"]),
            "states": [(s["start_seconds"], s["end_seconds"]) for s in data["states"]],
            "hand_drawn_roi": tuple(data["roi"]),
        }
    ]
    for fixture in json.loads(generalization.read_text(encoding="utf-8"))["fixtures"]:
        out.append(
            {
                "name": "sample_a" if "sample_a" in fixture["id"] else "sample_b",
                "video": _CORPUS_DIR / fixture["video_path"],
                "window": (
                    fixture["window_start_seconds"],
                    fixture["window_end_seconds"],
                ),
                "states": [
                    (s["start_seconds"], s["end_seconds"]) for s in fixture["states"]
                ],
                "hand_drawn_roi": tuple(fixture["roi"]),
            }
        )
    return out


def run(wanted: list[str] | None = None) -> dict[str, Any] | None:
    fixtures = _fixtures()
    if fixtures is None or not all(f["video"].exists() for f in fixtures):
        print(
            "M11 auto-ROI proposal gate skipped: private corpus / ground-truth "
            "files not present on this machine. Safe to run without them."
        )
        return None
    if wanted:
        fixtures = [f for f in fixtures if f["name"] in wanted]

    detector = PaddleTextDetector()
    detector.initialize()
    results: dict[str, Any] = {}
    try:
        for fixture in fixtures:
            proposal, probes, elapsed = propose_roi(
                detector, fixture["video"], fixture["window"]
            )
            print(f"\n=== {fixture['name']} ===")
            if not proposal["found"]:
                print("  no band survived the rule -> NO PROPOSAL")
                results[fixture["name"]] = {"coverage": False, "reason": "no proposal"}
                continue
            x, y, width, height = proposal["roi"]
            area = width * height
            hand = fixture["hand_drawn_roi"]
            print(
                f"  proposed   x={x:.4f} y={y:.4f} w={width:.4f} h={height:.4f}"
                f"   area={area * 100:5.1f}% of frame"
            )
            print(
                f"  hand-drawn x={hand[0]:.4f} y={hand[1]:.4f} "
                f"w={hand[2]:.4f} h={hand[3]:.4f}   area={hand[2] * hand[3] * 100:5.1f}%"
            )
            print(
                f"  lower-half bands {proposal['bands_kept']} of kept "
                f"{proposal['all_kept_bands']}; "
                f"{proposal['boxes_used']} boxes from {probes} probe frames; {elapsed:.0f}s"
            )
            envelopes = state_envelopes(
                detector,
                fixture["video"],
                fixture["states"],
                (hand[1], hand[1] + hand[3]),
            )
            cropped = []
            for index, envelope in enumerate(envelopes):
                if envelope is None:
                    print(f"    state {index + 1}: no full-frame detection at midpoint")
                    continue
                ok = _contains(proposal["roi"], envelope)
                if not ok:
                    cropped.append(index + 1)
                print(
                    f"    state {index + 1}: envelope "
                    f"x[{envelope[0]:.3f},{envelope[2]:.3f}] "
                    f"y[{envelope[1]:.3f},{envelope[3]:.3f}] "
                    f"w={(envelope[2] - envelope[0]) * 100:3.0f}%"
                    f"{'' if ok else '   <== CROPPED'}"
                )
            verdict = "COVERAGE PASS" if not cropped else f"COVERAGE FAIL {cropped}"
            print(f"  {verdict};  area {area * 100:.1f}% of frame")
            results[fixture["name"]] = {
                "coverage": not cropped,
                "area_ratio": area,
                "roi": proposal["roi"],
                "probe_frames": probes,
                "seconds": elapsed,
            }
    finally:
        detector.shutdown()
    return results


if __name__ == "__main__":
    run(sys.argv[1:] or None)
