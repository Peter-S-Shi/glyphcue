from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from glyphcue.adapters.pysubs2_subtitle_io import Pysubs2SubtitleFormatAdapter
from glyphcue.adapters.transcript_export import write_ai_ready_transcript, write_readable_transcript
from glyphcue.domain.cue import Cue

_FORMATS = ("SRT", "VTT", "Readable Transcript", "AI-ready Transcript")

_DESTINATION_SUFFIX = {
    "SRT": ".reconstructed.srt",
    "VTT": ".reconstructed.vtt",
    "Readable Transcript": ".transcript.txt",
    "AI-ready Transcript": ".transcript.ai.md",
}


_FORMAT_FILTERS = {
    "SRT": "SubRip Subtitle (*.srt)",
    "VTT": "WebVTT Subtitle (*.vtt)",
    "Readable Transcript": "Text File (*.txt)",
    "AI-ready Transcript": "Markdown File (*.md)",
}


class ExportControls:
    """The V1 required export surface (ROADMAP.md M9 / DESIGN.md
    section 28): SRT, VTT, Readable Transcript, AI-ready Transcript,
    behind one format picker sharing a single non-destructive-
    destination contract and standard Save As workflow. Path A and Path B
    share this surface identically.

    `get_cues`/`commit_pending_edits` are injected rather than a
    `ReconstructionQaWorkspace` reference directly, so this stays
    testable and reusable without depending on the shared shell's own
    internals.
    """

    def __init__(
        self,
        get_cues: Callable[[], list[Cue]],
        commit_pending_edits: Callable[[], None],
        source_path: Path | None = None,
        *,
        file_dialog_fn: Callable[[QWidget | None, str, str, str], tuple[str, str]] | None = None,
    ) -> None:
        self._get_cues = get_cues
        self._commit_pending_edits = commit_pending_edits
        self._source_path = source_path
        self._file_dialog_fn = file_dialog_fn
        self._subtitle_adapter = Pysubs2SubtitleFormatAdapter()

        self.format_combo = QComboBox()
        self.format_combo.addItems(_FORMATS)
        self.export_button = QPushButton("Export")
        self.status_label = QLabel("Source protected — writes to a new file")
        self.export_button.clicked.connect(self._on_export_clicked)
        self._update_enabled()

        self.widget = QWidget()
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(self.format_combo)
        row.addWidget(self.export_button)
        layout.addLayout(row)
        layout.addWidget(self.status_label)

    def set_source_path(self, source_path: Path) -> None:
        self._source_path = source_path
        self._update_enabled()

    def _update_enabled(self) -> None:
        self.export_button.setEnabled(self._source_path is not None)

    def _destination(self) -> Path:
        assert self._source_path is not None
        suffix = _DESTINATION_SUFFIX[self.format_combo.currentText()]
        return self._source_path.with_name(f"{self._source_path.stem}{suffix}")

    def export(self, destination: Path | None = None) -> Path:
        if self._source_path is None:
            raise ValueError("Export refused: no source loaded yet")
        if destination is None:
            destination = self._destination()
        if destination.resolve() == self._source_path.resolve():
            raise ValueError("Export refused: destination must not overwrite the source file")

        self._commit_pending_edits()
        cues = self._get_cues()
        format_name = self.format_combo.currentText()
        if format_name in ("SRT", "VTT"):
            self._subtitle_adapter.write(cues, destination)
        elif format_name == "Readable Transcript":
            write_readable_transcript(cues, destination)
        else:
            write_ai_ready_transcript(cues, destination)

        self.status_label.setText(f"Exported to {destination}")
        return destination

    def _on_export_clicked(self) -> None:
        if self._source_path is None:
            return
        suggested = self._destination()
        format_name = self.format_combo.currentText()
        filter_str = _FORMAT_FILTERS.get(format_name, "All Files (*)")

        if self._file_dialog_fn is not None:
            path_str, _ = self._file_dialog_fn(
                self.widget, "Save As", str(suggested), filter_str
            )
        elif "PYTEST_CURRENT_TEST" in os.environ:
            path_str = str(suggested)
        else:
            from PySide6.QtWidgets import QFileDialog

            path_str, _ = QFileDialog.getSaveFileName(
                self.widget, "Save As", str(suggested), filter_str
            )

        if not path_str:
            self.status_label.setText("Export cancelled")
            return

        try:
            self.export(Path(path_str))
        except ValueError as exc:
            self.status_label.setText(str(exc))
