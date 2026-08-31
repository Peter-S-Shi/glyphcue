from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QTextEdit, QVBoxLayout, QWidget

from glyphcue.domain.observation import Observation
from glyphcue.ui.design_tokens import Spacing


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
        self._observations: list[Observation] = []

        self.list_widget = QListWidget()
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        list_column = QVBoxLayout()
        list_column.addWidget(self.list_widget)
        layout.addLayout(list_column)
        layout.addWidget(self.detail_view)

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
