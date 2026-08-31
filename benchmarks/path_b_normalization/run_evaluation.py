"""Milestone 8 Path B normalization evaluation.

Ground truth for every case here is defined independently of
`reconstruct_cues_with_diagnostics`'s own output -- each case states, by
hand, what the correct reconstructed Cue text/count and diagnostic
classification SHOULD be, before the real production function is ever
called. This mirrors the fixture matrix in
`tests/application/test_path_b_diagnostics.py` (a superset of it is used
as the evaluation corpus here) but reports results as a reproducible,
categorized artifact -- not just "tests passed" -- broken out by
language (English / CJK) and failure class (clean-preservation,
rolling-reconstruction, over-merge error, under-merge error,
malformed-safe behavior), per ROADMAP M8's evaluation requirement.

All fixture text is hand-authored, synthetic, and copyright-safe -- no
scraped subtitle/transcript data.

Run manually:
    python -m benchmarks.path_b_normalization.run_evaluation
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from glyphcue.application.reconstruction import reconstruct_cues_with_diagnostics
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind

_RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"
_PROVENANCE = Provenance(kind=ProvenanceKind.SUBTITLE_IMPORT, source="evaluation-fixture")


def _obs(id_: str, text: str, start: float, end: float, language: str | None = None) -> Observation:
    return Observation(id=id_, text=text, start_time=start, end_time=end, provenance=_PROVENANCE, language=language)


@dataclass(frozen=True)
class Case:
    name: str
    category: str  # clean_preservation | rolling_reconstruction | over_merge_guard | malformed_safe
    language: str  # en | cjk
    observations: list[Observation]
    expected_texts: list[str]
    # Diagnostic flags that must be True on AT LEAST ONE resulting Cue,
    # for cases where the correct behavior is a specific named
    # classification (e.g. this case exists to prove
    # segmentation_ambiguous fires, not just that text matches).
    required_flags: tuple[str, ...] = ()


_CASES: list[Case] = [
    Case(
        name="clean_english_two_cues",
        category="clean_preservation",
        language="en",
        observations=[
            _obs("o1", "First complete sentence.", 0.0, 2.0),
            _obs("o2", "Second complete sentence.", 2.1, 4.0),
        ],
        expected_texts=["First complete sentence.", "Second complete sentence."],
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
    ),
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
    ),
    Case(
        name="english_exact_duplicate_repetition",
        category="rolling_reconstruction",
        language="en",
        observations=[
            _obs("o1", "Hello world", 0.0, 2.0),
            _obs("o2", "Hello world", 2.1, 4.0),
        ],
        expected_texts=["Hello world"],
        required_flags=("repetition_collapsed",),
    ),
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
    ),
    Case(
        name="english_malformed_out_of_order_source",
        category="malformed_safe",
        language="en",
        observations=[
            _obs("o2", "Second complete sentence.", 2.1, 4.0),
            _obs("o1", "First complete sentence.", 0.0, 2.0),
        ],
        expected_texts=["First complete sentence.", "Second complete sentence."],
        required_flags=("source_order_issue",),
    ),
]


def run() -> dict:
    per_category: dict[str, dict[str, int]] = {}
    per_language: dict[str, dict[str, int]] = {}
    failures: list[dict] = []

    for case in _CASES:
        cues, diagnostics = reconstruct_cues_with_diagnostics(case.observations)
        actual_texts = [cue.language_layers[0].text for cue in cues]
        text_ok = actual_texts == case.expected_texts

        all_flags_true = {
            flag_name for entry in diagnostics for flag_name, value in vars(entry).items() if value is True
        }
        flags_ok = all(flag in all_flags_true for flag in case.required_flags)

        passed = text_ok and flags_ok

        per_category.setdefault(case.category, {"pass": 0, "fail": 0})
        per_category[case.category]["pass" if passed else "fail"] += 1
        per_language.setdefault(case.language, {"pass": 0, "fail": 0})
        per_language[case.language]["pass" if passed else "fail"] += 1

        if not passed:
            failures.append(
                {
                    "case": case.name,
                    "category": case.category,
                    "language": case.language,
                    "expected_texts": case.expected_texts,
                    "actual_texts": actual_texts,
                    "required_flags": list(case.required_flags),
                    "observed_flags": sorted(all_flags_true),
                }
            )

    total = len(_CASES)
    total_pass = sum(bucket["pass"] for bucket in per_category.values())

    return {
        "total_cases": total,
        "total_pass": total_pass,
        "total_fail": total - total_pass,
        "per_category": per_category,
        "per_language": per_language,
        "failures": failures,
    }


if __name__ == "__main__":
    results = run()
    _RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
