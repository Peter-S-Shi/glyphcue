import numpy as np

from glyphcue.application.ocr_invocation_policy import (
    ChangeTriggeredOcrPolicy,
    NaiveDenseOcrPolicy,
)

_FRAME = np.full((10, 10, 3), 100, dtype=np.uint8)
_CHANGED_FRAME = np.full((10, 10, 3), 200, dtype=np.uint8)


def test_change_triggered_policy_always_ocrs_the_first_frame():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.5)

    assert policy.should_ocr(_FRAME, timestamp=0.0) is True


def test_change_triggered_policy_does_not_ocr_an_unchanged_frame():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.05)
    policy.should_ocr(_FRAME, timestamp=0.0)

    assert policy.should_ocr(_FRAME, timestamp=0.1) is False


def test_change_triggered_policy_ocrs_when_the_frame_changes_enough():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.05)
    policy.should_ocr(_FRAME, timestamp=0.0)

    # Frame 1: candidate onset (deferred)
    assert policy.should_ocr(_CHANGED_FRAME, timestamp=0.1) is False
    # Frame 2: stable on _CHANGED_FRAME -> settled & confirmed!
    assert policy.should_ocr(_CHANGED_FRAME, timestamp=0.14) is True


def test_change_triggered_policy_forces_a_confirmation_ocr_after_the_max_gap():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.5, max_gap_seconds=1.0)
    policy.should_ocr(_FRAME, timestamp=0.0)

    # Unchanged frame, but well past max_gap_seconds since the last OCR.
    assert policy.should_ocr(_FRAME, timestamp=2.0) is True


def test_change_triggered_policy_does_not_force_confirmation_before_the_max_gap():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.5, max_gap_seconds=1.0)
    policy.should_ocr(_FRAME, timestamp=0.0)

    assert policy.should_ocr(_FRAME, timestamp=0.5) is False


def test_naive_dense_policy_always_ocrs_every_frame():
    policy = NaiveDenseOcrPolicy()

    assert policy.should_ocr(_FRAME, timestamp=0.0) is True
    assert policy.should_ocr(_FRAME, timestamp=0.1) is True
    assert policy.should_ocr(_FRAME, timestamp=0.2) is True


def test_change_triggered_policy_reports_first_frame_as_the_trigger_reason():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.5)

    policy.should_ocr(_FRAME, timestamp=0.0)

    assert policy.last_trigger_reason == "first_frame"


def test_change_triggered_policy_reports_change_detected_as_the_trigger_reason():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.05, max_gap_seconds=100.0)
    policy.should_ocr(_FRAME, timestamp=0.0)

    policy.should_ocr(_CHANGED_FRAME, timestamp=0.1)
    policy.should_ocr(_CHANGED_FRAME, timestamp=0.14)

    assert policy.last_trigger_reason == "change_detected"


def test_change_triggered_policy_reports_periodic_confirmation_as_the_trigger_reason():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.5, max_gap_seconds=1.0)
    policy.should_ocr(_FRAME, timestamp=0.0)

    policy.should_ocr(_FRAME, timestamp=2.0)

    assert policy.last_trigger_reason == "periodic_confirmation"


def test_change_triggered_policy_reason_is_unchanged_when_should_ocr_returns_false():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.5, max_gap_seconds=1.0)
    policy.should_ocr(_FRAME, timestamp=0.0)

    policy.should_ocr(_FRAME, timestamp=0.5)  # no OCR this call

    assert policy.last_trigger_reason == "first_frame"  # still the last real decision's reason
