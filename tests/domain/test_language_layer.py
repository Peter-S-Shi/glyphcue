import pytest

from glyphcue.domain.language_layer import LanguageLayer


def test_language_layer_holds_language_and_text():
    layer = LanguageLayer(language="ja", text="こんにちは")

    assert layer.language == "ja"
    assert layer.text == "こんにちは"
    assert layer.observation_ids == ()


def test_language_layer_rejects_empty_language():
    with pytest.raises(ValueError):
        LanguageLayer(language="", text="hello")


def test_language_layer_has_no_timing_fields():
    layer = LanguageLayer(language="en", text="hello")

    assert not hasattr(layer, "start_time")
    assert not hasattr(layer, "end_time")


def test_language_layer_tracks_supporting_observation_ids():
    layer = LanguageLayer(language="en", text="hello", observation_ids=("obs-1", "obs-2"))

    assert layer.observation_ids == ("obs-1", "obs-2")
