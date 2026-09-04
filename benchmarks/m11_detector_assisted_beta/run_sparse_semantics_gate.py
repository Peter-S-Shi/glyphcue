"""M11 Research Gate -- sparse observation semantics gate.

The Hybrid-T scheduler is frozen exactly as committed in e8a1910. This
run changes only what happens DOWNSTREAM of its observations, and tests
the two fixes independently so neither can be credited with the other's
result:

    hybrid_t      e8a1910 as-is                     (the two failures)
    + rep         stable (medoid) representative    (sample_a state 1)
    + rep + tail  and the boundary guarantee        (sample_b state 5)

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_sparse_semantics_gate
"""

from __future__ import annotations

from typing import Any

from glyphcue.application.hybrid_cascade_dry_run import run_hybrid_cascade_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.sparse_observation_semantics import stable_representative
from glyphcue.application.text_anchored_region_mask import TextAnchoredRegionMask
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import (
    _CORPUS_DIR,
    _FROZEN_SAMPLING_FPS,
    _RECOGNITION_LATENCY_SECONDS,
    _load_fixtures,
    _tolerance_seconds,
)
from benchmarks.m11_detector_assisted_beta.run_cascade_cost_gate import _COST_TARGET, _accuracy

_VARIANTS = ("hybrid_t", "+rep", "+rep+tail")


def run() -> dict[str, Any] | None:
    fixtures = _load_fixtures()
    if not fixtures:
        print(
            "M11 sparse semantics gate skipped: private corpus / ground-truth "
            "files not present on this machine. Safe to run without them."
        )
        return None

    tolerance = _tolerance_seconds()
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

            def _run(**kwargs):
                return run_hybrid_cascade_dry_run(
                    video_path,
                    processing_range,
                    roi,
                    _FROZEN_SAMPLING_FPS,
                    detect=detector,
                    cheap_region_mask=TextAnchoredRegionMask(),
                    **kwargs,
                )

            runs = {
                "hybrid_t": _run(),
                "+rep": _run(representative=stable_representative),
                "+rep+tail": _run(representative=stable_representative, guarantee_tail=True),
            }
            acc = {name: _accuracy(run, states, tolerance) for name, run in runs.items()}
            final = acc["+rep+tail"]
            # This round's cost contract is a NO-REGRESSION one, not the
            # flat <= 20 of the scheduler round: the frozen Hybrid-T call
            # count may rise by at most the single fixed boundary call
            # the tail guarantee adds. sample_d sits at 23 for scheduler
            # reasons this round is not allowed to touch.
            cost_ceiling = runs["hybrid_t"].detector_invocations + 1
            cost_ok = runs["+rep+tail"].detector_invocations <= cost_ceiling
            passed = (
                final["recall_complete"]
                and not final["swallowed_states"]
                and final["within_hard_cap"]
                and cost_ok
            )
            totals = {
                name: run.detector_wall_seconds
                + run.representative_count * _RECOGNITION_LATENCY_SECONDS
                for name, run in runs.items()
            }

            reports.append(
                {
                    "fixture_id": fixture["id"],
                    "real_state_count": len(states),
                    **{
                        name: {
                            "detector_invocations": runs[name].detector_invocations,
                            "detector_wall_seconds": round(runs[name].detector_wall_seconds, 2),
                            "estimated_total_seconds": round(totals[name], 1),
                            "trigger_counts": runs[name].trigger_counts,
                            **acc[name],
                        }
                        for name in _VARIANTS
                    },
                    "PASS": passed,
                }
            )

            print(f"\n=== Fixture: {fixture['id']} ===")
            print(f"  Real states / transitions: {len(states)} / {len(states) - 1}")
            print(f"  {'':30}{'hybrid_t':>12}{'+rep':>12}{'+rep+tail':>12}")
            for label, getter in (
                ("detector invocations", lambda r, a: r.detector_invocations),
                ("detector wall seconds", lambda r, a: f"{r.detector_wall_seconds:.1f}"),
                ("representatives", lambda r, a: a["representative_count"]),
                ("transition recall", lambda r, a: a["recall"]),
                ("swallowed states", lambda r, a: a["swallowed_states"] or "none"),
            ):
                row = "".join(f"{str(getter(runs[n], acc[n])):>12}" for n in _VARIANTS)
                print(f"  {label:30}{row}")
            row = "".join(f"{totals[n]:>12.1f}" for n in _VARIANTS)
            print(f"  {'est. detector+recognition (s)':30}{row}")
            print(f"  +rep+tail triggers: {runs['+rep+tail'].trigger_counts}")
            print("  representatives per real state (hybrid_t -> +rep -> +rep+tail):")
            for state in states:
                index = state["index"]
                marker = "   <-- LOST" if acc["+rep+tail"]["per_state"][index] == 0 else ""
                counts = " -> ".join(f"{acc[n]['per_state'][index]:>2}" for n in _VARIANTS)
                print(f"    state {index}: {counts}{marker}")
            print(
                f"  cost ceiling (frozen Hybrid-T + 1 boundary call): {cost_ceiling}; "
                f"target band {_COST_TARGET} -- PASS: {passed}"
            )
    finally:
        detector.shutdown()

    overall = bool(reports) and all(r["PASS"] for r in reports)
    print(f"\n=== Sparse Observation Semantics Gate: {'PASS' if overall else 'FAIL'} ===")
    return {"fixtures": reports, "overall_pass": overall}


if __name__ == "__main__":
    run()
