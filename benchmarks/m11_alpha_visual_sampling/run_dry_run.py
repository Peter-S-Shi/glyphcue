"""M11 Research Gate -- bounded Alpha Dry-Run experiment.

Runs `glyphcue.application.alpha_visual_dry_run.run_alpha_visual_dry_run`
against the frozen private `sample_d.mp4` 10-second window
(9.87s-19.87s, ROI approximately the bilingual caption band) at a small,
FIXED set of sampling profiles (5/8/10 fps) -- no continuous parameter
search against this fixture. Never invokes PaddleOCR.

This script is tracked; `private_samples/m10_video_corpus/sample_d.mp4`
and `sample_d_alpha_window_ground_truth.json` are NOT (gitignored, see
`private_samples/`). If either is missing (any other machine, CI, a
fresh clone), `run()` returns `None` and prints a message instead of
failing -- same safety contract as
`benchmarks/private_video_corpus/run_evaluation.py`.

Frozen acceptance contract (see
`prompt-drafts/GlyphCue_Temporal_OCR_Research_Handoff_2026-09-01.md`):
- human ground truth for this window: 7 subtitle states / 6 real
  semantic transitions.
- 6/6 transition recall is a hard gate -- a profile that brackets fewer
  than all 6 real transitions FAILS regardless of its representative
  count.
- <=20 representatives to proceed to the next phase; 8-15 is the ideal
  range.

Run manually (requires the private corpus; no `[ocr]` extra needed):
    python -m benchmarks.m11_alpha_visual_sampling.run_dry_run
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from glyphcue.application.alpha_visual_dry_run import AlphaDryRunResult, run_alpha_visual_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

_CORPUS_DIR = Path(__file__).resolve().parents[2] / "private_samples" / "m10_video_corpus"
_VIDEO_PATH = _CORPUS_DIR / "sample_d.mp4"
_GROUND_TRUTH_PATH = _CORPUS_DIR / "sample_d_alpha_window_ground_truth.json"

_SAMPLING_PROFILES_FPS: tuple[float, ...] = (5.0, 8.0, 10.0)

_HARD_MAX_REPRESENTATIVES = 20
_IDEAL_MAX_REPRESENTATIVES = 15
_IDEAL_MIN_REPRESENTATIVES = 8


def _transition_is_bracketed(
    representative_timestamps: list[float], state_before: dict, state_after: dict
) -> bool:
    """A transition is "bracketed" when at least one representative falls
    inside each of its two real states -- i.e. a selective policy built
    on these representatives would have OCR'd both the pre- and
    post-transition text, not lost one of them to a missed group."""
    has_before = any(
        state_before["start_seconds"] <= t <= state_before["end_seconds"]
        for t in representative_timestamps
    )
    has_after = any(
        state_after["start_seconds"] <= t <= state_after["end_seconds"]
        for t in representative_timestamps
    )
    return has_before and has_after


def _evaluate_profile(result: AlphaDryRunResult, ground_truth: dict) -> dict[str, Any]:
    states_by_index = {s["index"]: s for s in ground_truth["states"]}
    reps = result.representative_timestamps

    transition_coverage = []
    for transition in ground_truth["transitions"]:
        before_idx, after_idx = transition["between_states"]
        bracketed = _transition_is_bracketed(
            reps, states_by_index[before_idx], states_by_index[after_idx]
        )
        transition_coverage.append(
            {
                "transition_index": transition["index"],
                "between_states": transition["between_states"],
                "window": transition["window"],
                "bracketed": bracketed,
            }
        )

    recall = sum(1 for t in transition_coverage if t["bracketed"])
    total = len(transition_coverage)
    within_hard_cap = result.representative_count <= _HARD_MAX_REPRESENTATIVES
    within_ideal_band = (
        _IDEAL_MIN_REPRESENTATIVES <= result.representative_count <= _IDEAL_MAX_REPRESENTATIVES
    )
    passed = (recall == total) and within_hard_cap

    return {
        "sampling_fps": result.sampling_fps,
        "representative_count": result.representative_count,
        "blank_group_count": result.blank_group_count,
        "sampled_frame_count": result.sampled_frame_count,
        "decoded_frame_count": result.decoded_frame_count,
        "max_representative_gap_seconds": round(result.max_representative_gap_seconds, 3),
        "elapsed_wall_seconds": round(result.elapsed_wall_seconds, 3),
        "transition_recall": f"{recall}/{total}",
        "transition_coverage": transition_coverage,
        "within_hard_cap_20": within_hard_cap,
        "within_ideal_band_8_to_15": within_ideal_band,
        "PASS": passed,
    }


def run() -> dict[str, Any] | None:
    if not _VIDEO_PATH.exists() or not _GROUND_TRUTH_PATH.exists():
        print(
            "M11 Alpha Dry-Run skipped: private sample_d.mp4 / "
            "sample_d_alpha_window_ground_truth.json not present on this "
            "machine. This script is safe to run without them; it simply "
            "does nothing."
        )
        return None

    ground_truth = json.loads(_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    roi = ROI(*ground_truth["roi"])
    processing_range = ProcessingRange(
        start_time=ground_truth["window_start_seconds"],
        end_time=ground_truth["window_end_seconds"],
    )

    profile_reports = []
    for fps in _SAMPLING_PROFILES_FPS:
        result = run_alpha_visual_dry_run(_VIDEO_PATH, processing_range, roi, sampling_fps=fps)
        report = _evaluate_profile(result, ground_truth)
        profile_reports.append(report)

        print(f"\n=== Profile: {fps:.0f} fps ===")
        print(result.format_report())
        print(f"Transition recall:          {report['transition_recall']}")
        print(f"Within hard cap (<=20):      {report['within_hard_cap_20']}")
        print(f"Within ideal band (8-15):    {report['within_ideal_band_8_to_15']}")
        print(f"PASS:                        {report['PASS']}")

    overall_pass = any(r["PASS"] for r in profile_reports)
    print(f"\n=== Overall: {'PASS' if overall_pass else 'FAIL'} ===")

    return {"profiles": profile_reports, "overall_pass": overall_pass}


if __name__ == "__main__":
    run()
