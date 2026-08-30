from glyphcue.domain.review_state import ReviewState


def test_review_state_has_expected_values():
    assert {s.value for s in ReviewState} == {
        "pending",
        "approved",
        "rejected",
        "needs_review",
    }


def test_review_state_default_is_pending():
    assert ReviewState.PENDING.value == "pending"
