import pytest

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


def _layers() -> tuple[LanguageLayer, ...]:
    return (LanguageLayer(language="en", text="hello"),)


def test_cue_holds_timing_and_layers_and_defaults_to_pending():
    cue = Cue(id="cue-1", start_time=1.0, end_time=2.0, language_layers=_layers())

    assert cue.start_time == 1.0
    assert cue.end_time == 2.0
    assert cue.language_layers == _layers()
    assert cue.review_state is ReviewState.PENDING


def test_cue_rejects_end_before_start():
    with pytest.raises(ValueError):
        Cue(id="cue-2", start_time=2.0, end_time=1.0, language_layers=_layers())


def test_cue_rejects_empty_language_layers():
    with pytest.raises(ValueError):
        Cue(id="cue-3", start_time=0.0, end_time=1.0, language_layers=())


def test_cue_supports_multiple_language_layers_sharing_its_timing():
    layers = (
        LanguageLayer(language="ja", text="こんにちは"),
        LanguageLayer(language="en", text="hello"),
    )

    cue = Cue(id="cue-4", start_time=0.0, end_time=1.0, language_layers=layers)

    assert len(cue.language_layers) == 2
    assert cue.start_time == 0.0
    assert cue.end_time == 1.0


def test_cue_accepts_explicit_review_state():
    cue = Cue(
        id="cue-5",
        start_time=0.0,
        end_time=1.0,
        language_layers=_layers(),
        review_state=ReviewState.APPROVED,
    )

    assert cue.review_state is ReviewState.APPROVED
