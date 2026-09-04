"""M11 Research Gate -- Generalization Gate.

Runs the FROZEN Alpha-D2 5 fps candidate (commit 8ebd856) -- no
threshold, no fps, no fixture-specific change -- against short windows
from the existing private real-video corpus that are deliberately
DIFFERENT in style from the sample_d window Alpha/Alpha-D/Alpha-D2 were
all developed against: monolingual vs. bilingual, different caption
font/weight, different background motion (hand/pen gesture vs. talking
head vs. hands-up gesture), presence/absence of real blank gaps.

Tracked; the corpus manifest, videos, and
`generalization_gate_ground_truth.json` are NOT (gitignored, see
`private_samples/`). Safe no-op if absent.

Evaluation uses a fixed, pre-declared time tolerance
(`ground_truth["tolerance_seconds"]`) applied uniformly to every
fixture's state windows AT CHECK TIME -- the stored ground-truth numbers
are never edited, only the comparison is widened by a constant declared
before any run in this script, so a near-boundary representative isn't
misread as a miss the way the zero-margin Alpha-D2 8 fps evaluation was.

Run manually (requires the private corpus):
    python -m benchmarks.m11_alpha_visual_sampling.run_generalization_gate
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from glyphcue.application.alpha_d2_centered_dry_run import run_alpha_d2_centered_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

_CORPUS_DIR = Path(__file__).resolve().parents[2] / "private_samples" / "m10_video_corpus"
_GROUND_TRUTH_PATH = _CORPUS_DIR / "generalization_gate_ground_truth.json"

_FROZEN_SAMPLING_FPS = 5.0


def _rep_in_window(reps: list[float], start: float, end: float, tolerance: float) -> bool:
    return any((start - tolerance) <= t <= (end + tolerance) for t in reps)


def _fragmentation_ratio(representative_count: int, real_state_count: int) -> float:
    """>1 means the algorithm split real states into more groups than
    truth has; ~1 is ideal; <1 would mean it under-split (impossible
    here without also failing recall)."""
    if real_state_count == 0:
        return 0.0
    return representative_count / real_state_count


def _check_no_cross_state_merges(groups, states, tolerance: float) -> list[str]:
    """A "merge" is a single subtitle group whose span reaches from
    inside one real state's window into inside a DIFFERENT, non-adjacent
    real state's window, i.e. it silently swallowed an entire
    intervening state. Returns a list of human-readable violations
    (empty = clean)."""
    violations = []
    for group in groups:
        if group.state_kind != "subtitle":
            continue
        containing = [
            s["index"]
            for s in states
            if (s["start_seconds"] - tolerance) <= group.start_timestamp
            and group.start_timestamp <= (s["end_seconds"] + tolerance)
        ]
        containing_end = [
            s["index"]
            for s in states
            if (s["start_seconds"] - tolerance) <= group.end_timestamp
            and group.end_timestamp <= (s["end_seconds"] + tolerance)
        ]
        if containing and containing_end:
            start_idx, end_idx = min(containing), max(containing_end)
            if end_idx - start_idx >= 2:
                violations.append(
                    f"group [{group.start_timestamp:.2f},{group.end_timestamp:.2f}] spans "
                    f"real states {start_idx}..{end_idx} (skips at least one whole state)"
                )
    return violations


def _evaluate_fixture(fixture: dict, tolerance: float) -> dict[str, Any]:
    video_path = _CORPUS_DIR / fixture["video_path"]
    roi = ROI(*fixture["roi"])
    processing_range = ProcessingRange(
        start_time=fixture["window_start_seconds"], end_time=fixture["window_end_seconds"]
    )

    result = run_alpha_d2_centered_dry_run(
        video_path, processing_range, roi, sampling_fps=_FROZEN_SAMPLING_FPS
    )
    reps = result.representative_timestamps
    states = fixture["states"]

    transitions = []
    for a, b in zip(states, states[1:]):
        bracketed = _rep_in_window(
            reps, a["start_seconds"], a["end_seconds"], tolerance
        ) and _rep_in_window(reps, b["start_seconds"], b["end_seconds"], tolerance)
        transitions.append(
            {"between_states": [a["index"], b["index"]], "bracketed": bracketed}
        )

    recall = sum(1 for t in transitions if t["bracketed"])
    total = len(transitions)
    merge_violations = _check_no_cross_state_merges(result.groups, states, tolerance)

    return {
        "fixture_id": fixture["id"],
        "style_note": fixture["style_note"],
        "real_state_count": len(states),
        "real_transition_count": total,
        "representative_count": result.representative_count,
        "blank_group_count": result.blank_group_count,
        "fragmentation_ratio": round(
            _fragmentation_ratio(result.representative_count, len(states)), 2
        ),
        "transition_recall": f"{recall}/{total}",
        "transitions": transitions,
        "cross_state_merge_violations": merge_violations,
        "PASS": (recall == total) and not merge_violations,
    }


def run() -> dict[str, Any] | None:
    if not _GROUND_TRUTH_PATH.exists():
        print(
            "M11 Generalization Gate skipped: private "
            "generalization_gate_ground_truth.json (or the videos it "
            "references) not present on this machine. Safe to run "
            "without them; it simply does nothing."
        )
        return None

    ground_truth = json.loads(_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    tolerance = ground_truth["tolerance_seconds"]

    fixture_reports = []
    for fixture in ground_truth["fixtures"]:
        video_path = _CORPUS_DIR / fixture["video_path"]
        if not video_path.exists():
            print(f"Skipping {fixture['id']}: {video_path.name} not present.")
            continue
        report = _evaluate_fixture(fixture, tolerance)
        fixture_reports.append(report)

        print(f"\n=== Fixture: {report['fixture_id']} ===")
        print(f"Style: {report['style_note']}")
        print(f"Real states / transitions:  {report['real_state_count']} / {report['real_transition_count']}")
        print(f"Representatives:             {report['representative_count']}")
        print(f"Blank groups:                {report['blank_group_count']}")
        print(f"Fragmentation ratio:         {report['fragmentation_ratio']}")
        print(f"Transition recall:          {report['transition_recall']}")
        print(f"Cross-state merges:          {report['cross_state_merge_violations'] or 'none'}")
        print(f"PASS:                        {report['PASS']}")

    overall_pass = bool(fixture_reports) and all(r["PASS"] for r in fixture_reports)
    print(f"\n=== Generalization Gate: {'PASS' if overall_pass else 'FAIL'} ===")

    return {"fixtures": fixture_reports, "overall_pass": overall_pass}


if __name__ == "__main__":
    run()
