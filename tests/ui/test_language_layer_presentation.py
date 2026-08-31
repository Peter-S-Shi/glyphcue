from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.ui.language_layer_presentation import LanguageLayersPanel, queue_label_for_cue


def _cue(layers):
    return Cue(id="c1", start_time=0.0, end_time=1.0, language_layers=tuple(layers))


def test_single_language_cue_queue_label_shows_just_that_layer():
    cue = _cue([LanguageLayer(language="en", text="Hello world")])

    assert queue_label_for_cue(cue) == "en: Hello world"


def test_bilingual_cue_queue_label_shows_both_layers():
    cue = _cue(
        [
            LanguageLayer(language="en", text="Hello there"),
            LanguageLayer(language="zh", text="你好朋友"),
        ]
    )

    assert queue_label_for_cue(cue) == "en: Hello there | zh: 你好朋友"


def test_high_n_cue_queue_label_collapses_extra_layers():
    # DESIGN.md section 12 guideline: queue shows primary + secondary,
    # additional layers collapse to "+N layers" -- full content stays
    # in the QA inspector (LanguageLayersPanel), not the queue.
    cue = _cue(
        [
            LanguageLayer(language="en", text="Hello there"),
            LanguageLayer(language="zh", text="你好朋友"),
            LanguageLayer(language="ja", text="こんにちは"),
            LanguageLayer(language="ko", text="안녕"),
        ]
    )

    assert queue_label_for_cue(cue) == "en: Hello there | zh: 你好朋友 +2 layers"


def test_panel_renders_one_card_per_language_layer_in_order(qapp_guard):
    cue = _cue(
        [
            LanguageLayer(language="en", text="Hello there"),
            LanguageLayer(language="zh", text="你好朋友"),
        ]
    )

    panel = LanguageLayersPanel(cue)

    assert len(panel.cards) == 2
    assert [card.language for card in panel.cards] == ["en", "zh"]
    assert panel.cards[0].text_label.text() == "Hello there"


def test_panel_marks_a_missing_layer_without_fabricating_text(qapp_guard):
    cue = _cue(
        [
            LanguageLayer(language="en", text="Hello there"),
            LanguageLayer(language="zh", text=""),  # missing/degraded layer
        ]
    )

    panel = LanguageLayersPanel(cue)

    assert panel.cards[0].is_missing is False
    assert panel.cards[1].is_missing is True
    assert panel.cards[1].text_label.text() != ""  # a placeholder, not blank/fabricated


def test_panel_set_cue_replaces_previous_cards(qapp_guard):
    first_cue = _cue([LanguageLayer(language="en", text="First")])
    second_cue = _cue(
        [
            LanguageLayer(language="en", text="Second"),
            LanguageLayer(language="zh", text="第二"),
        ]
    )
    panel = LanguageLayersPanel(first_cue)

    panel.set_cue(second_cue)

    assert len(panel.cards) == 2
    assert panel.cards[0].text_label.text() == "Second"
