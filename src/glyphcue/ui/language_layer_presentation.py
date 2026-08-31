from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from glyphcue.domain.cue import Cue
from glyphcue.ui.design_tokens import Color, Radius, Spacing

_QUEUE_VISIBLE_LAYER_COUNT = 2
"""DESIGN.md section 12 guideline: the left queue shows primary +
secondary layer, collapsing anything past that to "+N layers" so the
navigation list stays vertically stable regardless of how many language
layers a Cue has. Full layer content always stays in the QA inspector
(`LanguageLayersPanel`), never the queue."""


def queue_label_for_cue(cue: Cue) -> str:
    """The compact, fixed-height summary text for one Cue's queue row.

    Never grows unbounded with N: shows at most
    `_QUEUE_VISIBLE_LAYER_COUNT` layers' `language: text`, and collapses
    anything beyond that to a `+N layers` suffix -- DESIGN.md section
    12's explicit guideline for high-N language cases.
    """
    layers = cue.language_layers
    visible = layers[:_QUEUE_VISIBLE_LAYER_COUNT]
    parts = [f"{layer.language}: {layer.text}" for layer in visible]
    label = " | ".join(parts)
    remaining = len(layers) - len(visible)
    if remaining > 0:
        label += f" +{remaining} layers"
    return label


class _LanguageLayerCard(QFrame):
    """One repeatable row/card for a single LanguageLayer, per
    DESIGN.md section 12: language name, reconstructed text, and a
    local issue marker when the layer is missing/degraded (an empty
    reconstructed text -- see `multilingual_reconstruction.py`'s
    missing-layer diagnostic; this card never fabricates a
    replacement, it surfaces the gap)."""

    def __init__(self, language: str, text: str) -> None:
        super().__init__()
        self.setObjectName("languageLayerCard")
        self.setStyleSheet(
            f"""
            QFrame#languageLayerCard {{
                background-color: {Color.SURFACE_1};
                border: 1px solid {Color.BORDER_SUBTLE};
                border-radius: {Radius.MEDIUM}px;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.CARD_STANDARD, Spacing.CARD_COMPACT, Spacing.CARD_STANDARD, Spacing.CARD_COMPACT
        )
        layout.setSpacing(Spacing.MICRO)

        is_missing = not text
        header_text = language.upper()
        if is_missing:
            header_text += "  ⚠ missing"
        header = QLabel(header_text)
        header.setStyleSheet(
            f"color: {Color.WARNING if is_missing else Color.TEXT_SECONDARY}; font-weight: 600;"
        )
        layout.addWidget(header)

        body = QLabel(text if text else "(no evidence for this language in this Cue)")
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color: {Color.TEXT_MUTED if is_missing else Color.TEXT_PRIMARY};"
            + (" font-style: italic;" if is_missing else "")
        )
        layout.addWidget(body)

        self.is_missing = is_missing
        self.language = language
        self.text_label = body
        self.header_label = header


class LanguageLayersPanel(QWidget):
    """Renders ALL of one Cue's language layers as repeatable cards --
    the QA inspector's full view (DESIGN.md section 12: "The QA
    inspector may show all layers"), unlike the queue's collapsed
    `queue_label_for_cue` summary.

    V1 frozen: no per-layer timing controls exist here at all (ROADMAP
    section 4 / DESIGN.md section 13) -- every layer inherits the
    Cue's own start_time/end_time, never its own.
    """

    def __init__(self, cue: Cue | None = None) -> None:
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Spacing.STANDARD)
        self.cards: list[_LanguageLayerCard] = []
        if cue is not None:
            self.set_cue(cue)

    def set_cue(self, cue: Cue | None) -> None:
        """Replaces the panel's contents with `cue`'s language layers,
        always in `cue.language_layers`' own order -- the same stable,
        Track Group-configured ordering `reconstruct_multilingual_cues_for_track_group`
        produces, never re-sorted or re-derived here. `None` clears the
        panel back to no cards (e.g. a fresh/single-language OCR run
        with no multilingual Cue to show)."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.cards = []
        if cue is None:
            return
        for layer in cue.language_layers:
            card = _LanguageLayerCard(layer.language, layer.text)
            self._layout.addWidget(card)
            self.cards.append(card)
