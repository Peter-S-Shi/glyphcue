import pytest

from glyphcue.application.cue_review_actions import (
    approve_cue,
    discard_cue,
    edit_cue_language_text,
    merge_cues,
    nudge_cue_timing,
    split_cue,
)
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


def _cue(id_, start, end, texts=None, review_state=ReviewState.PENDING):
    texts = texts or {"en": "Hello"}
    layers = tuple(
        LanguageLayer(language=language, text=text, observation_ids=(f"{id_}-{language}",))
        for language, text in texts.items()
    )
    return Cue(id=id_, start_time=start, end_time=end, language_layers=layers, review_state=review_state)


def test_approve_cue_sets_approved_and_leaves_others_untouched():
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]

    result = approve_cue(cues, "c1")

    assert result[0].review_state == ReviewState.APPROVED
    assert result[1].review_state == ReviewState.PENDING


def test_approve_cue_raises_for_unknown_id():
    cues = [_cue("c1", 0.0, 1.0)]

    with pytest.raises(ValueError):
        approve_cue(cues, "missing")


def test_discard_cue_sets_rejected():
    cues = [_cue("c1", 0.0, 1.0)]

    result = discard_cue(cues, "c1")

    assert result[0].review_state == ReviewState.REJECTED


def test_edit_cue_language_text_updates_only_the_named_layer():
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Hello", "zh": "你好"})]

    result = edit_cue_language_text(cues, "c1", "en", "Hello there")

    layers = {layer.language: layer for layer in result[0].language_layers}
    assert layers["en"].text == "Hello there"
    assert layers["zh"].text == "你好"
    # Provenance is not discarded just because the text was hand-edited.
    assert layers["en"].observation_ids == ("c1-en",)


def test_edit_cue_language_text_raises_for_unknown_language():
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Hello"})]

    with pytest.raises(ValueError):
        edit_cue_language_text(cues, "c1", "zh", "你好")


def test_nudge_cue_timing_shifts_start_and_end():
    cues = [_cue("c1", 1.0, 2.0)]

    result = nudge_cue_timing(cues, "c1", start_delta=-0.1, end_delta=0.2)

    assert result[0].start_time == pytest.approx(0.9)
    assert result[0].end_time == pytest.approx(2.2)


def test_nudge_cue_timing_rejects_a_nudge_that_would_make_end_before_start():
    cues = [_cue("c1", 1.0, 1.2)]

    with pytest.raises(ValueError):
        nudge_cue_timing(cues, "c1", start_delta=0.0, end_delta=-1.0)


def test_split_cue_produces_two_cues_spanning_the_original_range():
    cues = [_cue("c1", 0.0, 4.0, texts={"en": "Hello world"})]

    result = split_cue(cues, "c1", split_time=2.0)

    assert len(result) == 2
    first, second = result
    assert first.start_time == 0.0
    assert first.end_time == 2.0
    assert second.start_time == 2.0
    assert second.end_time == 4.0
    # Needs fresh human review -- a machine split is not an approval.
    assert first.review_state == ReviewState.NEEDS_REVIEW
    assert second.review_state == ReviewState.NEEDS_REVIEW
    assert first.id != second.id


def test_split_cue_rejects_a_split_time_outside_the_cue_range():
    cues = [_cue("c1", 0.0, 4.0)]

    with pytest.raises(ValueError):
        split_cue(cues, "c1", split_time=5.0)


def test_merge_cues_spans_both_original_ranges():
    cues = [
        _cue("c1", 0.0, 2.0, texts={"en": "Hello"}),
        _cue("c2", 2.0, 4.0, texts={"en": "world"}),
    ]

    result = merge_cues(cues, "c1", "c2")

    assert len(result) == 1
    merged = result[0]
    assert merged.start_time == 0.0
    assert merged.end_time == 4.0
    assert merged.review_state == ReviewState.NEEDS_REVIEW


def test_merge_cues_combines_matching_language_layers_and_keeps_provenance():
    cues = [
        _cue("c1", 0.0, 2.0, texts={"en": "Hello"}),
        _cue("c2", 2.0, 4.0, texts={"en": "world"}),
    ]

    result = merge_cues(cues, "c1", "c2")

    layer = result[0].language_layers[0]
    assert layer.language == "en"
    assert "Hello" in layer.text and "world" in layer.text
    assert set(layer.observation_ids) == {"c1-en", "c2-en"}


def test_merge_cues_preserves_a_language_present_in_only_one_side():
    cues = [
        _cue("c1", 0.0, 2.0, texts={"en": "Hello", "zh": "你好"}),
        _cue("c2", 2.0, 4.0, texts={"en": "world"}),
    ]

    result = merge_cues(cues, "c1", "c2")

    layers = {layer.language: layer for layer in result[0].language_layers}
    assert layers["zh"].text == "你好"
