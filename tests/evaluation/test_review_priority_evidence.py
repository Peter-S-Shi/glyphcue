"""Milestone 10 Review Priority failure-class evidence closure.

Classifies a real, unmodified `ReviewPriority` (M7's production
`compute_review_priority` output -- no algorithm change, no re-tuned
threshold) by WHICH component(s) actually fired, so the M10 evaluation
can report what kind of evidence the heuristic did or didn't have for a
Cue that turned out wrong -- not just whether it beat a random baseline
overall.
"""

from glyphcue.application.review_priority import ReviewPriority, ReviewPriorityComponent
from glyphcue.evaluation.review_priority_evidence import classify_review_priority_failure


def _priority(*component_names: str) -> ReviewPriority:
    return ReviewPriority(
        cue_id="cue-1",
        score=0.5 if component_names else 0.0,
        level="Medium" if component_names else "None",
        components=tuple(
            ReviewPriorityComponent(name=name, contribution=0.5, explanation="test")
            for name in component_names
        ),
    )


def test_classify_review_priority_failure_with_no_components_is_no_signal():
    assert classify_review_priority_failure(_priority()) == "no_signal"


def test_classify_review_priority_failure_with_only_confidence_component():
    assert classify_review_priority_failure(_priority("ocr_confidence")) == "low_confidence_only"


def test_classify_review_priority_failure_with_only_non_confidence_component():
    assert (
        classify_review_priority_failure(_priority("cross_frame_disagreement"))
        == "other_signal_only"
    )


def test_classify_review_priority_failure_with_both_kinds_of_component():
    assert (
        classify_review_priority_failure(_priority("ocr_confidence", "cross_frame_disagreement"))
        == "low_confidence_and_other_signal"
    )
