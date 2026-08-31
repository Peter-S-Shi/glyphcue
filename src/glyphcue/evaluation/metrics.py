"""Milestone 10 shared evaluation metrics.

`character_error_rate` is the canonical implementation, promoted here
from `benchmarks/ocr_runtime_selection/cer.py` (formerly duplicated via
`sys.path` imports by `benchmarks/multi_frame_consensus/run_evaluation.py`
and `benchmarks/multilingual_reconstruction/run_evaluation.py`) so every
M3-M10 evaluation script shares one real, importable implementation
instead of each reaching for its own copy.
"""

from __future__ import annotations

from collections.abc import Sequence


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous_row = list(range(len(hypothesis) + 1))
    for i, ref_token in enumerate(reference, start=1):
        current_row = [i]
        for j, hyp_token in enumerate(hypothesis, start=1):
            cost = 0 if ref_token == hyp_token else 1
            current_row.append(
                min(
                    previous_row[j] + 1,  # deletion
                    current_row[j - 1] + 1,  # insertion
                    previous_row[j - 1] + cost,  # substitution
                )
            )
        previous_row = current_row
    return previous_row[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein edit distance / len(reference), at character granularity."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return _edit_distance(list(reference), list(hypothesis)) / len(reference)


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Levenshtein edit distance / word count of reference, at
    whitespace-tokenized word granularity. Meaningful for space-delimited
    text (e.g. English); not meaningful for CJK, where CER is used
    instead (ROADMAP.md section 17)."""
    reference_tokens = reference.split()
    hypothesis_tokens = hypothesis.split()
    if not reference_tokens:
        return 0.0 if not hypothesis_tokens else 1.0
    return _edit_distance(reference_tokens, hypothesis_tokens) / len(reference_tokens)


def _spans_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    a_start, a_end = a
    b_start, b_end = b
    return a_start < b_end and b_start < a_end


def cue_recovery_precision_recall(
    predicted_spans: Sequence[tuple[float, float]],
    ground_truth_spans: Sequence[tuple[float, float]],
) -> tuple[float, float]:
    """Cue-level (not text-level) recovery: did a predicted Cue's time
    span land where a real Cue was, and was every real Cue caught by
    some predicted Cue? A ground-truth span counts as recovered if ANY
    predicted span overlaps it; a predicted span counts as correct if
    it overlaps ANY ground-truth span (existence-based, not a strict
    one-to-one match -- text accuracy of a matched Cue is CER/WER's
    job, not this metric's)."""
    precision = (
        sum(
            1
            for predicted in predicted_spans
            if any(_spans_overlap(predicted, truth) for truth in ground_truth_spans)
        )
        / len(predicted_spans)
        if predicted_spans
        else 0.0
    )
    recall = (
        sum(
            1
            for truth in ground_truth_spans
            if any(_spans_overlap(truth, predicted) for predicted in predicted_spans)
        )
        / len(ground_truth_spans)
        if ground_truth_spans
        else 0.0
    )
    return precision, recall


def timing_error(
    predicted_spans: Sequence[tuple[float, float]],
    ground_truth_spans: Sequence[tuple[float, float]],
) -> tuple[float, float]:
    """Mean absolute start/end offset, in seconds, over ground-truth
    spans that have at least one overlapping predicted span (matched by
    greatest overlap). A ground-truth span with no overlapping predicted
    span is a Cue-recovery miss, not a timing error, and is excluded --
    see `cue_recovery_precision_recall` for recall on those."""
    start_errors: list[float] = []
    end_errors: list[float] = []
    for truth_start, truth_end in ground_truth_spans:
        best_match = max(
            (predicted for predicted in predicted_spans if _spans_overlap(predicted, (truth_start, truth_end))),
            key=lambda predicted: min(predicted[1], truth_end) - max(predicted[0], truth_start),
            default=None,
        )
        if best_match is None:
            continue
        predicted_start, predicted_end = best_match
        start_errors.append(abs(predicted_start - truth_start))
        end_errors.append(abs(predicted_end - truth_end))

    mean_start_error = sum(start_errors) / len(start_errors) if start_errors else 0.0
    mean_end_error = sum(end_errors) / len(end_errors) if end_errors else 0.0
    return mean_start_error, mean_end_error


_WRONG_ASSIGNMENT_CER_THRESHOLD = 0.2


def multilingual_layer_assignment_errors(
    ground_truth_by_language: dict[str, str],
    recovered_by_language: dict[str, str],
) -> dict[str, list[str]]:
    """For each expected language whose own layer wasn't recovered,
    distinguishes a true miss from a wrong-layer assignment: if that
    language's ground-truth text is a near-exact match (low CER) for
    text recovered under a DIFFERENT language's key, the text was
    produced but tagged with the wrong language layer, not lost."""
    missing: list[str] = []
    wrong_assignment: list[str] = []
    for language, truth_text in ground_truth_by_language.items():
        recovered_text = recovered_by_language.get(language)
        if recovered_text:
            continue
        found_under_other_layer = any(
            other_language != language
            and character_error_rate(truth_text, other_text) < _WRONG_ASSIGNMENT_CER_THRESHOLD
            for other_language, other_text in recovered_by_language.items()
        )
        if found_under_other_layer:
            wrong_assignment.append(language)
        else:
            missing.append(language)
    return {"missing": missing, "wrong_assignment": wrong_assignment}


def recall_at_top_fraction(
    ranked_ids: Sequence[str], target_ids: set[str] | frozenset[str], fraction: float
) -> float:
    """Of `target_ids`, the fraction that fall within the top
    `fraction` of `ranked_ids` (e.g. the top 20% of Cues by Review
    Priority score). Generic over what `target_ids` means -- the same
    Cues overall, or one observed failure class among them."""
    if not target_ids:
        return 0.0
    top_n = max(1, round(len(ranked_ids) * fraction))
    reviewed = set(ranked_ids[:top_n])
    return len(reviewed & target_ids) / len(target_ids)


def group_pass_fail_by_tag(results: Sequence[tuple[str, bool]]) -> dict[str, dict[str, int]]:
    """Groups (tag, passed) pairs into independent per-tag pass/fail
    counts. One case can contribute to more than one tag (e.g. a fixture
    that is evidence for both segmentation and timing normalization) --
    each pair is counted under its own tag, not forced into a single
    bucket."""
    counts: dict[str, dict[str, int]] = {}
    for tag, passed in results:
        bucket = counts.setdefault(tag, {"pass": 0, "fail": 0})
        bucket["pass" if passed else "fail"] += 1
    return counts
