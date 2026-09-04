import pytest

from glyphcue.application.cue_merge import merge_incremental_cues
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


def _cue(id_, start, end, text="text", state=ReviewState.PENDING):
    return Cue(
        id=id_,
        start_time=start,
        end_time=end,
        language_layers=(LanguageLayer(language="en", text=text, observation_ids=(f"obs-{id_}",)),),
        review_state=state,
    )


def test_merge_disjoint_ranges_appends_cues():
    existing = [_cue("c1", 0.0, 1.0, state=ReviewState.APPROVED)]
    new_cues = [_cue("c2", 2.0, 3.0, state=ReviewState.PENDING)]

    merged = merge_incremental_cues(existing, new_cues, range_start=1.5, range_end=3.5)

    assert [c.id for c in merged] == ["c1", "c2"]
    assert merged[0].review_state == ReviewState.APPROVED
    assert merged[1].review_state == ReviewState.PENDING


def test_merge_overlapping_replaces_unreviewed_pending_cues():
    existing = [
        _cue("c1", 0.0, 1.0, text="first", state=ReviewState.APPROVED),
        _cue("c2_old", 1.5, 2.5, text="old machine", state=ReviewState.PENDING),
        _cue("c3", 4.0, 5.0, text="last", state=ReviewState.PENDING),
    ]
    new_cues = [_cue("c2_new", 1.4, 2.6, text="new machine", state=ReviewState.PENDING)]

    merged = merge_incremental_cues(existing, new_cues, range_start=1.0, range_end=3.0)

    assert [c.id for c in merged] == ["c1", "c2_new", "c3"]
    assert merged[1].language_layers[0].text == "new machine"


def test_merge_preserves_approved_rejected_and_needs_review_cues():
    existing = [
        _cue("c_app", 1.2, 1.8, text="approved text", state=ReviewState.APPROVED),
        _cue("c_rej", 2.0, 2.5, text="rejected text", state=ReviewState.REJECTED),
        _cue("c_nr", 2.6, 3.2, text="edited text", state=ReviewState.NEEDS_REVIEW),
    ]
    # New OCR tries to run over 1.0 - 4.0 and proposes a colliding machine cue
    new_cues = [
        _cue("c_new_colliding", 1.1, 3.0, text="machine raw", state=ReviewState.PENDING),
        _cue("c_new_fresh", 3.5, 3.9, text="fresh text", state=ReviewState.PENDING),
    ]

    merged = merge_incremental_cues(existing, new_cues, range_start=1.0, range_end=4.0)

    # Approved, rejected, needs_review must all survive and colliding new cue is dropped
    ids = [c.id for c in merged]
    assert "c_app" in ids
    assert "c_rej" in ids
    assert "c_nr" in ids
    assert "c_new_fresh" in ids
    assert "c_new_colliding" not in ids


def test_merge_preserves_boundary_straddling_cues():
    existing = [
        _cue("straddle_left", 0.5, 1.5, state=ReviewState.PENDING),  # crosses range_start = 1.0
        _cue("straddle_right", 2.5, 3.5, state=ReviewState.PENDING),  # crosses range_end = 3.0
    ]
    new_cues = [_cue("c_mid", 1.8, 2.2, state=ReviewState.PENDING)]

    merged = merge_incremental_cues(existing, new_cues, range_start=1.0, range_end=3.0)

    ids = [c.id for c in merged]
    assert ids == ["straddle_left", "c_mid", "straddle_right"]