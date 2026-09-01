"""Milestone 8 Path B normalization evaluation.

Ground truth for every case here is defined independently of
`reconstruct_cues_with_diagnostics`'s own output -- each case states, by
hand, what the correct reconstructed Cue text/count and diagnostic
classification SHOULD be, before the real production function is ever
called. This mirrors the fixture matrix in
`tests/application/test_path_b_diagnostics.py` (a superset of it is used
as the evaluation corpus here) but reports results as a reproducible,
categorized artifact -- not just "tests passed" -- broken out by
language (English / CJK) and failure class, per ROADMAP M8's evaluation
requirement.

Two failure classes are reported SEPARATELY on purpose, per a corrective
pass over this evaluation's first draft: "out-of-order source" (a
diagnosis-not-silently-discarded case, exercised at the
`reconstruct_cues_with_diagnostics` level on hand-built Observations)
and "malformed/recoverable import" (a real, distinct per-EVENT parser
defensive seam, exercised at the `Pysubs2SubtitleFormatAdapter` level
through real file I/O -- a domain-invalid event, e.g. inverted timing,
must not take down the whole file). The first draft's "malformed_safe"
category only ever covered the first of these and should not have
implied it covered general malformed-input robustness; this version
names and measures both explicitly.

All fixture text is hand-authored, synthetic, and copyright-safe -- no
scraped subtitle/transcript data.

Milestone 10 addition (same corpus, same `reconstruct_cues_with_diagnostics`,
no algorithm change): each case is hand-tagged with which of ROADMAP.md
section 17's three named Path B metrics (duplicate_removal / segmentation
/ timing_normalization) it is real evidence for, reported independently
under `roadmap_metrics` -- e.g. a case can be evidence for segmentation
without being evidence for duplicate-removal correctness, instead of one
blended per_category pass rate standing in for all three. Cases that are
evidence for none of the three (e.g. malformed-import recovery) are left
untagged rather than forced into an ill-fitting bucket.

Run manually:
    python -m benchmarks.path_b_normalization.run_evaluation
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from glyphcue.adapters.pysubs2_subtitle_io import Pysubs2SubtitleFormatAdapter
from glyphcue.application.reconstruction import reconstruct_cues_with_diagnostics
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.evaluation.metrics import group_pass_fail_by_tag, timing_error

_RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"
_PROVENANCE = Provenance(kind=ProvenanceKind.SUBTITLE_IMPORT, source="evaluation-fixture")


def _obs(id_: str, text: str, start: float, end: float, language: str | None = None) -> Observation:
    return Observation(id=id_, text=text, start_time=start, end_time=end, provenance=_PROVENANCE, language=language)


@dataclass(frozen=True)
class Case:
    name: str
    category: str
    language: str  # en | cjk | n/a
    observations: list[Observation]
    expected_texts: list[str]
    # Diagnostic flags that must be True on AT LEAST ONE resulting Cue,
    # for cases where the correct behavior is a specific named
    # classification (e.g. this case exists to prove
    # segmentation_ambiguous fires, not just that text matches).
    required_flags: tuple[str, ...] = ()
    # Diagnostic flags that must be False on every resulting Cue -- for
    # cases that exist specifically to prove a DANGEROUS false-positive
    # merge does NOT happen (the over-merge-guard category's whole
    # point).
    forbidden_flags: tuple[str, ...] = ()
    # Optional expected (start_time, end_time) per resulting Cue, in
    # order -- checked only when provided. Text/flag assertions alone
    # cannot catch a timing-normalization regression (e.g. a Cue span
    # silently reverting to "last Observation's end" instead of the
    # latest end across all supporting evidence); this lets a case
    # assert the real span without requiring every case to.
    expected_spans: tuple[tuple[float, float], ...] | None = None
    # Which of ROADMAP.md section 17's named Path B metrics
    # (duplicate_removal / segmentation / timing_normalization) this
    # case is real evidence for -- hand-assigned per case, not inferred
    # from category/flags, so a case only counts toward a metric it
    # actually exercises. A case with no applicable metric (e.g.
    # malformed-import recovery, which is neither of the three) is
    # simply not tagged, per M10's "don't force a number everywhere."
    roadmap_metrics: tuple[str, ...] = ()


_CASES: list[Case] = [
    # -- Clean preservation ---------------------------------------------------
    Case(
        name="clean_english_two_cues",
        category="clean_preservation",
        language="en",
        observations=[
            _obs("o1", "First complete sentence.", 0.0, 2.0),
            _obs("o2", "Second complete sentence.", 2.1, 4.0),
        ],
        expected_texts=["First complete sentence.", "Second complete sentence."],
        expected_spans=((0.0, 2.0), (2.1, 4.0)),
        roadmap_metrics=("segmentation", "timing_normalization"),
    ),
    Case(
        name="clean_cjk_two_cues",
        category="clean_preservation",
        language="cjk",
        observations=[
            _obs("o1", "第一句話。", 0.0, 2.0, language="zh"),
            _obs("o2", "第二句話。", 2.1, 4.0, language="zh"),
        ],
        expected_texts=["第一句話。", "第二句話。"],
        expected_spans=((0.0, 2.0), (2.1, 4.0)),
        roadmap_metrics=("segmentation", "timing_normalization"),
    ),
    # -- Rolling reconstruction (real temporal evidence) -----------------------
    Case(
        name="english_growing_window",
        category="rolling_reconstruction",
        language="en",
        observations=[
            _obs("o1", "Hello", 0.0, 2.0),
            _obs("o2", "Hello world", 1.0, 4.0),
            _obs("o3", "Hello world, how are you", 3.0, 6.0),
        ],
        expected_texts=["Hello world, how are you"],
        required_flags=("rolling_growth",),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="cjk_growing_window",
        category="rolling_reconstruction",
        language="cjk",
        observations=[
            _obs("o1", "こんにちは", 0.0, 2.0, language="ja"),
            _obs("o2", "こんにちは世界", 1.0, 4.0, language="ja"),
            _obs("o3", "こんにちは世界、ようこそ", 3.0, 6.0, language="ja"),
        ],
        expected_texts=["こんにちは世界、ようこそ"],
        required_flags=("rolling_growth",),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="cjk_single_character_whole_prefix_growth",
        category="rolling_reconstruction",
        language="cjk",
        observations=[
            _obs("o1", "你", 0.0, 2.0, language="zh"),
            _obs("o2", "你好，世界", 1.0, 4.0, language="zh"),
        ],
        expected_texts=["你好，世界"],
        required_flags=("rolling_growth",),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="english_sliding_overlap",
        category="rolling_reconstruction",
        language="en",
        observations=[
            _obs("o1", "the quick brown fox", 0.0, 2.0),
            _obs("o2", "brown fox jumps over", 1.5, 4.0),
            _obs("o3", "jumps over the lazy dog", 3.5, 6.0),
        ],
        expected_texts=["the quick brown fox jumps over the lazy dog"],
        required_flags=("sliding_overlap",),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="cjk_sliding_overlap",
        category="rolling_reconstruction",
        language="cjk",
        observations=[
            _obs("o1", "今日は天気が良い", 0.0, 2.0, language="ja"),
            _obs("o2", "天気が良いので散歩する", 1.5, 4.0, language="ja"),
        ],
        expected_texts=["今日は天気が良いので散歩する"],
        required_flags=("sliding_overlap",),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="english_exact_duplicate_repetition_within_bounded_gap",
        category="rolling_reconstruction",
        language="en",
        observations=[
            _obs("o1", "Hello world", 0.0, 2.0),
            _obs("o2", "Hello world", 2.1, 4.0),
        ],
        expected_texts=["Hello world"],
        required_flags=("repetition_collapsed",),
        roadmap_metrics=("duplicate_removal",),
    ),
    Case(
        name="english_backtrack_pure_suffix_repetition_within_bounded_gap",
        category="rolling_reconstruction",
        language="en",
        observations=[
            _obs("o1", "Hello world, how are you", 0.0, 2.0),
            _obs("o2", "how are you", 2.1, 4.0),  # repeats the tail, adds nothing new
        ],
        expected_texts=["Hello world, how are you"],
        required_flags=("repetition_collapsed",),
        roadmap_metrics=("duplicate_removal",),
    ),
    Case(
        name="english_irregular_timing_span_covers_latest_end",
        category="rolling_reconstruction",
        language="en",
        observations=[
            _obs("o1", "Hello", 0.0, 5.0),  # starts first, ends LATEST
            _obs("o2", "Hello world", 1.0, 3.0),  # starts later, ends earlier
        ],
        expected_texts=["Hello world"],
        required_flags=("rolling_growth",),
        expected_spans=((0.0, 5.0),),
        roadmap_metrics=("segmentation", "timing_normalization"),
    ),
    # -- Over-merge guard: must NOT merge, no matter how strong the text match --
    Case(
        name="english_over_merge_guard_single_char_coincidence",
        category="over_merge_guard",
        language="en",
        observations=[
            _obs("o1", "Thanks a lot", 0.0, 2.0),
            _obs("o2", "totally different topic", 1.5, 4.0),
        ],
        expected_texts=["Thanks a lot", "totally different topic"],
        required_flags=("segmentation_ambiguous",),
        forbidden_flags=("rolling_growth", "sliding_overlap"),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="cjk_over_merge_guard_single_char_coincidence",
        category="over_merge_guard",
        language="cjk",
        observations=[
            _obs("o1", "今日は天気が良", 0.0, 2.0, language="ja"),
            _obs("o2", "良かったね、また明日", 1.5, 4.0, language="ja"),
        ],
        expected_texts=["今日は天気が良", "良かったね、また明日"],
        required_flags=("segmentation_ambiguous",),
        forbidden_flags=("rolling_growth", "sliding_overlap"),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="english_over_merge_guard_unrelated_overlapping_speakers",
        category="over_merge_guard",
        language="en",
        observations=[
            _obs("o1", "Speaker A says something long", 0.0, 5.0),
            _obs("o2", "Speaker B interjects briefly", 1.0, 3.0),
        ],
        expected_texts=["Speaker A says something long", "Speaker B interjects briefly"],
        required_flags=("timing_collision",),
        forbidden_flags=("rolling_growth", "sliding_overlap", "repetition_collapsed"),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="english_over_merge_guard_far_distant_identical_captions",
        category="over_merge_guard",
        language="en",
        observations=[
            _obs("o1", "Thank you for watching", 0.0, 2.0),
            _obs("o2", "Thank you for watching", 120.0, 122.0),
        ],
        expected_texts=["Thank you for watching", "Thank you for watching"],
        forbidden_flags=("rolling_growth", "sliding_overlap", "repetition_collapsed"),
        roadmap_metrics=("segmentation",),
    ),
    Case(
        name="english_over_merge_guard_non_overlapping_coincidental_boundary",
        category="over_merge_guard",
        language="en",
        observations=[
            _obs("o1", "It was a bright cold day", 0.0, 2.0),
            _obs("o2", "day after day it rained", 2.5, 4.0),
        ],
        expected_texts=["It was a bright cold day", "day after day it rained"],
        forbidden_flags=("rolling_growth", "sliding_overlap", "repetition_collapsed"),
        roadmap_metrics=("segmentation",),
    ),
    # -- Out-of-order source: diagnose, don't silently discard -----------------
    Case(
        name="english_out_of_order_source",
        category="out_of_order_safe",
        language="en",
        observations=[
            _obs("o2", "Second complete sentence.", 2.1, 4.0),
            _obs("o1", "First complete sentence.", 0.0, 2.0),
        ],
        expected_texts=["First complete sentence.", "Second complete sentence."],
        required_flags=("source_order_issue",),
        roadmap_metrics=("segmentation",),
    ),
]


def _evaluate_reconstruction_cases() -> tuple[dict, dict, list[dict], list[tuple[str, bool]], list[tuple[tuple[float, float], tuple[float, float]]]]:
    per_category: dict[str, dict[str, int]] = {}
    per_language: dict[str, dict[str, int]] = {}
    failures: list[dict] = []
    # Milestone 10: ROADMAP.md section 17 names three independent Path B
    # metrics (duplicate-removal / segmentation / timing normalization).
    # Each case's hand-assigned `roadmap_metrics` tags contribute the
    # SAME overall `passed` verdict already computed above to whichever
    # metric(s) it is real evidence for -- no separate, looser pass
    # criterion invented per metric.
    roadmap_metric_results: list[tuple[str, bool]] = []
    timing_span_pairs: list[tuple[tuple[float, float], tuple[float, float]]] = []

    for case in _CASES:
        cues, diagnostics = reconstruct_cues_with_diagnostics(case.observations)
        actual_texts = [cue.language_layers[0].text for cue in cues]
        text_ok = actual_texts == case.expected_texts

        actual_spans = [(cue.start_time, cue.end_time) for cue in cues]
        spans_ok = case.expected_spans is None or actual_spans == list(case.expected_spans)

        all_flags_true = {
            flag_name for entry in diagnostics for flag_name, value in vars(entry).items() if value is True
        }
        flags_ok = all(flag in all_flags_true for flag in case.required_flags)
        forbidden_ok = not any(flag in all_flags_true for flag in case.forbidden_flags)

        passed = text_ok and spans_ok and flags_ok and forbidden_ok

        per_category.setdefault(case.category, {"pass": 0, "fail": 0})
        per_category[case.category]["pass" if passed else "fail"] += 1
        per_language.setdefault(case.language, {"pass": 0, "fail": 0})
        per_language[case.language]["pass" if passed else "fail"] += 1

        for metric in case.roadmap_metrics:
            roadmap_metric_results.append((metric, passed))
        if "timing_normalization" in case.roadmap_metrics and case.expected_spans is not None:
            timing_span_pairs.extend(zip(actual_spans, case.expected_spans))

        if not passed:
            failures.append(
                {
                    "case": case.name,
                    "category": case.category,
                    "language": case.language,
                    "expected_texts": case.expected_texts,
                    "actual_texts": actual_texts,
                    "expected_spans": list(case.expected_spans) if case.expected_spans else None,
                    "actual_spans": actual_spans,
                    "required_flags": list(case.required_flags),
                    "forbidden_flags": list(case.forbidden_flags),
                    "observed_flags": sorted(all_flags_true),
                }
            )

    return per_category, per_language, failures, roadmap_metric_results, timing_span_pairs


_MALFORMED_IMPORT_SRT = """1
00:00:00,000 --> 00:00:02,000
First valid line.

2
00:00:03,000 --> 00:00:02,500
Invalid inverted timing line.

3
00:00:04,000 --> 00:00:06,000
Second valid line.
"""


def _evaluate_malformed_recoverable_import() -> dict:
    """A distinct category from `out_of_order_safe`: a real, per-EVENT
    parser defensive seam at `Pysubs2SubtitleFormatAdapter`, exercised
    through real file I/O -- a domain-invalid event (here: inverted
    timing) must not take down the whole file, and the skipped event
    must produce an explicit, visible warning, not a silent drop."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "malformed.srt"
        path.write_text(_MALFORMED_IMPORT_SRT, encoding="utf-8")
        observations, warnings = Pysubs2SubtitleFormatAdapter().parse_with_warnings(path)

    texts = [observation.text for observation in observations]
    expected_texts = ["First valid line.", "Second valid line."]
    text_ok = texts == expected_texts
    warning_ok = len(warnings) == 1 and warnings[0].source_index == 1
    passed = text_ok and warning_ok

    return {
        "category": "malformed_recoverable_import",
        "pass": 1 if passed else 0,
        "fail": 0 if passed else 1,
        "expected_texts": expected_texts,
        "actual_texts": texts,
        "warning_count": len(warnings),
        "warning_source_indices": [warning.source_index for warning in warnings],
    }


def run() -> dict:
    per_category, per_language, failures, roadmap_metric_results, timing_span_pairs = (
        _evaluate_reconstruction_cases()
    )
    malformed_import_result = _evaluate_malformed_recoverable_import()

    per_category["malformed_recoverable_import"] = {
        "pass": malformed_import_result["pass"],
        "fail": malformed_import_result["fail"],
    }
    if malformed_import_result["fail"]:
        failures.append(malformed_import_result)

    total = len(_CASES) + 1
    total_pass = sum(bucket["pass"] for bucket in per_category.values())

    roadmap_metrics = group_pass_fail_by_tag(roadmap_metric_results)
    if timing_span_pairs:
        actual_spans, expected_spans = zip(*timing_span_pairs)
        mean_start_error, mean_end_error = timing_error(list(actual_spans), list(expected_spans))
        roadmap_metrics["timing_normalization"] = {
            **roadmap_metrics.get("timing_normalization", {"pass": 0, "fail": 0}),
            "mean_start_error_seconds": mean_start_error,
            "mean_end_error_seconds": mean_end_error,
        }

    return {
        "total_cases": total,
        "total_pass": total_pass,
        "total_fail": total - total_pass,
        "per_category": per_category,
        "per_language": per_language,
        "malformed_recoverable_import_detail": malformed_import_result,
        "failures": failures,
        "roadmap_metrics": roadmap_metrics,
        "scope_note": (
            "This corpus is the same hand-authored, ground-truth fixture "
            "matrix the implementation was built against via TDD (a "
            "superset of tests/application/test_path_b_diagnostics.py), "
            "not a held-out validation set. A 100% pass rate demonstrates "
            "these specific, deliberately adversarial edge cases (over-merge "
            "risk, irregular timing spans, CJK single-character growth vs. "
            "coincidence, malformed per-event import recovery) are each "
            "individually verified, not a claim of generalization beyond "
            "this fixture corpus."
        ),
        "roadmap_metrics_scope_note": (
            "duplicate_removal / segmentation / timing_normalization "
            "(ROADMAP.md section 17) are hand-assigned per case above -- "
            "only cases that are real evidence for a given metric "
            "contribute to it (e.g. malformed-import recovery is neither "
            "of the three and is not tagged). Each metric's pass/fail "
            "reuses the SAME overall per-case verdict already computed "
            "for per_category/per_language, not a separately invented, "
            "possibly looser criterion."
        ),
    }


if __name__ == "__main__":
    results = run()
    _RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
