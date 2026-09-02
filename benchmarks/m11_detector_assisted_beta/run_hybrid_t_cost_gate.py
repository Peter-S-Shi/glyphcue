"""M11 Research Gate -- Hybrid-T detector-anchored scheduler cost gate.

Three passes over each of the three frozen real 10s windows:

    dense      Beta-S, detector on every sampled frame        (50 calls)
    cascade    whole-ROI cheap scheduler + sentinel           (000fe1a)
    hybrid_t   cheap scheduler restricted to the last
               detector-confirmed text region + sentinel

Everything except the scheduler's FIELD OF VIEW is frozen: Beta-S, the
5 fps evidence grid, the 0.10 grouping threshold, the 0.03 candidate
threshold, the 1.0s safety sentinel, the detector configuration and the
recognition cost model.

Reports both contracts: accuracy (100% semantic transition recall, zero
swallowed states, <= 20 representatives) and cost (detector invocations,
trigger sources, detector wall time, estimated detector + recognition
total), plus the number this round is really about -- how often the
cheap gate fires while a caption is simply being held.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_hybrid_t_cost_gate
"""

from __future__ import annotations

from typing import Any

from glyphcue.application.beta_detector_dry_run import run_beta_detector_dry_run
from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.hybrid_cascade_dry_run import run_hybrid_cascade_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.text_anchored_region_mask import (
    PADDING_TO_LINE_HEIGHT,
    TextAnchoredRegionMask,
)
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


def _held_caption_candidates(result, states: list[dict]) -> str:
    """How often the cheap gate scheduled a call while a caption was
    merely being held -- the specific noise Hybrid-T set out to remove.
    Counts candidate observations strictly inside a real state, i.e. not
    at its boundaries, where firing is correct."""
    if not hasattr(result, "observations"):
        return "n/a"  # the dense pass has no scheduler to count
    inside = 0
    for timestamp, reason in result.observations:
        if not reason.startswith("candidate"):
            continue
        for state in states:
            margin = 0.2
            if state["start_seconds"] + margin < timestamp < state["end_seconds"] - margin:
                inside += 1
                break
    return f"{inside}"


def run() -> dict[str, Any] | None:
    fixtures = _load_fixtures()
    if not fixtures:
        print(
            "M11 Hybrid-T cost gate skipped: private corpus / ground-truth "
            "files not present on this machine. Safe to run without them."
        )
        return None

    tolerance = _tolerance_seconds()
    print(f"Text-region padding: {PADDING_TO_LINE_HEIGHT:.2f} x line height.")

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

            dense = run_beta_detector_dry_run(
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
            region_mask = TextAnchoredRegionMask()
            hybrid_t = run_hybrid_cascade_dry_run(
                video_path,
                processing_range,
                roi,
                _FROZEN_SAMPLING_FPS,
                detect=detector,
                cheap_region_mask=region_mask,
            )

            runs = {"dense": dense, "cascade": cascade, "hybrid_t": hybrid_t}
            acc = {name: _accuracy(run, states, tolerance) for name, run in runs.items()}
            final = acc["hybrid_t"]
            passed = (
                final["recall_complete"]
                and not final["swallowed_states"]
                and final["within_hard_cap"]
                and hybrid_t.detector_invocations <= _COST_TARGET
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
                            "detector_invocations": run.detector_invocations,
                            "detector_wall_seconds": round(run.detector_wall_seconds, 2),
                            "estimated_total_seconds": round(totals[name], 1),
                            **acc[name],
                        }
                        for name, run in runs.items()
                    },
                    "cascade_trigger_counts": cascade.trigger_counts,
                    "hybrid_t_trigger_counts": hybrid_t.trigger_counts,
                    "hybrid_t_masked_grid_points": region_mask.masked_count,
                    "hybrid_t_fallback_grid_points": region_mask.fallback_count,
                    "PASS": passed,
                }
            )

            print(f"\n=== Fixture: {fixture['id']} ===")
            print(f"  Real states / transitions: {len(states)} / {len(states) - 1}")
            print(f"  {'':30}{'dense':>11}{'cascade':>11}{'hybrid_t':>11}")
            for label, getter in (
                ("detector invocations", lambda r, a: r.detector_invocations),
                ("detector wall seconds", lambda r, a: f"{r.detector_wall_seconds:.1f}"),
                ("representatives", lambda r, a: a["representative_count"]),
                ("transition recall", lambda r, a: a["recall"]),
                ("swallowed states", lambda r, a: a["swallowed_states"] or "none"),
            ):
                row = "".join(f"{str(getter(runs[n], acc[n])):>11}" for n in runs)
                print(f"  {label:30}{row}")
            row = "".join(f"{totals[n]:>11.1f}" for n in runs)
            print(f"  {'est. detector+recognition (s)':30}{row}")
            row = "".join(
                f"{_held_caption_candidates(runs[n], states):>11}"
                for n in ("dense", "cascade", "hybrid_t")
            )
            print(f"  {'held-caption candidate fires':30}{row}")
            print(f"  cascade triggers:   {cascade.trigger_counts}")
            print(f"  hybrid_t triggers:  {hybrid_t.trigger_counts}")
            print(
                f"  hybrid_t grid points masked / whole-ROI fallback: "
                f"{region_mask.masked_count} / {region_mask.fallback_count}"
            )
            print("  representatives per real state (dense -> cascade -> hybrid_t):")
            for state in states:
                index = state["index"]
                marker = "   <-- LOST" if acc["hybrid_t"]["per_state"][index] == 0 else ""
                counts = " -> ".join(f"{acc[n]['per_state'][index]:>2}" for n in runs)
                print(f"    state {index}: {counts}{marker}")
            print(f"  PASS (cost target <= {_COST_TARGET} calls): {passed}")
    finally:
        detector.shutdown()

    overall = bool(reports) and all(r["PASS"] for r in reports)
    print(f"\n=== Hybrid-T Cost Gate: {'PASS' if overall else 'FAIL'} ===")
    return {"fixtures": reports, "overall_pass": overall}


if __name__ == "__main__":
    run()
