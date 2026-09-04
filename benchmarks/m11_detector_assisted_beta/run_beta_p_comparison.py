"""M11 Research Gate -- Beta-P photometric-decoupling comparison.

Runs the ORIGINAL Beta signature (41e80f9) and Beta-P (Beta with ONLY
its photometric ink rule replaced by a local-contrast rule) over the
same three frozen real 10s windows.

Everything except the ink rule is frozen: same detector configuration,
same 5 fps sampling, same canonical band layout, same cell-mismatch
distance, same 0.10 grouping threshold, same blank rule, same
sampling -> grouping -> representative harness. Both variants also share
byte-identical detector output (the detector runs once per fixture and
its polygons are replayed to the second variant), so any difference
observed is attributable to the photometric layer alone.

Beyond the gate numbers, this reports WITHIN-STATE fragmentation --
representatives per real ground-truth state -- because the question this
round asks is specifically whether photometric coupling was what split
held captions, not merely whether the total went down.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_beta_p_comparison
"""

from __future__ import annotations

from typing import Any

from glyphcue.application.beta_detector_dry_run import run_beta_detector_dry_run
from glyphcue.application.beta_photometric_ink import beta_p_signature
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
from benchmarks.m11_detector_assisted_beta.run_beta_n_comparison import (
    _RecordingDetector,
    _representatives_per_state,
)


def _summarize(result, states: list[dict], tolerance: float) -> dict[str, Any]:
    reps = result.representative_timestamps
    transitions = [
        _rep_in_window(reps, before["start_seconds"], before["end_seconds"], tolerance)
        and _rep_in_window(reps, after["start_seconds"], after["end_seconds"], tolerance)
        for before, after in zip(states, states[1:])
    ]
    per_state = _representatives_per_state(reps, states, tolerance)
    return {
        "representative_count": result.representative_count,
        "blank_group_count": result.blank_group_count,
        "recall": f"{sum(transitions)}/{len(transitions)}",
        "recall_complete": all(transitions),
        "swallowed_states": _swallowed_states(reps, states, tolerance),
        "fragmentation_ratio": round(result.representative_count / max(1, len(states)), 2),
        "per_state": per_state,
        # Fragmentation strictly INSIDE real states: how many extra
        # representatives a state collected beyond the one it needs.
        "within_state_excess": sum(max(0, n - 1) for n in per_state.values()),
        "within_hard_cap": result.representative_count <= _HARD_MAX_REPRESENTATIVES,
    }


def run() -> dict[str, Any] | None:
    fixtures = _load_fixtures()
    if not fixtures:
        print(
            "M11 Beta-P comparison skipped: private corpus / ground-truth "
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
            beta_p = run_beta_detector_dry_run(
                video_path,
                processing_range,
                roi,
                _FROZEN_SAMPLING_FPS,
                detect=recorder,
                signature_fn=beta_p_signature,
            )

            before = _summarize(beta, states, tolerance)
            after = _summarize(beta_p, states, tolerance)
            passed = (
                after["recall_complete"]
                and not after["swallowed_states"]
                and after["within_hard_cap"]
            )
            reports.append(
                {
                    "fixture_id": fixture["id"],
                    "real_state_count": len(states),
                    "beta": before,
                    "beta_p": after,
                    "PASS": passed,
                }
            )

            print(f"\n=== Fixture: {fixture['id']} ===")
            print(f"  Real states / transitions: {len(states)} / {len(states) - 1}")
            print(f"  {'':24}{'Beta':>10}{'Beta-P':>10}")
            print(f"  {'representatives':24}{before['representative_count']:>10}{after['representative_count']:>10}")
            print(f"  {'transition recall':24}{before['recall']:>10}{after['recall']:>10}")
            print(f"  {'swallowed states':24}{str(before['swallowed_states'] or 'none'):>10}{str(after['swallowed_states'] or 'none'):>10}")
            print(f"  {'fragmentation ratio':24}{before['fragmentation_ratio']:>10}{after['fragmentation_ratio']:>10}")
            print(f"  {'within-state excess reps':24}{before['within_state_excess']:>10}{after['within_state_excess']:>10}")
            print(f"  {'blank groups':24}{before['blank_group_count']:>10}{after['blank_group_count']:>10}")
            print("  representatives per real state (Beta -> Beta-P):")
            for state in states:
                index = state["index"]
                marker = "   <-- LOST" if after["per_state"][index] == 0 else ""
                print(
                    f"    state {index}: {before['per_state'][index]:>2} -> {after['per_state'][index]:>2}{marker}"
                )
            print(f"  PASS: {passed}")
    finally:
        detector.shutdown()

    overall = bool(reports) and all(r["PASS"] for r in reports)
    print(f"\n=== Beta-P Gate: {'PASS' if overall else 'FAIL'} ===")
    return {"fixtures": reports, "overall_pass": overall}


if __name__ == "__main__":
    run()
