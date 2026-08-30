from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from glyphcue.adapters.pysubs2_subtitle_io import Pysubs2SubtitleFormatAdapter
from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.design_tokens import Spacing
from glyphcue.ui.main_window import MainWindow


def _padded_pane(*widgets: QWidget) -> QWidget:
    pane = QWidget()
    layout = QVBoxLayout(pane)
    layout.setContentsMargins(
        Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
    )
    for widget in widgets:
        layout.addWidget(widget)
    return pane


class PathBWorkspace:
    """Wires the M1 minimal QA loop into the frozen three-pane shell.

    Scope is intentionally limited to ROADMAP.md Milestone 1: queue
    selection, active Cue, source observations, editable text, approve,
    export. This is not the full QA workspace (Milestone 7).
    """

    def __init__(
        self,
        cues: list[Cue],
        observations_by_id: dict[str, Observation],
        export_destination: Path,
    ) -> None:
        self._cues = list(cues)
        self._observations_by_id = observations_by_id
        self._export_destination = export_destination
        self._adapter = Pysubs2SubtitleFormatAdapter()

        self.queue = QListWidget()
        self.evidence_view = QTextEdit()
        self.evidence_view.setReadOnly(True)
        self.text_edit = QTextEdit()
        self.approve_button = QPushButton("Approve")
        self.export_button = QPushButton("Export")
        self.status_label = QLabel("")

        for cue in self._cues:
            layer_text = cue.language_layers[0].text if cue.language_layers else ""
            self.queue.addItem(QListWidgetItem(f"{cue.start_time:.2f}–{cue.end_time:.2f}  {layer_text[:40]}"))

        self.window = MainWindow(
            left_pane=_padded_pane(self.queue),
            center_pane=_padded_pane(self.evidence_view),
            right_pane=_padded_pane(
                self.text_edit, self.approve_button, self.export_button, self.status_label
            ),
        )

        self.queue.currentRowChanged.connect(self._on_row_changed)
        self.approve_button.clicked.connect(self._on_approve)
        self.export_button.clicked.connect(self._on_export)

        if self._cues:
            self.queue.setCurrentRow(0)

    @property
    def cues(self) -> list[Cue]:
        return list(self._cues)

    @property
    def active_cue(self) -> Cue | None:
        row = self.queue.currentRow()
        if row < 0 or row >= len(self._cues):
            return None
        return self._cues[row]

    def _on_row_changed(self, row: int) -> None:
        cue = self.active_cue
        if cue is None:
            self.evidence_view.clear()
            self.text_edit.clear()
            return
        layer = cue.language_layers[0]
        self.text_edit.setPlainText(layer.text)
        sources = [
            self._observations_by_id[observation_id].text
            for observation_id in layer.observation_ids
            if observation_id in self._observations_by_id
        ]
        self.evidence_view.setPlainText("\n".join(sources))

    def _on_approve(self) -> None:
        row = self.queue.currentRow()
        cue = self.active_cue
        if cue is None:
            return
        layer = replace(cue.language_layers[0], text=self.text_edit.toPlainText())
        self._cues[row] = replace(
            cue, language_layers=(layer,), review_state=ReviewState.APPROVED
        )
        self.status_label.setText("Approved")

    def _on_export(self) -> None:
        self._adapter.write(self._cues, self._export_destination)
        self.status_label.setText(f"Exported to {self._export_destination}")
