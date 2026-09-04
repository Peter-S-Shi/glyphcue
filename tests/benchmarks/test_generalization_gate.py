from glyphcue.application.visual_state_sampling import VisualStateGroup

from benchmarks.m11_alpha_visual_sampling.run_generalization_gate import (
    _check_no_cross_state_merges,
    _fragmentation_ratio,
    _rep_in_window,
)

_STATES = [
    {"index": 1, "start_seconds": 0.0, "end_seconds": 1.0},
    {"index": 2, "start_seconds": 1.2, "end_seconds": 2.0},
    {"index": 3, "start_seconds": 2.2, "end_seconds": 3.0},
]


def _group(start: float, end: float) -> VisualStateGroup:
    mid = (start + end) / 2
    return VisualStateGroup(
        state_kind="subtitle",
        start_timestamp=start,
        end_timestamp=end,
        frame_count=1,
        representative_timestamp=mid,
        representative_index=0,
    )


def test_rep_in_window_finds_a_representative_inside_the_declared_state_span():
    assert _rep_in_window([0.5], 0.0, 1.0, tolerance=0.0) is True


def test_rep_in_window_respects_a_nonzero_tolerance_past_the_boundary():
    # 1.03s is 0.03s past the declared end (1.0s) -- must be accepted
    # under a 0.08s tolerance, the exact scenario the Alpha-D2 8fps
    # boundary artifact needed a non-zero-margin check for.
    assert _rep_in_window([1.03], 0.0, 1.0, tolerance=0.08) is True


def test_rep_in_window_still_rejects_a_representative_far_outside_tolerance():
    assert _rep_in_window([1.5], 0.0, 1.0, tolerance=0.08) is False


def test_fragmentation_ratio_is_one_when_representatives_match_real_states():
    assert _fragmentation_ratio(representative_count=6, real_state_count=6) == 1.0


def test_fragmentation_ratio_above_one_means_over_splitting():
    assert _fragmentation_ratio(representative_count=24, real_state_count=6) == 4.0


def test_no_merge_violation_when_each_group_stays_within_one_real_state():
    groups = [_group(0.0, 1.0), _group(1.2, 2.0), _group(2.2, 3.0)]

    violations = _check_no_cross_state_merges(groups, _STATES, tolerance=0.0)

    assert violations == []


def test_merge_violation_flagged_when_a_group_spans_two_non_adjacent_real_states():
    # One group's span reaches from inside state 1 all the way into
    # state 3, silently swallowing the whole of state 2 -- exactly the
    # "cheating by merging real states" case this round must catch.
    groups = [_group(0.5, 2.5)]

    violations = _check_no_cross_state_merges(groups, _STATES, tolerance=0.0)

    assert len(violations) == 1
    assert "1" in violations[0] and "3" in violations[0]


def test_no_merge_violation_for_a_group_spanning_only_two_adjacent_states():
    # Spanning two ADJACENT real states (no whole state skipped) is not
    # flagged by this specific "skipped an entire state" check -- it is
    # a real but different failure mode (one state can still lose its
    # own representative), reported separately in the fixture summary,
    # not conflated with a same-severity merge violation here.
    groups = [_group(0.5, 1.5)]

    violations = _check_no_cross_state_merges(groups, _STATES, tolerance=0.0)

    assert violations == []
