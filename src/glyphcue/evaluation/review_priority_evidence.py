"""Milestone 10 Review Priority failure-class evidence.

Classifies a real, unmodified `ReviewPriority` (M7's production
`compute_review_priority`) by which component(s) fired -- not a
re-derivation of the underlying signals or thresholds, which would risk
silently drifting from `compute_review_priority`'s own logic. This
answers "what kind of evidence did the heuristic have, if any" for a
Cue, independent of whether that Cue turned out right or wrong; the
caller (an evaluation script with real ground truth) combines this with
`is_error` to report what the heuristic is actually good at catching
and what it structurally cannot see.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glyphcue.application.review_priority import ReviewPriority

_CONFIDENCE_COMPONENT = "ocr_confidence"


def classify_review_priority_failure(priority: "ReviewPriority") -> str:
    component_names = {component.name for component in priority.components}
    if not component_names:
        return "no_signal"
    has_confidence = _CONFIDENCE_COMPONENT in component_names
    has_other = bool(component_names - {_CONFIDENCE_COMPONENT})
    if has_confidence and has_other:
        return "low_confidence_and_other_signal"
    if has_confidence:
        return "low_confidence_only"
    return "other_signal_only"
