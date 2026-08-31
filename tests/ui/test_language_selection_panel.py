from glyphcue.ui.language_selection_panel import LanguageSelectionPanel


def test_defaults_to_a_single_legal_language_when_nothing_is_selected(qapp_guard):
    panel = LanguageSelectionPanel(available_languages=("en", "zh", "ja"))

    assert panel.selected_languages() == ("en",)


def test_set_languages_restores_a_previously_configured_multilingual_selection(qapp_guard):
    panel = LanguageSelectionPanel(available_languages=("en", "zh", "ja"))

    panel.set_languages(("ja", "en"))

    assert panel.selected_languages() == ("ja", "en")


def test_add_language_appends_a_generic_selection_not_hard_coded_to_two(qapp_guard):
    panel = LanguageSelectionPanel(available_languages=("en", "zh", "ja"))

    panel.add_combo.setCurrentText("zh")
    panel.add_button.click()
    panel.add_combo.setCurrentText("ja")
    panel.add_button.click()

    assert panel.selected_languages() == ("en", "zh", "ja")


def test_add_language_does_not_duplicate_an_already_selected_language(qapp_guard):
    panel = LanguageSelectionPanel(available_languages=("en", "zh", "ja"))

    panel.add_combo.setCurrentText("en")
    panel.add_button.click()

    assert panel.selected_languages() == ("en",)


def test_remove_selected_language_removes_it(qapp_guard):
    panel = LanguageSelectionPanel(available_languages=("en", "zh", "ja"))
    panel.set_languages(("en", "zh"))
    panel.language_list.setCurrentRow(1)

    panel.remove_button.click()

    assert panel.selected_languages() == ("en",)


def test_cannot_remove_the_last_remaining_language(qapp_guard):
    # A Track Group must always have at least one language (domain
    # invariant, see TrackGroup.__post_init__) -- the picker must never
    # let a user reach zero.
    panel = LanguageSelectionPanel(available_languages=("en", "zh", "ja"))
    panel.language_list.setCurrentRow(0)

    panel.remove_button.click()

    assert panel.selected_languages() == ("en",)
