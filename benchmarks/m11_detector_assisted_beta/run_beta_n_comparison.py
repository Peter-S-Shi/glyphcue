"""M11 Research Gate -- Beta-N signature-normalization corrective.

Runs the ORIGINAL Beta signature (41e80f9: stretch-to-fixed-width hard
binary bands, cell-mismatch distance) and the Beta-N signature
(aspect-preserving soft coverage bands, shift-tolerant mass-normalized
distance) over the same three frozen real 10s windows, and reports the
per-fixture before/after.

Everything except normalization and comparison is held fixed: the same
detector, the same 5 fps sampling profile, the same 0.10 grouping
threshold, the same blank rule, the same
sampling -> grouping -> representative harness. Both variants even share
the SAME detector output: the detector runs once per fixture and its
polygons are replayed to the second variant from a cache, so the two
runs cannot differ by so much as one box, and any difference observed is
attributable to normalization alone.

The decisive check is not the representative count but WHERE the
representatives went: `representatives per real state` must drop only
where one real state had been fragmented into many, and must never drop
to zero for any real state (that would be the Alpha family's
state-swallowing failure returning in a new disguise).

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_beta_n_comparison
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from glyphcue.application.beta_detector_dry_run import run_beta_detector_dry_run
from glyphcue.application.beta_normalized_signature import (
    beta_normalized_signature,
    shift_tolerant_distance,
)
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import (
    _CORPUS_DIR,
    _FROZEN_SAMPLING_FPS,
    _HARD_MAX_REPRESENTATIVES,
    _load_fixtures,
    _rep_in_window,
    _swallowed_states,
    _tolerance_seconds,
)


class _RecordingDetector:
    """Runs the real detector once, then replays its polygons so a second
    variant sees byte-identical localization."""

    def __init__(self, detector: PaddleTextDetector) -> None:
        self._detector = detector
        self._recorded: list[Any] = []
        self._replay_index: int | None = None

    def record(self) -> None:
        self._recorded = []
        self._replay_index = None

    def replay(self) -> None:
        self._replay_index = 0

    def __call__(self, roi_frame):
        if self._replay_index is None:
            polygons = self._detector(roi_frame)
            self._recorded.append(polygons)
            return polygons
        polygons = self._recorded[self._replay_index]
        self._replay_index += 1
        return polygons


def _representatives_per_state(reps: list[float], states: list[dict], tolerance: float) -> dict[int, int]:
    return {
        state["index"]: sum(
            1
            for t in reps
            if (state["start_seconds"] - tolerance) <= t <= (state["end_seconds"] + tolerance)
        )
        for state in states
    }


def _summarize(result, states: list[dict], tolerance: float) -> dict[str, Any]:
    reps = result.representative_timestamps
    transitions = [
        _rep_in_window(reps, before["start_seconds"], before["end_seconds"], tolerance)
        and _rep_in_window(reps, after["start_seconds"], after["end_seconds"], tolerance)
        for before, after in zip(states, states[1:])
    ]
    return {
        "representative_count": result.representative_count,
        "blank_group_count": result.blank_group_count,
        "recall": f"{sum(transitions)}/{len(transitions)}",
        "recall_complete": all(transitions),
        "swallowed_states": _swallowed_states(reps, states, tolerance),
        "fragmentation_ratio": round(result.representative_count / max(1, len(states)), 2),
        "per_state": _representatives_per_state(reps, states, tolerance),
        "within_hard_cap": result.representative_count <= _HARD_MAX_REPRESENTATIVES,
        "representatives": [round(t, 2) for t in reps],
    }


def run() -> dict[str, Any] | None:
    fixtures = _load_fixtures()
    if not fixtures:
        print(
            "M11 Beta-N comparison skipped: private corpus / ground-truth "
            "files not present on this machine. Safe to run without them."
        )
        return None

    tolerance = _tolerance_seconds()
    detector = PaddleTextDetector()
    detector.initialize()
    recorder = _RecordingDetector(detector)

    reports = []
    try:
        for fixture in fixtures:
            video_path = _CORPUS_DIR / fixture["video_path"]
            if not video_path.exists():
                print(f"Skipping {fixture['id']}: {video_path.name} not present.")
                continue

            roi = ROI(*fixture["roi"])
            processing_range = ProcessingRange(
                start_time=fixture["window_start_seconds"],
                end_time=fixture["window_end_seconds"],
            )
            states = fixture["states"]

            recorder.record()
            beta = run_beta_detector_dry_run(
                video_path, processing_range, roi, _FROZEN_SAMPLING_FPS, detect=recorder
            )

            recorder.replay()
            beta_n = run_beta_detector_dry_run(
                video_path,
                processing_range,
                roi,
                _FROZEN_SAMPLING_FPS,
                detect=recorder,
                signature_fn=beta_normalized_signature,
                distance_fn=shift_tolerant_distance,
            )

            before = _summarize(beta, states, tolerance)
            after = _summarize(beta_n, states, tolerance)
            passed = (
                after["recall_complete"]
                and not after["swallowed_states"]
                and after["within_hard_cap"]
            )
            reports.append(
                {
                    "fixture_id": fixture["id"],
                    "real_state_count": len(states),
                    "real_transition_count": len(states) - 1,
                    "beta": before,
                    "beta_n": after,
                    "PASS": passed,
                }
            )

            print(f"\n=== Fixture: {fixture['id']} ===")
            print(f"  Real states / transitions: {len(states)} / {len(states) - 1}")
            print(f"  {'':22}{'Beta':>10}{'Beta-N':>10}")
            print(f"  {'representatives':22}{before['representative_count']:>10}{after['representative_count']:>10}")
            print(f"  {'transition recall':22}{before['recall']:>10}{after['recall']:>10}")
            print(f"  {'fragmentation ratio':22}{before['fragmentation_ratio']:>10}{after['fragmentation_ratio']:>10}")
            print(f"  {'swallowed states':22}{str(before['swallowed_states'] or 'none'):>10}{str(after['swallowed_states'] or 'none'):>10}")
            print(f"  {'blank groups':22}{before['blank_group_count']:>10}{after['blank_group_count']:>10}")
            print("  representatives per real state (Beta -> Beta-N):")
            for state in states:
                index = state["index"]
                print(
                    f"    state {index}: {before['per_state'][index]:>2} -> {after['per_state'][index]:>2}"
                    + ("   <-- LOST" if after["per_state"][index] == 0 else "")
                )
            print(f"  PASS: {passed}")
    finally:
        detector.shutdown()

    overall = bool(reports) and all(r["PASS"] for r in reports)
    print(f"\n=== Beta-N Gate: {'PASS' if overall else 'FAIL'} ===")
    return {"fixtures": reports, "overall_pass": overall}


if __name__ == "__main__":
    run()
