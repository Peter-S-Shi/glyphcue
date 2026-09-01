from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.application.thin_path_b import parse_and_reconstruct
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.design_tokens import Color, Spacing, base_stylesheet
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.path_b_workspace import PathBWorkspace

DEFAULT_DB_PATH = Path.home() / ".glyphcue" / "glyphcue.sqlite3"


class GlyphCueWorkbench(QMainWindow):
    """The persistent Evidence Workbench product shell (M11 UI Reconstruction
    Phase A / DOG-008).

    Replaces the previous thin chooser / separate-window model with a single,
    persistent product shell. Path A (Video Extraction) and Path B (Caption
    Normalizer) exist as peer evidence-source modes within this shell.
    Mode switching preserves the window, commits pending edits, and switches
    the 3-pane workbench view in-place.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        super().__init__()
        self._db_path = db_path
        self.setWindowTitle("GlyphCue")
        self.setStyleSheet(base_stylesheet())
        self.resize(1360, 860)

        # Compatibility reference
        self.window = self
        self._active_window = self

        self.path_a_pane: PathAMediaPane | None = None
        self.path_b_workspace: PathBWorkspace | None = None
        self.current_mode: str = "path_a"

        # 1. Top App Header / Chrome
        header_widget = QWidget()
        header_widget.setObjectName("appHeader")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.STANDARD, Spacing.PANEL_MAJOR, Spacing.STANDARD
        )

        brand_label = QLabel("GlyphCue")
        brand_label.setStyleSheet(
            f"font-weight: 800; font-size: 15px; color: {Color.TEXT_PRIMARY};"
        )
        header_layout.addWidget(brand_label)

        mode_nav = QHBoxLayout()
        self.path_a_mode_button = QPushButton("Path A: Video Extraction")
        self.path_b_mode_button = QPushButton("Path B: Caption Normalizer")
        self.path_a_mode_button.setCheckable(True)
        self.path_b_mode_button.setCheckable(True)
        self.path_a_mode_button.setChecked(True)
        mode_nav.addWidget(self.path_a_mode_button)
        mode_nav.addWidget(self.path_b_mode_button)
        header_layout.addLayout(mode_nav)

        header_layout.addStretch(1)

        self.asset_status_label = QLabel("Ready · No source loaded")
        self.asset_status_label.setStyleSheet(
            f"color: {Color.TEXT_MUTED}; font-size: 11px;"
        )
        header_layout.addWidget(self.asset_status_label)

        self.open_video_button = QPushButton("Open Video…")
        self.open_caption_button = QPushButton("Open Caption File…")
        header_layout.addWidget(self.open_video_button)
        header_layout.addWidget(self.open_caption_button)

        # 2. Central Stacked Workspaces
        self._stack = QStackedWidget()

        # Initialize Path A inside the workbench from startup
        _app, self.path_a_pane = create_path_a_app(
            db_path=self._db_path, on_open_caption_file=self.open_caption_file
        )
        self._stack.addWidget(self.path_a_pane.qa.window.centralWidget())

        # Container for main layout
        root_container = QWidget()
        root_layout = QVBoxLayout(root_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(header_widget)
        root_layout.addWidget(self._stack, stretch=1)
        self.setCentralWidget(root_container)

        self.statusBar().showMessage("Local-first · Non-Destructive Ingestion")

        # Event connections
        self.path_a_mode_button.clicked.connect(lambda: self.switch_to_mode("path_a"))
        self.path_b_mode_button.clicked.connect(lambda: self.switch_to_mode("path_b"))
        self.open_video_button.clicked.connect(self._on_open_video_clicked)
        self.open_caption_button.clicked.connect(self._on_open_caption_clicked)

    def _show(self, window: QMainWindow) -> None:
        if self.path_a_pane is not None:
            self.path_a_pane.commit_pending_edits()
        if self.path_b_workspace is not None:
            self.path_b_workspace.commit_pending_edits()
        if self._active_window is not None and self._active_window is not window:
            self._active_window.hide()
        window.show()
        self._active_window = window
        self.show()

    def commit_pending_edits(self) -> None:
        if self.path_a_pane is not None:
            self.path_a_pane.commit_pending_edits()
        if self.path_b_workspace is not None:
            self.path_b_workspace.commit_pending_edits()

    def switch_to_mode(self, mode: str) -> None:
        self.commit_pending_edits()
        if mode == "path_a":
            self.current_mode = "path_a"
            self.path_a_mode_button.setChecked(True)
            self.path_b_mode_button.setChecked(False)
            self._stack.setCurrentIndex(0)
            if self.path_a_pane and self.path_a_pane._video_path:
                self.asset_status_label.setText(f"Video: {self.path_a_pane._video_path.name}")
            else:
                self.asset_status_label.setText("Path A: Ready · No video loaded")
        elif mode == "path_b":
            self.current_mode = "path_b"
            self.path_a_mode_button.setChecked(False)
            self.path_b_mode_button.setChecked(True)
            if self.path_b_workspace is None:
                # Provide a ready empty Path B workspace if none opened yet
                dummy_path = Path("untitled.srt")
                self.path_b_workspace = PathBWorkspace(
                    [], {}, dummy_path, on_open_video=self.open_video
                )
                self._stack.addWidget(self.path_b_workspace.qa.window.centralWidget())
            self._stack.setCurrentIndex(1)
            if self.path_b_workspace and self.path_b_workspace._source_path.name != "untitled.srt":
                self.asset_status_label.setText(f"Captions: {self.path_b_workspace._source_path.name}")
            else:
                self.asset_status_label.setText("Path B: Ready · No caption file loaded")

    def open_video(self, path: Path) -> PathAMediaPane:
        self.commit_pending_edits()
        if self.path_a_pane is None:
            _app, self.path_a_pane = create_path_a_app(
                db_path=self._db_path, on_open_caption_file=self.open_caption_file
            )
            self._stack.insertWidget(0, self.path_a_pane.qa.window.centralWidget())
        self.path_a_pane.open_video(path)
        self.switch_to_mode("path_a")
        self._show(self.path_a_pane.window)
        self.asset_status_label.setText(f"Video: {path.name}")
        return self.path_a_pane

    def open_caption_file(self, path: Path) -> PathBWorkspace:
        self.commit_pending_edits()
        cues, observations_by_id, diagnostics_by_cue_id, import_warnings = parse_and_reconstruct(
            path
        )
        workspace = PathBWorkspace(
            cues,
            observations_by_id,
            path,
            diagnostics_by_cue_id=diagnostics_by_cue_id,
            import_warnings=import_warnings,
            on_open_video=self.open_video,
        )
        self.path_b_workspace = workspace
        # Update or add page 1
        if self._stack.count() > 1:
            old_widget = self._stack.widget(1)
            self._stack.removeWidget(old_widget)
        self._stack.addWidget(workspace.qa.window.centralWidget())
        self.switch_to_mode("path_b")
        self._show(workspace.window)
        self.asset_status_label.setText(f"Captions: {path.name} ({len(cues)} cues)")
        return workspace

    def _on_open_video_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            self, "Open Video", "", "Video files (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if path_str:
            self.open_video(Path(path_str))

    def _on_open_caption_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            self, "Open Caption File", "", "Subtitle files (*.srt *.vtt)"
        )
        if path_str:
            self.open_caption_file(Path(path_str))


GlyphCueEntry = GlyphCueWorkbench


def create_app(db_path: Path = DEFAULT_DB_PATH) -> tuple[QApplication, GlyphCueWorkbench]:
    """Build the QApplication and the persistent Evidence Workbench product shell."""
    app = QApplication.instance() or QApplication(sys.argv)
    workbench = GlyphCueWorkbench(db_path=db_path)
    return app, workbench


def create_path_a_app(
    db_path: Path = DEFAULT_DB_PATH,
    on_open_caption_file: Callable[[Path], None] | None = None,
) -> tuple[QApplication, PathAMediaPane]:
    """Build the QApplication and the Path A media pane, with
    TrackGroup/ROI and OCR-evidence (Observation) persistence wired in.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    conn = connect(db_path)
    track_group_repository = TrackGroupRepository(conn)
    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine_factory=PaddleOcrEngine,
        db_path=db_path,
        on_open_caption_file=on_open_caption_file,
    )
    return app, pane


def main(db_path: Path | None = None) -> int:
    """Production entrypoint (ROADMAP M9): the shared GlyphCue product
    entry -- persistent Evidence Workbench shell.
    """
    app, workbench = create_app(db_path=db_path or DEFAULT_DB_PATH)
    workbench.window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
