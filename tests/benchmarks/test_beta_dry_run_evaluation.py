"""Tests for the Beta gate's evaluation rules.

Imports the runner module only -- `paddle_text_detector` defers its
`paddleocr` import into `initialize()`, so these run without the heavy
`[ocr]` extra and without any private media.
"""

from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import (
    _rep_in_window,
    _swallowed_states,
)

_STATES = [
    {"index": 1, "start_seconds": 0.0, "end_seconds": 1.0},
    {"index": 2, "start_seconds": 1.2, "end_seconds": 2.0},
    {"index": 3, "start_seconds": 2.2, "end_seconds": 3.0},
]


def test_no_state_is_swallowed_when_each_one_keeps_a_representative():
    reps = [0.5, 1.5, 2.5]

    assert _swallowed_states(reps, _STATES, tolerance=0.08) == []


def test_a_state_with_no_representative_of_its_own_is_reported_as_swallowed():
    # Exactly the failure that stopped the Alpha family: a neighbouring
    # group absorbs a real state, so that state never gets OCR'd at all.
    # The Generalization Gate's skip-a-whole-state check missed this
    # because states 1 and 2 are ADJACENT; this check must not.
    reps = [1.5, 2.5]

    assert _swallowed_states(reps, _STATES, tolerance=0.08) == [1]


def test_every_state_is_reported_when_nothing_was_detected_at_all():
    assert _swallowed_states([], _STATES, tolerance=0.08) == [1, 2, 3]


def test_tolerance_rescues_a_representative_just_past_a_state_boundary():
    # 1.03s is past state 1's declared end (1.0s) but within tolerance,
    # so state 1 is NOT swallowed -- the non-zero-margin rule this round
    # inherits from the Generalization Gate.
    reps = [1.03, 1.5, 2.5]

    assert _swallowed_states(reps, _STATES, tolerance=0.08) == []


def test_tolerance_does_not_rescue_a_representative_far_outside_a_state():
    assert _rep_in_window([5.0], 0.0, 1.0, tolerance=0.08) is False
