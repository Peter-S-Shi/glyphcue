"""Milestone 10 shared evaluation metrics.

Every expected value here is computed independently by hand (or is a
well-known textbook example), never derived by re-running the formula
under test, per the tdd skill's rule against tautological assertions.
"""

import pytest

from glyphcue.evaluation.metrics import (
    character_error_rate,
    cue_recovery_precision_recall,
    multilingual_layer_assignment_errors,
    timing_error,
    word_error_rate,
)


def test_character_error_rate_exact_match_is_zero():
    assert character_error_rate("hello world", "hello world") == 0.0


def test_character_error_rate_one_substitution_over_reference_length():
    # "cat" -> "cot": 1 substitution, reference length 3.
    assert character_error_rate("cat", "cot") == pytest.approx(1 / 3)


def test_character_error_rate_empty_reference_and_hypothesis_is_zero():
    assert character_error_rate("", "") == 0.0


def test_character_error_rate_empty_reference_nonempty_hypothesis_is_one():
    assert character_error_rate("", "anything") == 1.0


def test_word_error_rate_exact_match_is_zero():
    assert word_error_rate("the quick brown fox", "the quick brown fox") == 0.0


def test_word_error_rate_one_word_substitution_over_reference_word_count():
    # reference has 4 words, hypothesis substitutes 1 word ("brown" -> "red").
    assert word_error_rate(
        "the quick brown fox", "the quick red fox"
    ) == pytest.approx(1 / 4)


def test_word_error_rate_empty_reference_nonempty_hypothesis_is_one():
    assert word_error_rate("", "anything at all") == 1.0


def test_cue_recovery_precision_recall_perfect_match():
    # 2 predicted spans, each overlapping exactly one of 2 ground-truth
    # spans: nothing missed, nothing spurious.
    predicted = [(0.0, 2.0), (3.0, 5.0)]
    ground_truth = [(0.0, 2.0), (3.0, 5.0)]

    precision, recall = cue_recovery_precision_recall(predicted, ground_truth)

    assert precision == 1.0
    assert recall == 1.0


def test_cue_recovery_precision_recall_one_missed_and_one_spurious():
    # Ground truth has 2 spans; only the first is recovered (predicted
    # overlaps it). The second predicted span (8-9) overlaps no ground
    # truth span at all -- a spurious detection.
    predicted = [(0.0, 2.0), (8.0, 9.0)]
    ground_truth = [(0.0, 2.0), (3.0, 5.0)]

    precision, recall = cue_recovery_precision_recall(predicted, ground_truth)

    # 1 of 2 predicted spans overlaps a real ground-truth span.
    assert precision == pytest.approx(0.5)
    # 1 of 2 ground-truth spans was recovered by some predicted span.
    assert recall == pytest.approx(0.5)


def test_timing_error_averages_absolute_start_and_end_offsets_over_matches():
    predicted = [(0.1, 2.2), (4.8, 8.3)]
    ground_truth = [(0.0, 2.0), (5.0, 8.0)]

    mean_start_error, mean_end_error = timing_error(predicted, ground_truth)

    # start offsets: |0.1-0.0|=0.1, |4.8-5.0|=0.2 -> mean 0.15
    assert mean_start_error == pytest.approx(0.15)
    # end offsets: |2.2-2.0|=0.2, |8.3-8.0|=0.3 -> mean 0.25
    assert mean_end_error == pytest.approx(0.25)


def test_timing_error_ignores_unmatched_ground_truth_spans():
    # Only the first ground-truth span has an overlapping predicted span;
    # the second (20-22) has none and must not pollute the average.
    predicted = [(0.1, 2.2)]
    ground_truth = [(0.0, 2.0), (20.0, 22.0)]

    mean_start_error, mean_end_error = timing_error(predicted, ground_truth)

    assert mean_start_error == pytest.approx(0.1)
    assert mean_end_error == pytest.approx(0.2)


def test_multilingual_layer_assignment_errors_reports_truly_missing_language():
    ground_truth_by_language = {"en": "hello world", "zh": "你好世界"}
    recovered_by_language = {"en": "hello world"}  # "zh" never recovered at all

    errors = multilingual_layer_assignment_errors(ground_truth_by_language, recovered_by_language)

    assert errors["missing"] == ["zh"]
    assert errors["wrong_assignment"] == []


def test_multilingual_layer_assignment_errors_reports_wrong_layer_assignment():
    # "ja" was never recovered under its own key, but its ground-truth
    # text shows up (near-exact) under "zh" instead -- a mis-assignment,
    # not a plain miss.
    ground_truth_by_language = {"en": "hello world", "ja": "こんにちは世界"}
    recovered_by_language = {"en": "hello world", "zh": "こんにちは世界"}

    errors = multilingual_layer_assignment_errors(ground_truth_by_language, recovered_by_language)

    assert errors["missing"] == []
    assert errors["wrong_assignment"] == ["ja"]
