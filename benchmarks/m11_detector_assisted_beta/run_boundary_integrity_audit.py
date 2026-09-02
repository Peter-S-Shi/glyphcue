"""M11 Research Gate -- ground-truth boundary integrity audit.

Re-verifies EVERY subtitle state boundary in a fixture against dense
frame evidence, and rewrites the private ground truth from what the
frames actually show.

WHY THIS EXISTS. Auditing one disputed boundary in sample_d found the
annotation about 0.43s late, and correcting it removed 92% of the
hard-bound overlap in the occupancy calibration. That is enough to
suspect the rest of the corpus rather than the metric. But auditing only
the boundaries that happen to produce inconvenient calibration pairs
would be fitting the ground truth to the result, so this audits ALL of
them, once, in one pass, by one rule.

INDEPENDENCE. Nothing here reads, computes, or is influenced by any
candidate operating threshold, and no boundary is judged by whether
moving it would help a calibration. Every decision comes from evidence
that exists before any threshold does:

  * detector box geometry -- where the caption lines are, in frame
    coordinates, straight from the detector;
  * Beta-S content -- what ink is inside those boxes.

and it is used only as a NEAREST-REFERENCE comparison, which is
threshold-free and scale-free: each frame is assigned to whichever
neighbouring caption it resembles more, and a frame must agree on BOTH
kinds of evidence to be assigned at all.

THE PROCEDURE, declared before running and applied identically to every
boundary of every fixture:

  1. References are the frames at the temporal MIDPOINT of each of the
     two annotated states -- chosen by the annotation alone, deep inside
     each state, never by inspection.
  2. The sweep spans from the earlier state's midpoint to the later
     state's midpoint, clipped to at most 1.5s either side of the
     annotated boundary region so the cost stays bounded.
  3. Each swept frame is assigned EARLIER, LATER, or ambiguous.
     Ambiguous covers both a genuine crossfade and a blank gap, since a
     frame with no detected line resembles neither caption.
  4. offset = the last timestamp such that every frame up to it is
     EARLIER; onset = the first timestamp such that every frame from it
     onward is LATER. Requiring whole prefixes and suffixes rather than
     single frames makes one flickering frame unable to move a boundary.
  5. The earlier state ends at offset, the later state starts at onset,
     and the transition window between them is exactly [offset, onset].

A boundary is reported as CONFIRMED when the evidence reproduces the
existing annotation within one frame interval, and CORRECTED otherwise.
Either way the rationale is written into the ground truth's `revisions`
log, and the ground truth is frozen afterwards.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_boundary_integrity_audit
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource
from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.detector_assisted_signature import (
    MAX_LINES,
    detected_lines_from_polygons,
)
from glyphcue.application.occupancy_normalized_distance import (
    occupancy_normalized_distance,
)
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import _CORPUS_DIR

_MAX_SWEEP_MARGIN_SECONDS = 1.5
_FRAME_INTERVAL_SECONDS = 1.0 / 30.0


def _geometry(frame: np.ndarray, polygons) -> list[tuple[float, float, float, float]]:
    height, width = frame.shape[:2]
    return [
        (box[0] / width, box[1] / height, box[2] / width, box[3] / height)
        for box in detected_lines_from_polygons(polygons)[:MAX_LINES]
    ]


def _geometry_distance(a, b) -> float:
    if len(a) != len(b):
        return 1.0
    if not a:
        return 1.0  # two line-less frames resemble no caption, not each other
    return float(np.mean([abs(x - y) for pa, pb in zip(a, b) for x, y in zip(pa, pb)]))


def _sweep(detector, path: Path, roi: ROI, start: float, end: float) -> dict[float, dict]:
    observations: dict[float, dict] = {}
    source = PyAvMediaFrameSource()
    source.open(path)
    try:
        for timestamp, frame in source.frames(start, end):
            roi_frame = crop_to_roi(frame, roi)
            polygons = [np.asarray(p, dtype=np.float64) for p in (detector(roi_frame) or [])]
            observations[round(timestamp, 4)] = {
                "geometry": _geometry(roi_frame, polygons),
                "signature": beta_s_signature(roi_frame, polygons),
                "lines": len(detected_lines_from_polygons(polygons)[:MAX_LINES]),
            }
    finally:
        source.close()
    return observations


def _assign(record, earlier, later) -> str:
    geometry_earlier = _geometry_distance(record["geometry"], earlier["geometry"])
    geometry_later = _geometry_distance(record["geometry"], later["geometry"])
    content_earlier = occupancy_normalized_distance(record["signature"], earlier["signature"])
    content_later = occupancy_normalized_distance(record["signature"], later["signature"])
    if record["lines"] == 0:
        return "ambiguous"
    if geometry_earlier < geometry_later and content_earlier < content_later:
        return "EARLIER"
    if geometry_later < geometry_earlier and content_later < content_earlier:
        return "LATER"
    return "ambiguous"


def _audit_boundary(detector, path, roi, earlier_state, later_state) -> dict[str, Any] | None:
    earlier_mid = (earlier_state["start_seconds"] + earlier_state["end_seconds"]) / 2
    later_mid = (later_state["start_seconds"] + later_state["end_seconds"]) / 2
    start = max(earlier_mid, earlier_state["end_seconds"] - _MAX_SWEEP_MARGIN_SECONDS)
    end = min(later_mid, later_state["start_seconds"] + _MAX_SWEEP_MARGIN_SECONDS)

    frames = _sweep(detector, path, roi, min(start, earlier_mid), max(end, later_mid))
    if not frames:
        return None
    times = sorted(frames)

    def nearest(target: float) -> float:
        return min(times, key=lambda t: abs(t - target))

    earlier = frames[nearest(earlier_mid)]
    later = frames[nearest(later_mid)]
    swept = [t for t in times if start <= t <= end]
    if not swept:
        return None
    verdicts = {t: _assign(frames[t], earlier, later) for t in swept}

    offset = None
    for timestamp in swept:
        if verdicts[timestamp] == "EARLIER":
            offset = timestamp
        else:
            break
    onset = None
    for timestamp in reversed(swept):
        if verdicts[timestamp] == "LATER":
            onset = timestamp
        else:
            break
    if offset is None or onset is None or offset >= onset:
        return {
            "resolved": False,
            "swept": [swept[0], swept[-1]],
            "verdicts": "".join(
                {"EARLIER": "E", "LATER": "L", "ambiguous": "."}[verdicts[t]] for t in swept
            ),
        }
    return {
        "resolved": True,
        "offset": round(offset, 3),
        "onset": round(onset, 3),
        "swept": [swept[0], swept[-1]],
        "verdicts": "".join(
            {"EARLIER": "E", "LATER": "L", "ambiguous": "."}[verdicts[t]] for t in swept
        ),
    }


def audit_fixture(detector, path: Path, roi: ROI, data: dict, label: str) -> list[dict]:
    states = sorted(data["states"], key=lambda s: s["start_seconds"])
    results = []
    print(f"\n=== {label} ===")
    print(f"{'boundary':12s}{'annotated':>22s}{'evidence':>22s}  verdict")
    for earlier_state, later_state in zip(states, states[1:]):
        outcome = _audit_boundary(detector, path, roi, earlier_state, later_state)
        name = f"{earlier_state['index']}->{later_state['index']}"
        annotated = (earlier_state["end_seconds"], later_state["start_seconds"])
        if outcome is None or not outcome["resolved"]:
            print(
                f"{name:12s}{f'{annotated[0]:.3f}-{annotated[1]:.3f}':>22s}"
                f"{'unresolved':>22s}  LEFT AS ANNOTATED"
            )
            results.append({"boundary": name, "resolved": False, "annotated": annotated})
            continue
        offset, onset = outcome["offset"], outcome["onset"]
        moved = max(abs(offset - annotated[0]), abs(onset - annotated[1]))
        verdict = "CONFIRMED" if moved <= _FRAME_INTERVAL_SECONDS else "CORRECTED"
        print(
            f"{name:12s}{f'{annotated[0]:.3f}-{annotated[1]:.3f}':>22s}"
            f"{f'{offset:.3f}-{onset:.3f}':>22s}  {verdict} (moved {moved:.3f}s)"
        )
        results.append(
            {
                "boundary": name,
                "resolved": True,
                "annotated": annotated,
                "offset": offset,
                "onset": onset,
                "verdict": verdict,
                "moved_seconds": round(moved, 3),
                "frame_verdicts": outcome["verdicts"],
                "swept": outcome["swept"],
            }
        )
    return results


def apply_revisions(fixture: dict, results: list[dict]) -> None:
    """Rewrites one fixture's boundaries in place and logs the rationale.

    `fixture` is whichever dict actually holds `states` -- the whole
    document for sample_d, one entry of `fixtures` for the shared
    generalization file.
    """
    states = {s["index"]: s for s in fixture["states"]}
    transitions = {tuple(t["between_states"]): t for t in fixture.get("transitions", [])}
    corrections = []
    for result in results:
        if not result["resolved"] or result["verdict"] != "CORRECTED":
            continue
        first, second = (int(part) for part in result["boundary"].split("->"))
        before = {
            f"state_{first}_end_seconds": states[first]["end_seconds"],
            f"state_{second}_start_seconds": states[second]["start_seconds"],
        }
        states[first]["end_seconds"] = result["offset"]
        states[second]["start_seconds"] = result["onset"]
        transition = transitions.get((first, second))
        if transition is not None:
            before["transition_window"] = list(transition["window"])
            transition["window"] = [result["offset"], result["onset"]]
        corrections.append(
            {
                "boundary": result["boundary"],
                "before": before,
                "after": {
                    f"state_{first}_end_seconds": result["offset"],
                    f"state_{second}_start_seconds": result["onset"],
                    "transition_window": [result["offset"], result["onset"]],
                },
                "moved_seconds": result["moved_seconds"],
                "frame_verdicts": result["frame_verdicts"],
            }
        )

    fixture.setdefault("revisions", []).append(
        {
            "audit": "M11 ground-truth boundary integrity audit",
            "procedure": (
                "Every boundary swept frame by frame between the two annotated "
                "states' midpoints (clipped to 1.5s either side of the boundary). "
                "Each frame assigned to whichever neighbouring caption it resembles "
                "more, requiring agreement between detector box geometry and Beta-S "
                "content; frames with no detected line count as ambiguous. The "
                "earlier state ends at the last all-EARLIER prefix and the later "
                "state starts at the first all-LATER suffix, so a single flickering "
                "frame cannot move a boundary. No operating threshold was read, "
                "computed or consulted, and no boundary was judged by whether "
                "moving it would help a calibration."
            ),
            "confirmed": [
                r["boundary"] for r in results if r["resolved"] and r["verdict"] == "CONFIRMED"
            ],
            "unresolved_left_as_annotated": [
                r["boundary"] for r in results if not r["resolved"]
            ],
            "corrections": corrections,
            "frozen": True,
        }
    )


def _fixtures():
    """Yields (label, path, document, fixture) -- `document` is what gets
    written back, `fixture` is where that fixture's states live."""
    sample_d = _CORPUS_DIR / "sample_d_alpha_window_ground_truth.json"
    if sample_d.exists():
        document = json.loads(sample_d.read_text(encoding="utf-8"))
        yield "sample_d", sample_d, document, document
    generalization = _CORPUS_DIR / "generalization_gate_ground_truth.json"
    if generalization.exists():
        document = json.loads(generalization.read_text(encoding="utf-8"))
        for fixture in document["fixtures"]:
            yield fixture["id"], generalization, document, fixture


def run() -> None:
    if not (_CORPUS_DIR / "sample_d_alpha_window_ground_truth.json").exists():
        print(
            "M11 boundary integrity audit skipped: private corpus / "
            "ground-truth files not present on this machine. Safe to run "
            "without them."
        )
        return

    detector = PaddleTextDetector()
    detector.initialize()
    try:
        for label, path, document, fixture in _fixtures():
            video = _CORPUS_DIR / fixture["video_path"]
            if not video.exists():
                print(f"\n=== {label} === skipped: video absent")
                continue
            results = audit_fixture(
                detector, video, ROI(*fixture["roi"]), fixture, label
            )
            apply_revisions(fixture, results)
            path.write_text(
                json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8"
            )
    finally:
        detector.shutdown()


if __name__ == "__main__":
    run()
