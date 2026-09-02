"""M11 Research Gate -- Hybrid Cascade cost gate.

Beta-S settled accuracy; this asks whether that accuracy can be bought
with far fewer detector calls. For each of the three frozen real 10s
windows it runs:

    baseline  Beta-S, detector on every sampled frame  (50 calls / 10s)
    cascade   Beta-S, detector only where the cheap Alpha-D temporal
              evidence says "possibly changing", plus a periodic safety
              sentinel that no cheap verdict can suppress

and reports the accuracy contract (100% semantic transition recall, zero
swallowed states, <= 20 representatives) alongside the cost contract
(detector invocations, where each came from, detector wall time, and the
estimated end-to-end detector + recognition total).

The detector runs for real in BOTH passes rather than being replayed, so
the wall-time comparison is a measurement rather than an extrapolation.
Its output is deterministic for a given frame, so the two passes still
see identical localization wherever they look at the same frame.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_cascade_cost_gate
"""

from __future__ import annotations

from typing import Any

from glyphcue.application.beta_detector_dry_run import run_beta_detector_dry_run
from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.hybrid_cascade_dry_run import (
    CASCADE_CANDIDATE_DISTANCE_THRESHOLD,
    MAX_DETECTOR_GAP_SECONDS,
    run_hybrid_cascade_dry_run,
)
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import (
    _CORPUS_DIR,
    _FROZEN_SAMPLING_FPS,
    _HARD_MAX_REPRESENTATIVES,
    _RECOGNITION_LATENCY_SECONDS,
    _load_fixtures,
    _rep_in_window,
    _swallowed_states,
    _tolerance_seconds,
)
from benchmarks.m11_detector_assisted_beta.run_beta_n_comparison import (
    _representatives_per_state,
)

# The cost target this round was given: detector calls per 10s window.
_COST_TARGET = 20


def _accuracy(result, states: list[dict], tolerance: float) -> dict[str, Any]:
    reps = result.representative_timestamps
    transitions = [
        _rep_in_window(reps, before["start_seconds"], before["end_seconds"], tolerance)
        and _rep_in_window(reps, after["start_seconds"], after["end_seconds"], tolerance)
        for before, after in zip(states, states[1:])
    ]
    return {
        "representative_count": result.representative_count,
        "recall": f"{sum(transitions)}/{len(transitions)}",
        "recall_complete": all(transitions),
        "swallowed_states": _swallowed_states(reps, states, tolerance),
        "per_state": _representatives_per_state(reps, states, tolerance),
        "within_hard_cap": result.representative_count <= _HARD_MAX_REPRESENTATIVES,
    }


def run() -> dict[str, Any] | None:
    fixtures = _load_fixtures()
    if not fixtures:
        print(
            "M11 cascade cost gate skipped: private corpus / ground-truth "
            "files not present on this machine. Safe to run without them."
        )
        return None

    tolerance = _tolerance_seconds()
    print(
        f"Cheap-gate candidate threshold {CASCADE_CANDIDATE_DISTANCE_THRESHOLD:.3f}; "
        f"safety sentinel every {MAX_DETECTOR_GAP_SECONDS:.1f}s; "
        f"evidence grid {_FROZEN_SAMPLING_FPS:.0f} fps."
    )

    detector = PaddleTextDetector()
    detector.initialize()

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

            baseline = run_beta_detector_dry_run(
                video_path,
                processing_range,
                roi,
                _FROZEN_SAMPLING_FPS,
                detect=detector,
                signature_fn=beta_s_signature,
            )
            cascade = run_hybrid_cascade_dry_run(
                video_path, processing_range, roi, _FROZEN_SAMPLING_FPS, detect=detector
            )

            base_acc = _accuracy(baseline, states, tolerance)
            cas_acc = _accuracy(cascade, states, tolerance)
            passed = (
                cas_acc["recall_complete"]
                and not cas_acc["swallowed_states"]
                and cas_acc["within_hard_cap"]
                and cascade.detector_invocations <= _COST_TARGET
            )

            base_total = (
                baseline.detector_wall_seconds
                + baseline.representative_count * _RECOGNITION_LATENCY_SECONDS
            )
            cascade_total = (
                cascade.detector_wall_seconds
                + cascade.representative_count * _RECOGNITION_LATENCY_SECONDS
            )
            dense_total = baseline.sampled_frame_count * _RECOGNITION_LATENCY_SECONDS

            reports.append(
                {
                    "fixture_id": fixture["id"],
                    "real_state_count": len(states),
                    "baseline": {
                        "detector_invocations": baseline.detector_invocations,
                        "detector_wall_seconds": round(baseline.detector_wall_seconds, 2),
                        **base_acc,
                    },
                    "cascade": {
                        "detector_invocations": cascade.detector_invocations,
                        "detector_wall_seconds": round(cascade.detector_wall_seconds, 2),
                        "cheap_gate_wall_seconds": round(cascade.cheap_gate_wall_seconds, 2),
                        "trigger_counts": cascade.trigger_counts,
                        "max_detector_gap_seconds": round(cascade.max_detector_gap_seconds, 2),
                        "detector_call_reduction": round(cascade.detector_call_reduction, 3),
                        **cas_acc,
                    },
                    "estimated_seconds": {
                        "dense_recognition": round(dense_total, 1),
                        "beta_s_baseline": round(base_total, 1),
                        "cascade": round(cascade_total, 1),
                    },
                    "PASS": passed,
                }
            )

            print(f"\n=== Fixture: {fixture['id']} ===")
            print(f"  Real states / transitions: {len(states)} / {len(states) - 1}")
            print(f"  {'':28}{'Beta-S':>12}{'Cascade':>12}")
            print(
                f"  {'detector invocations':28}{baseline.detector_invocations:>12}"
                f"{cascade.detector_invocations:>12}"
            )
            print(
                f"  {'detector wall seconds':28}{baseline.detector_wall_seconds:>12.2f}"
                f"{cascade.detector_wall_seconds:>12.2f}"
            )
            print(f"  {'representatives':28}{base_acc['representative_count']:>12}{cas_acc['representative_count']:>12}")
            print(f"  {'transition recall':28}{base_acc['recall']:>12}{cas_acc['recall']:>12}")
            print(
                f"  {'swallowed states':28}{str(base_acc['swallowed_states'] or 'none'):>12}"
                f"{str(cas_acc['swallowed_states'] or 'none'):>12}"
            )
            print(f"  cheap gate wall seconds:    {cascade.cheap_gate_wall_seconds:.2f}")
            print(f"  detector call reduction:    {cascade.detector_call_reduction:.1%}")
            print(f"  max detector gap:           {cascade.max_detector_gap_seconds:.2f}s")
            print(f"  trigger sources:            {cascade.trigger_counts}")
            print("  representatives per real state (Beta-S -> cascade):")
            for state in states:
                index = state["index"]
                marker = "   <-- LOST" if cas_acc["per_state"][index] == 0 else ""
                print(
                    f"    state {index}: {base_acc['per_state'][index]:>2} -> "
                    f"{cas_acc['per_state'][index]:>2}{marker}"
                )
            print("  estimated detector + recognition total:")
            print(f"    dense recognition on every sample: {dense_total:7.1f}s")
            print(f"    Beta-S baseline:                   {base_total:7.1f}s")
            print(f"    cascade:                           {cascade_total:7.1f}s")
            print(f"  PASS (cost target <= {_COST_TARGET} calls): {passed}")
    finally:
        detector.shutdown()

    overall = bool(reports) and all(r["PASS"] for r in reports)
    print(f"\n=== Hybrid Cascade Cost Gate: {'PASS' if overall else 'FAIL'} ===")
    return {"fixtures": reports, "overall_pass": overall}


if __name__ == "__main__":
    run()
