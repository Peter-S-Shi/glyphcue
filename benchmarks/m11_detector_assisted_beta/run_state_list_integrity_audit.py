"""M11 Research Gate -- ground-truth STATE-LIST integrity audit.

The boundary audit re-verified where annotated boundaries fall, taking
the annotated state LIST as given. That is exactly what it could not
check: a state whose onset is annotated a second late, with a blank gap
recorded over the interval the caption actually occupies, passes a
boundary audit because both of its reference frames come from the same
list. sample_a turned out to be that case.

So this audit assumes nothing about how many states there are and
rebuilds each fixture's list from evidence.

THE RULE, fixed before the first run and applied identically to every
fixture. No candidate distance threshold is read or consulted anywhere
in it, and nothing is added, removed or moved because it would help a
calibration.

  1. Sample the declared window at 10 fps (0.1s resolution) on the
     fixture's own frozen ROI.
  2. Per frame, take the detector's caption LINE boxes and -- where a
     line exists -- the REAL recognized text, normalized (punctuation
     and whitespace dropped, lowercased). Recognition is the
     segmentation evidence precisely because equality of text is exact
     and threshold-free, unlike any distance.
  3. Identity key: BLANK (no line), UNREADABLE (a line that recognized
     to nothing), or the normalized text.
  4. Maximal runs of one key. A run under 0.2s between two DIFFERENT
     runs is a transition -- a crossfade or a one-frame recognition
     stutter -- belonging to neither neighbour. Runs of the same key
     separated only by transitions merge back: a caption does not stop
     being itself because recognition stuttered.
  5. What survives: text runs are STATES, blank runs of at least 0.2s
     are BLANK INTERVALS.
  6. AMBIGUITY MEANS STOP, never guess. Flagged when an UNREADABLE run
     lasts 0.3s or more, or when the identity changes three or more
     times inside 0.5s. Those windows go to a human, and that fixture's
     list is neither rewritten nor frozen.

Caption text is private. States are identified in all output by a short
hash of their text, never by the text.

Requires the `[ocr]` extra (detection AND recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_state_list_integrity_audit
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource
from glyphcue.application.detector_assisted_signature import (
    MAX_LINES,
    detected_lines_from_polygons,
)
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import _CORPUS_DIR

_AUDIT_FPS = 10.0
_INTERVAL = 1.0 / _AUDIT_FPS
_MIN_RUN_SECONDS = 0.2
_UNREADABLE_AMBIGUITY_SECONDS = 0.3
_MAX_IDENTITY_CHANGES_PER_HALF_SECOND = 3

_PUNCTUATION = re.compile(r"[^\w一-鿿]+", re.UNICODE)


def _normalize(text: str) -> str:
    return _PUNCTUATION.sub("", text).lower()


def _short(key: str) -> str:
    if key in ("BLANK", "UNREADABLE"):
        return key
    return "text:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


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
            "roi": tuple(data["roi"]),
            "window": (data["window_start_seconds"], data["window_end_seconds"]),
            "language": "en",
            "states": [(s["start_seconds"], s["end_seconds"]) for s in data["states"]],
        }
    ]
    for fixture in json.loads(generalization.read_text(encoding="utf-8"))["fixtures"]:
        out.append(
            {
                "name": "sample_a" if "sample_a" in fixture["id"] else "sample_b",
                "video": _CORPUS_DIR / fixture["video_path"],
                "roi": tuple(fixture["roi"]),
                "window": (
                    fixture["window_start_seconds"],
                    fixture["window_end_seconds"],
                ),
                "language": "zh",
                "states": [
                    (s["start_seconds"], s["end_seconds"]) for s in fixture["states"]
                ],
            }
        )
    return out


def _capture(detector, fixture) -> list[dict[str, Any]]:
    engine = PaddleOcrEngine(language=fixture["language"])
    engine.initialize()
    roi = ROI(*fixture["roi"])
    next_sample = fixture["window"][0]
    rows: list[dict[str, Any]] = []
    source = PyAvMediaFrameSource()
    source.open(fixture["video"])
    try:
        for timestamp, frame in source.frames(*fixture["window"]):
            if timestamp < next_sample:
                continue
            next_sample += _INTERVAL
            roi_frame = crop_to_roi(frame, roi)
            polygons = [
                np.asarray(p, dtype=np.float64) for p in (detector(roi_frame) or [])
            ]
            boxes = detected_lines_from_polygons(polygons)[:MAX_LINES]
            key = "BLANK"
            if boxes:
                regions = engine.recognize(roi_frame)
                text = _normalize(" ".join(r.text for r in regions if r.text))
                key = text if text else "UNREADABLE"
            rows.append({"timestamp": round(timestamp, 4), "key": key})
    finally:
        source.close()
        engine.shutdown()
    return rows


def _segment(rows):
    runs = []
    for row in rows:
        if runs and runs[-1]["key"] == row["key"]:
            runs[-1]["end"] = row["timestamp"]
        else:
            runs.append(
                {"key": row["key"], "start": row["timestamp"], "end": row["timestamp"]}
            )

    def duration(run):
        return run["end"] - run["start"] + _INTERVAL

    for index, run in enumerate(runs):
        run["transition"] = (
            0 < index < len(runs) - 1
            and duration(run) < _MIN_RUN_SECONDS
            and runs[index - 1]["key"] != runs[index + 1]["key"]
        )
    merged = []
    for run in runs:
        if run["transition"]:
            merged.append(run)
            continue
        previous = next((r for r in reversed(merged) if not r["transition"]), None)
        if previous is not None and previous["key"] == run["key"]:
            previous["end"] = run["end"]
            for other in merged:
                if other["transition"] and other["start"] > previous["start"]:
                    other["absorbed"] = True
            continue
        merged.append(run)
    return [r for r in merged if not r.get("absorbed")], duration


def _ambiguities(runs, duration):
    flagged = []
    for run in runs:
        if run["key"] == "UNREADABLE" and duration(run) >= _UNREADABLE_AMBIGUITY_SECONDS:
            flagged.append((run["start"], run["end"], "unreadable text region"))
    for index, run in enumerate(runs):
        window = [r for r in runs[index:] if r["start"] < run["start"] + 0.5]
        if len(window) > _MAX_IDENTITY_CHANGES_PER_HALF_SECOND:
            flagged.append(
                (
                    window[0]["start"],
                    window[-1]["end"],
                    f"{len(window)} identity changes within 0.5s",
                )
            )
    return flagged


def run() -> dict[str, Any] | None:
    fixtures = _fixtures()
    if fixtures is None or not all(f["video"].exists() for f in fixtures):
        print(
            "M11 state-list integrity audit skipped: private corpus / "
            "ground-truth files not present on this machine. Safe to run "
            "without them."
        )
        return None

    detector = PaddleTextDetector()
    detector.initialize()
    verdicts = {}
    try:
        for fixture in fixtures:
            rows = _capture(detector, fixture)
            runs, duration = _segment(rows)
            states = [
                r
                for r in runs
                if r["key"] not in ("BLANK", "UNREADABLE") and not r["transition"]
            ]
            blanks = [
                r
                for r in runs
                if r["key"] == "BLANK"
                and not r["transition"]
                and duration(r) >= _MIN_RUN_SECONDS
            ]
            flagged = _ambiguities(runs, duration)
            print(f"\n=== {fixture['name']} ===")
            print(
                f"  evidence: {len(states)} text states, {len(blanks)} blank intervals; "
                f"ground truth records {len(fixture['states'])} states"
            )
            for run in runs:
                if run["transition"]:
                    kind = "transition"
                elif run["key"] == "BLANK":
                    kind = "blank" if duration(run) >= _MIN_RUN_SECONDS else "blank(short)"
                elif run["key"] == "UNREADABLE":
                    kind = "unreadable"
                else:
                    kind = "STATE"
                print(
                    f"  {kind:14s}{run['start']:10.3f}{run['end']:10.3f}"
                    f"{duration(run):7.2f}  {_short(run['key'])}"
                )
            if flagged:
                verdict = "INCONCLUSIVE -- needs human adjudication"
                print("  AMBIGUOUS WINDOWS:")
                seen = set()
                for start, end, why in flagged:
                    if (round(start, 2), round(end, 2)) in seen:
                        continue
                    seen.add((round(start, 2), round(end, 2)))
                    print(f"    {start:.3f}-{end:.3f}  {why}")
            elif len(states) == len(fixture["states"]):
                verdict = "CONFIRMED"
            else:
                verdict = "MISMATCH -- evidence disagrees with the recorded list"
            print(f"  verdict: {verdict}")
            verdicts[fixture["name"]] = verdict
    finally:
        detector.shutdown()
    return verdicts


if __name__ == "__main__":
    run()
