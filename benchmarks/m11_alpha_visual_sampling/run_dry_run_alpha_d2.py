"""M11 Research Gate -- Alpha-D2 (centered/non-causal) corrective runner.

Same private fixture, same three fixed sampling profiles, same
evaluation harness as `run_dry_run_alpha_d.py` -- only the persistence
evidence source changes, from `alpha_d_stable_dry_run` (causal trailing
window) to `alpha_d2_centered_dry_run` (centered window, same horizon).

Prints Alpha-D vs. Alpha-D2 group-level diffs so the "did this actually
remove the onset artifact, or did it cheat by merging real states"
question in the M11 Alpha-D2 prompt is answered directly from one run.

Run manually (requires the private corpus):
    python -m benchmarks.m11_alpha_visual_sampling.run_dry_run_alpha_d2
"""

from __future__ import annotations

import json
from typing import Any

from glyphcue.application.alpha_d2_centered_dry_run import run_alpha_d2_centered_dry_run
from glyphcue.application.alpha_d_stable_dry_run import run_alpha_d_stable_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

from benchmarks.m11_alpha_visual_sampling.run_dry_run import (
    _GROUND_TRUTH_PATH,
    _SAMPLING_PROFILES_FPS,
    _VIDEO_PATH,
    _evaluate_profile,
)


def run() -> dict[str, Any] | None:
    if not _VIDEO_PATH.exists() or not _GROUND_TRUTH_PATH.exists():
        print(
            "M11 Alpha-D2 Dry Run skipped: private sample_d.mp4 / "
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
        alpha_d_result = run_alpha_d_stable_dry_run(_VIDEO_PATH, processing_range, roi, sampling_fps=fps)
        alpha_d2_result = run_alpha_d2_centered_dry_run(
            _VIDEO_PATH, processing_range, roi, sampling_fps=fps
        )
        report = _evaluate_profile(alpha_d2_result, ground_truth)
        report["alpha_d_representative_count"] = alpha_d_result.representative_count
        report["reduction_vs_alpha_d"] = (
            alpha_d_result.representative_count - alpha_d2_result.representative_count
        )

        alpha_d_reps = set(round(t, 2) for t in alpha_d_result.representative_timestamps)
        alpha_d2_reps = set(round(t, 2) for t in alpha_d2_result.representative_timestamps)
        removed = sorted(alpha_d_reps - alpha_d2_reps)
        added = sorted(alpha_d2_reps - alpha_d_reps)
        report["representatives_removed_vs_alpha_d"] = removed
        report["representatives_added_vs_alpha_d"] = added

        profile_reports.append(report)

        print(f"\n=== Profile: {fps:.0f} fps ===")
        print(alpha_d2_result.format_report())
        print(f"Alpha-D representatives:  {alpha_d_result.representative_count}")
        print(f"Alpha-D2 representatives: {alpha_d2_result.representative_count}")
        print(f"Reduction vs Alpha-D:     {report['reduction_vs_alpha_d']}")
        print(f"Removed timestamps:       {removed}")
        print(f"Added timestamps:         {added}")
        print(f"Transition recall:          {report['transition_recall']}")
        print(f"Within hard cap (<=20):      {report['within_hard_cap_20']}")
        print(f"Within ideal band (8-15):    {report['within_ideal_band_8_to_15']}")
        print(f"PASS:                        {report['PASS']}")

    overall_pass = any(r["PASS"] for r in profile_reports)
    print(f"\n=== Overall: {'PASS' if overall_pass else 'FAIL'} ===")

    return {"profiles": profile_reports, "overall_pass": overall_pass}


if __name__ == "__main__":
    run()
