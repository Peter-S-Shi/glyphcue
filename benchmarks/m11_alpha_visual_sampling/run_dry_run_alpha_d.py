"""M11 Research Gate -- Alpha-D corrective experiment runner.

Same private fixture, same three fixed sampling profiles (5/8/10 fps,
no continuous parameter search), same evaluation harness
(`_evaluate_profile` / ground-truth bracket check) as
`run_dry_run.py` (the Alpha baseline, commit 973157b) -- only the
signature under test changes, from `alpha_visual_dry_run` (raw
whole-ROI edge mask) to `alpha_d_stable_dry_run` (edge + temporal
persistence + connected-component size filtering).

Prints both the Alpha-D numbers AND a direct before/after comparison
against Alpha at the same profiles, so the "how much did this actually
filter" question in the M11 Alpha-D corrective prompt is answered from
one run, not left to a human diffing two JSON files.

Run manually (requires the private corpus):
    python -m benchmarks.m11_alpha_visual_sampling.run_dry_run_alpha_d
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from glyphcue.application.alpha_d_stable_dry_run import run_alpha_d_stable_dry_run
from glyphcue.application.alpha_visual_dry_run import run_alpha_visual_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

from benchmarks.m11_alpha_visual_sampling.run_dry_run import (
    _CORPUS_DIR,
    _GROUND_TRUTH_PATH,
    _SAMPLING_PROFILES_FPS,
    _VIDEO_PATH,
    _evaluate_profile,
)

_ = _CORPUS_DIR  # re-exported path constants, kept for readability at call sites


def run() -> dict[str, Any] | None:
    if not _VIDEO_PATH.exists() or not _GROUND_TRUTH_PATH.exists():
        print(
            "M11 Alpha-D Dry Run skipped: private sample_d.mp4 / "
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
        alpha_result = run_alpha_visual_dry_run(_VIDEO_PATH, processing_range, roi, sampling_fps=fps)
        alpha_d_result = run_alpha_d_stable_dry_run(
            _VIDEO_PATH, processing_range, roi, sampling_fps=fps
        )
        report = _evaluate_profile(alpha_d_result, ground_truth)
        report["alpha_baseline_representative_count"] = alpha_result.representative_count
        report["reduction_vs_alpha"] = (
            alpha_result.representative_count - alpha_d_result.representative_count
        )
        profile_reports.append(report)

        print(f"\n=== Profile: {fps:.0f} fps ===")
        print(alpha_d_result.format_report())
        print(f"Alpha (baseline) representatives: {alpha_result.representative_count}")
        print(f"Alpha-D representatives:           {alpha_d_result.representative_count}")
        print(f"Reduction:                         {report['reduction_vs_alpha']}")
        print(f"Transition recall:          {report['transition_recall']}")
        print(f"Within hard cap (<=20):      {report['within_hard_cap_20']}")
        print(f"Within ideal band (8-15):    {report['within_ideal_band_8_to_15']}")
        print(f"PASS:                        {report['PASS']}")

    overall_pass = any(r["PASS"] for r in profile_reports)
    print(f"\n=== Overall: {'PASS' if overall_pass else 'FAIL'} ===")

    return {"profiles": profile_reports, "overall_pass": overall_pass}


if __name__ == "__main__":
    run()
