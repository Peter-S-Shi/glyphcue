from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QTextEdit, QVBoxLayout, QWidget

from glyphcue.domain.observation import Observation
from glyphcue.application.caption_identity_review import caption_evidence_summary
from glyphcue.ui.design_tokens import Color, Spacing


def _summary(observation: Observation) -> str:
    text = observation.text if len(observation.text) <= 40 else observation.text[:37] + "..."
    return f"{observation.start_time:.3f}s  {text}"


def _detail(observation: Observation) -> str:
    lines = [
        f"text: {observation.text}",
        f"start_time: {observation.start_time}",
        f"end_time: {observation.end_time}",
        f"language: {observation.language}",
        f"confidence: {observation.confidence}",
        f"roi: {observation.roi}",
        f"geometry: {observation.geometry}",
        f"frame_reference: {observation.frame_reference}",
        f"provenance.kind: {observation.provenance.kind.value}",
        f"provenance.source: {observation.provenance.source}",
        f"provenance.detail: {dict(observation.provenance.detail)}",
    ]
    identity = caption_evidence_summary(observation)
    if identity:
        lines.append(identity)
    return "\n".join(lines)


class OcrEvidencePane(QWidget):
    """QA-workbench pane for inspecting Milestone 4 OCR Observations.

    Read-only evidence review: lists every Observation and shows full
    provenance for the selected one (PTS, ROI, raw text, engine score,
    geometry, engine/runtime metadata, source-frame reference) -- the
    ROADMAP M4 "observations are inspectable in the QA workbench"
    acceptance gate. Mirrors PathBWorkspace's queue/evidence_view
    pattern (list on the left, detail on the right) rather than
    inventing a new layout convention.
    """

    def __init__(self, observations: list[Observation]) -> None:
        super().__init__()
        self.setObjectName("observationEvidenceCard")
        self._observations: list[Observation] = []

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("observationList")
        self.detail_view = QTextEdit()
        self.detail_view.setObjectName("observationDetail")
        self.detail_view.setReadOnly(True)
        self.detail_view.setStyleSheet(
            f"background-color: {Color.SURFACE_0}; font-family: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace; font-size: 11px; border: 1px solid {Color.BORDER_SUBTLE}; border-radius: 4px; padding: 4px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.CARD_STANDARD, Spacing.CARD_COMPACT, Spacing.CARD_STANDARD, Spacing.CARD_COMPACT
        )
        layout.setSpacing(Spacing.COMPACT)

        header_title = QLabel("ALL OBSERVATIONS & PROVENANCE AUDIT")
        header_title.setObjectName("sectionHeaderLabel")
        header_title.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {Color.TEXT_SECONDARY}; letter-spacing: 0.5px;"
        )
        layout.addWidget(header_title)

        panes_layout = QHBoxLayout()
        panes_layout.setSpacing(Spacing.STANDARD)

        list_column = QVBoxLayout()
        list_title = QLabel("OBSERVATIONS")
        list_title.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {Color.TEXT_MUTED};")
        list_column.addWidget(list_title)
        list_column.addWidget(self.list_widget)
        panes_layout.addLayout(list_column, stretch=1)

        detail_column = QVBoxLayout()
        detail_title = QLabel("PROVENANCE & METADATA")
        detail_title.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {Color.TEXT_MUTED};")
        detail_column.addWidget(detail_title)
        detail_column.addWidget(self.detail_view)
        panes_layout.addLayout(detail_column, stretch=1)

        layout.addLayout(panes_layout)

        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        self.set_observations(observations)

    def set_observations(self, observations: list[Observation]) -> None:
        self._observations = list(observations)
        self.list_widget.clear()
        self.detail_view.clear()
        for observation in self._observations:
            self.list_widget.addItem(_summary(observation))

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._observations):
            self.detail_view.clear()
            return
        self.detail_view.setPlainText(_detail(self._observations[row]))
