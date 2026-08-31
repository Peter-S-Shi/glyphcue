"""Locks the M8 Path B normalization evaluation's own reported counts to
the corpus it actually runs -- a regression for the specific drift this
was corrected for: the evaluation script's docstring/PR narrative
claimed 17 cases / English rolling 5/5 while the actual `_CASES` corpus
only produced 16. This test fails loudly if that gap reopens (e.g. a
case added to the fixture matrix but not mirrored into the evaluation
corpus, or vice versa).
"""

from benchmarks.path_b_normalization.run_evaluation import _CASES, run


def test_evaluation_totals_match_the_stated_17_cases_all_passing():
    results = run()

    assert results["total_cases"] == 17
    assert results["total_pass"] == 17
    assert results["total_fail"] == 0
    assert results["failures"] == []


def test_english_rolling_reconstruction_category_is_five_of_five():
    english_rolling_cases = [
        case for case in _CASES if case.category == "rolling_reconstruction" and case.language == "en"
    ]
    assert len(english_rolling_cases) == 5

    results = run()
    # per_category aggregates both languages; cross-check specifically
    # that none of the 5 English rolling cases are among the failures.
    failed_case_names = {failure["case"] for failure in results["failures"]}
    assert not failed_case_names.intersection({case.name for case in english_rolling_cases})


def test_irregular_timing_span_case_verifies_the_real_merged_span():
    # A regression for the evaluation itself: text/flag assertions alone
    # cannot catch a timing-normalization bug (e.g. Cue.end_time
    # silently reverting to "last Observation's end" instead of the
    # latest end across all supporting evidence) -- this case must
    # actually check the real (start_time, end_time), not just text.
    case = next(c for c in _CASES if c.name == "english_irregular_timing_span_covers_latest_end")
    assert case.expected_spans == ((0.0, 5.0),)
