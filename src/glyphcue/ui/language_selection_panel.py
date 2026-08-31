from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QListWidget, QPushButton, QVBoxLayout, QWidget

from glyphcue.ui.design_tokens import Spacing


class LanguageSelectionPanel(QWidget):
    """A generic, repeatable 1..N language add/remove/select surface for
    a Track Group (DESIGN.md section 11: Track Group -> ROI -> Language
    Layers 1..N; "Do not hard-code: Language A / Language B as the
    product model").

    `available_languages` is the closed set of language codes this
    surface can offer -- for the real production entrypoint, this is
    `PaddleOcrEngine.CANONICAL_LANGUAGES`, since only those are
    languages the real OCR runtime can actually be constructed for.
    Tests can pass any tuple, so this widget itself never hard-codes
    specific language codes.

    Always starts with exactly one legal selection
    (`available_languages[0]`) -- never zero, and never a placeholder
    like "und" that no real engine could be constructed with -- until
    `set_languages` restores a previously-saved configuration.
    """

    def __init__(self, available_languages: tuple[str, ...]) -> None:
        super().__init__()
        if not available_languages:
            raise ValueError("LanguageSelectionPanel.available_languages must not be empty")
        self._available_languages = available_languages

        self.language_list = QListWidget()
        self.add_combo = QComboBox()
        self.add_combo.addItems(list(available_languages))
        self.add_button = QPushButton("Add Language")
        self.remove_button = QPushButton("Remove Selected")

        self.add_button.clicked.connect(self._on_add_clicked)
        self.remove_button.clicked.connect(self._on_remove_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.COMPACT)
        layout.addWidget(self.language_list)
        controls = QHBoxLayout()
        controls.addWidget(self.add_combo)
        controls.addWidget(self.add_button)
        controls.addWidget(self.remove_button)
        layout.addLayout(controls)

        self.set_languages((available_languages[0],))

    def selected_languages(self) -> tuple[str, ...]:
        return tuple(self.language_list.item(index).text() for index in range(self.language_list.count()))

    def set_languages(self, languages: tuple[str, ...]) -> None:
        """Replaces the current selection with `languages`, in that
        order. Falls back to a single legal language if `languages` is
        empty -- the picker must never show zero (TrackGroup requires
        at least one)."""
        self.language_list.clear()
        for language in languages or (self._available_languages[0],):
            self.language_list.addItem(language)

    def _on_add_clicked(self) -> None:
        language = self.add_combo.currentText()
        if language and language not in self.selected_languages():
            self.language_list.addItem(language)

    def _on_remove_clicked(self) -> None:
        if self.language_list.count() <= 1:
            return  # never remove the last remaining language
        row = self.language_list.currentRow()
        if row >= 0:
            self.language_list.takeItem(row)
