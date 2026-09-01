"""M11 Research Gate -- Detector-Assisted Beta dry run over all three
frozen real 10s evidence windows.

Runs ONE set of Beta rules (one detector configuration, one grouping
threshold, one sampling profile -- 5 fps, the frozen Alpha-D2 candidate
profile) unchanged across sample_d, sample_a and sample_b. No
fixture-specific parameters anywhere in this script.

Answers two questions in one run:

1. Accuracy -- per fixture: real states/transitions, representatives,
   semantic transition recall, fragmentation ratio, and whether any real
   state was SWALLOWED by a neighbour (the exact failure that stopped
   the Alpha family in commit faf8bc4; note the Generalization Gate's
   own merge check only caught a group skipping a whole intervening
   state, so this script checks the stricter "a real state kept no
   representative at all" condition directly).
2. Cost -- detector invocations, detector wall time, cold vs. warm
   latency, and the resulting end-to-end cost model against both naive
   dense OCR and the classical Alpha-D2 gate, so "detector-assisted is
   more accurate, but is it cheap enough to be a recognition gate?" is
   answered with measured numbers rather than an assumption.

Tracked; the private corpus and ground-truth files it reads are NOT
(gitignored). Safe no-op if absent.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_beta_dry_run
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from glyphcue.application.beta_detector_dry_run import run_beta_detector_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector

_CORPUS_DIR = Path(__file__).resolve().parents[2] / "private_samples" / "m10_video_corpus"
_SAMPLE_D_GROUND_TRUTH = _CORPUS_DIR / "sample_d_alpha_window_ground_truth.json"
_GENERALIZATION_GROUND_TRUTH = _CORPUS_DIR / "generalization_gate_ground_truth.json"

# The frozen candidate profile carried over from Alpha-D2 (8ebd856).
_FROZEN_SAMPLING_FPS = 5.0

# Pre-declared evaluation tolerance, identical to the Generalization
# Gate round's: applied at check time, never by editing stored
# ground-truth numbers.
_DEFAULT_TOLERANCE_SECONDS = 0.08

# Measured mean PaddleOCR *recognition* latency on this machine, from
# the M10/M11 performance evidence already recorded in
# prompt-drafts/GlyphCue_Temporal_OCR_Research_Handoff_2026-09-01.md
# (~3.15s/call). Used only to express the cost model below in seconds.
_RECOGNITION_LATENCY_SECONDS = 3.15

_HARD_MAX_REPRESENTATIVES = 20
_IDEAL_MIN_REPRESENTATIVES = 8
_IDEAL_MAX_REPRESENTATIVES = 15


def _rep_in_window(reps: list[float], start: float, end: float, tolerance: float) -> bool:
    return any((start - tolerance) <= t <= (end + tolerance) for t in reps)


def _swallowed_states(reps: list[float], states: list[dict], tolerance: float) -> list[int]:
    """Real states that kept NO representative of their own -- i.e. were
    swallowed by a neighbouring state's group. This is the strict
    cross-state merge condition for this round: it catches an adjacent
    swallow, which the Generalization Gate's skip-a-whole-state check
    did not."""
    return [
        state["index"]
        for state in states
        if not _rep_in_window(reps, state["start_seconds"], state["end_seconds"], tolerance)
    ]


def _load_fixtures() -> list[dict]:
    """Normalizes the two private ground-truth files into one shape."""
    fixtures: list[dict] = []

    if _SAMPLE_D_GROUND_TRUTH.exists():
        raw = json.loads(_SAMPLE_D_GROUND_TRUTH.read_text(encoding="utf-8"))
        fixtures.append(
            {
                "id": "sample_d_bilingual_typical",
                "style_note": (
                    "Bilingual en/zh two-line captions, talking-head hair/face motion "
                    "inside the ROI. The window every Alpha round was developed against."
                ),
                "video_path": raw["video_path"],
                "window_start_seconds": raw["window_start_seconds"],
                "window_end_seconds": raw["window_end_seconds"],
                "roi": raw["roi"],
                "states": raw["states"],
            }
        )

    if _GENERALIZATION_GROUND_TRUTH.exists():
        raw = json.loads(_GENERALIZATION_GROUND_TRUTH.read_text(encoding="utf-8"))
        fixtures.extend(raw["fixtures"])

    return fixtures


def _tolerance_seconds() -> float:
    if _GENERALIZATION_GROUND_TRUTH.exists():
        raw = json.loads(_GENERALIZATION_GROUND_TRUTH.read_text(encoding="utf-8"))
        return float(raw.get("tolerance_seconds", _DEFAULT_TOLERANCE_SECONDS))
    return _DEFAULT_TOLERANCE_SECONDS


def _evaluate_fixture(fixture: dict, detector: PaddleTextDetector, tolerance: float) -> dict[str, Any]:
    video_path = _CORPUS_DIR / fixture["video_path"]
    roi = ROI(*fixture["roi"])
    processing_range = ProcessingRange(
        start_time=fixture["window_start_seconds"], end_time=fixture["window_end_seconds"]
    )

    result = run_beta_detector_dry_run(
        video_path,
        processing_range,
        roi,
        sampling_fps=_FROZEN_SAMPLING_FPS,
        detect=detector,
    )

    reps = result.representative_timestamps
    states = fixture["states"]

    transitions = []
    for before, after in zip(states, states[1:]):
        bracketed = _rep_in_window(
            reps, before["start_seconds"], before["end_seconds"], tolerance
        ) and _rep_in_window(reps, after["start_seconds"], after["end_seconds"], tolerance)
        transitions.append(
            {"between_states": [before["index"], after["index"]], "bracketed": bracketed}
        )

    recall = sum(1 for t in transitions if t["bracketed"])
    swallowed = _swallowed_states(reps, states, tolerance)
    within_cap = result.representative_count <= _HARD_MAX_REPRESENTATIVES

    detected = result.detected_box_counts
    return {
        "fixture_id": fixture["id"],
        "real_state_count": len(states),
        "real_transition_count": len(transitions),
        "representative_count": result.representative_count,
        "blank_group_count": result.blank_group_count,
        "fragmentation_ratio": round(result.representative_count / max(1, len(states)), 2),
        "transition_recall": f"{recall}/{len(transitions)}",
        "transitions": transitions,
        "swallowed_states": swallowed,
        "within_hard_cap_20": within_cap,
        "within_ideal_band_8_to_15": (
            _IDEAL_MIN_REPRESENTATIVES
            <= result.representative_count
            <= _IDEAL_MAX_REPRESENTATIVES
        ),
        "detector_invocations": result.detector_invocations,
        "detector_wall_seconds": round(result.detector_wall_seconds, 2),
        "detector_cold_latency_seconds": round(result.detector_cold_latency_seconds, 3),
        "detector_warm_mean_latency_seconds": round(
            result.detector_warm_mean_latency_seconds, 3
        ),
        "detected_boxes_min_max": [min(detected), max(detected)] if detected else [0, 0],
        "sampled_frame_count": result.sampled_frame_count,
        "PASS": (recall == len(transitions)) and not swallowed and within_cap,
    }


def _print_cost_model(report: dict) -> None:
    sampled = report["sampled_frame_count"]
    reps = report["representative_count"]
    gate = report["detector_wall_seconds"]
    beta_total = gate + reps * _RECOGNITION_LATENCY_SECONDS
    dense_total = sampled * _RECOGNITION_LATENCY_SECONDS

    print("  --- cost model (10s window) ---")
    print(f"  Detector gate:                {gate:7.1f}s  ({report['detector_invocations']} calls)")
    print(f"  + recognition on {reps:2d} reps:    {reps * _RECOGNITION_LATENCY_SECONDS:7.1f}s")
    print(f"  = Beta end-to-end:            {beta_total:7.1f}s")
    print(f"  Naive dense OCR @5fps:        {dense_total:7.1f}s")
    print(f"  Beta vs dense:                {dense_total / beta_total:7.2f}x cheaper")


def run() -> dict[str, Any] | None:
    fixtures = _load_fixtures()
    if not fixtures:
        print(
            "M11 Detector-Assisted Beta dry run skipped: private corpus / "
            "ground-truth files not present on this machine. Safe to run "
            "without them; it simply does nothing."
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

            report = _evaluate_fixture(fixture, detector, tolerance)
            reports.append(report)

            print(f"\n=== Fixture: {report['fixture_id']} ===")
            print(f"  Real states / transitions:  {report['real_state_count']} / {report['real_transition_count']}")
            print(f"  Representatives:             {report['representative_count']}")
            print(f"  Blank groups:                {report['blank_group_count']}")
            print(f"  Fragmentation ratio:         {report['fragmentation_ratio']}")
            print(f"  Transition recall:           {report['transition_recall']}")
            print(f"  Swallowed real states:       {report['swallowed_states'] or 'none'}")
            print(f"  Detected boxes (min..max):   {report['detected_boxes_min_max']}")
            print(f"  Detector cold / warm:        {report['detector_cold_latency_seconds']}s / {report['detector_warm_mean_latency_seconds']}s")
            print(f"  Within hard cap (<=20):      {report['within_hard_cap_20']}")
            print(f"  Within ideal band (8-15):    {report['within_ideal_band_8_to_15']}")
            print(f"  PASS:                        {report['PASS']}")
            _print_cost_model(report)
    finally:
        detector.shutdown()

    overall_pass = bool(reports) and all(r["PASS"] for r in reports)
    print(f"\n=== Detector-Assisted Beta Gate: {'PASS' if overall_pass else 'FAIL'} ===")
    return {"fixtures": reports, "overall_pass": overall_pass}


if __name__ == "__main__":
    run()
