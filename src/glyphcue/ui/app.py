from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.ocr_engine_selection import create_ocr_engine
from glyphcue.adapters.paddleocr_text_detector import PaddleOcrTextDetector
from glyphcue.adapters.text_detector_selection import create_text_detector
from glyphcue.application.hybrid_evidence_job import TextDetector
from glyphcue.application.thin_path_b import parse_and_reconstruct
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.design_tokens import Color, Spacing, base_stylesheet
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.path_b_workspace import PathBWorkspace

DEFAULT_DB_PATH = Path.home() / ".glyphcue" / "glyphcue.sqlite3"

DEV_OCR_PROFILE_SELECTOR_ENV_VAR = "GLYPHCUE_DEV_OCR_PROFILE_SELECTOR"
"""Set to "1" before launching to reveal the developer/manual-QA-only
OCR Profile dropdown in Path A (M11). Unset/anything else keeps the
shipped default: production trigger, no selector shown. Not a V1
product feature -- there is no in-app way to turn this on."""


def _dev_ocr_profile_selector_enabled() -> bool:
    return os.environ.get(DEV_OCR_PROFILE_SELECTOR_ENV_VAR) == "1"


PREFER_DIRECTML_OCR_ENV_VAR = "GLYPHCUE_PREFER_DIRECTML_OCR"
"""Set to "1" to opt into the experimental Windows DirectML OCR
accelerator (M11 P3, see docs/adr/0001-ocr-runtime-selection.md's
Milestone 11 addendum) for OCR engines this process constructs.
Unset/anything else keeps the shipped default: PaddleOcrEngine (P2
recognition-only), unconditionally. Even when set, create_ocr_engine only
attempts DirectML after a real platform/package preflight and
initialization probe, and falls back to Paddle on any unsupported
platform, missing install, or provider-init failure -- this variable
requests the preference, it does not guarantee the backend. Not a V1
product feature -- there is no in-app toggle for this.
"""


def _prefer_directml_ocr_enabled() -> bool:
    return os.environ.get(PREFER_DIRECTML_OCR_ENV_VAR) == "1"


def _ocr_engine_factory(language: str) -> OcrEngine:
    return create_ocr_engine(language, prefer_directml=_prefer_directml_ocr_enabled())


PREFER_DIRECTML_DETECTOR_ENV_VAR = "GLYPHCUE_PREFER_DIRECTML_DETECTOR"
"""Set to "1" to opt into the experimental Windows DirectML text detector
accelerator (M11 P4B) for Hybrid OCR jobs this process constructs.
Unset/anything else keeps the shipped default: PaddleOcrTextDetector (PaddlePaddle
CPU), unconditionally. Even when set, create_text_detector only attempts DirectML
after a real platform/package preflight and initialization probe, and falls back
to Paddle on any unsupported platform, missing install, or provider-init failure.
"""


def _prefer_directml_detector_enabled() -> bool:
    return os.environ.get(PREFER_DIRECTML_DETECTOR_ENV_VAR) == "1"


def _hybrid_detector_factory() -> TextDetector:
    return create_text_detector(prefer_directml=_prefer_directml_detector_enabled())


class GlyphCueWorkbench(QMainWindow):
    """The persistent Evidence Workbench product shell (M11 UI Reconstruction
    Phase A, Phase B & Phase B.1 / DOG-008).

    Replaces the previous thin chooser / separate-window model with a single,
    persistent product shell. Path A (Video Extraction) and Path B (Caption
    Normalizer) exist as peer evidence-source modes within this shell.
    Mode switching preserves the window, commits pending edits, and switches
    the 3-pane workbench view in-place.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        super().__init__()
        self._db_path = db_path
        self.setWindowTitle("GlyphCue — Subtitle Reconstruction Evidence Workbench")
        self.setStyleSheet(base_stylesheet())
        self.resize(1280, 720)
        self.setMinimumSize(1024, 600)

        # Compatibility reference
        self.window = self
        self._active_window = self

        self.path_a_pane: PathAMediaPane | None = None
        self.path_b_workspace: PathBWorkspace | None = None
        self.current_mode: str = "path_a"

        # 1. Top App Header / Chrome (Prototype Visual Hierarchy)
        header_widget = QWidget()
        header_widget.setObjectName("appHeader")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.COMPACT, Spacing.PANEL_MAJOR, Spacing.COMPACT
        )

        brand_box = QHBoxLayout()
        brand_box.setSpacing(Spacing.STANDARD)
        brand_logo = QLabel("GC")
        brand_logo.setObjectName("brandLogoBox")
        brand_label = QLabel("GlyphCue")
        brand_label.setObjectName("brandLabel")
        app_badge = QLabel("v0.1.0 · LOCAL")
        app_badge.setObjectName("appBadge")
        brand_box.addWidget(brand_logo)
        brand_box.addWidget(brand_label)
        brand_box.addWidget(app_badge)
        header_layout.addLayout(brand_box)

        # Segmented Mode Switcher
        mode_nav_widget = QWidget()
        mode_nav_widget.setObjectName("modeNavContainer")
        mode_nav_layout = QHBoxLayout(mode_nav_widget)
        mode_nav_layout.setContentsMargins(2, 2, 2, 2)
        mode_nav_layout.setSpacing(2)

        self.path_a_mode_button = QPushButton("Path A: Video Extraction")
        self.path_a_mode_button.setObjectName("modeBtn")
        self.path_a_mode_button.setCheckable(True)
        self.path_a_mode_button.setChecked(True)

        self.path_b_mode_button = QPushButton("Path B: Caption Normalizer")
        self.path_b_mode_button.setObjectName("modeBtn")
        self.path_b_mode_button.setCheckable(True)
        self.path_b_mode_button.setChecked(False)

        mode_nav_layout.addWidget(self.path_a_mode_button)
        mode_nav_layout.addWidget(self.path_b_mode_button)
        header_layout.addWidget(mode_nav_widget)

        header_layout.addStretch(1)

        self.asset_status_label = QLabel("Ready · No source loaded")
        self.asset_status_label.setObjectName("assetStatusPill")
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
        self.path_a_pane.qa.bind_to_host(self)

        # Hide redundant embedded in-pane actions when hosted in workbench shell
        self.path_a_pane.open_button.hide()
        self.path_a_pane.open_caption_file_button.hide()

        self._stack.addWidget(self.path_a_pane.qa.central_widget)

        # Set default responsive 3-pane splitter widths (Left ~280px, Center 1fr flex, Right ~360px)
        splitter = self.path_a_pane.qa.window.findChild(QSplitter)
        if splitter:
            splitter.setSizes([280, 640, 360])

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

    def closeEvent(self, event: QCloseEvent) -> None:
        """DOG-004: Closing the persistent workbench shell commits pending
        edits in whichever workspace is currently active."""
        self.commit_pending_edits()
        super().closeEvent(event)

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
            if self.path_a_pane is not None:
                self.path_a_pane.qa.bind_to_host(self)
                if self.path_a_pane._video_path:
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
                self.path_b_workspace.open_video_button.hide()
                self._stack.addWidget(self.path_b_workspace.qa.central_widget)
                splitter_b = self.path_b_workspace.qa.window.findChild(QSplitter)
                if splitter_b:
                    splitter_b.setSizes([280, 640, 360])
            self.path_b_workspace.qa.bind_to_host(self)
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
            self._stack.insertWidget(0, self.path_a_pane.qa.central_widget)
            splitter = self.path_a_pane.qa.window.findChild(QSplitter)
            if splitter:
                splitter.setSizes([280, 640, 360])
        self.path_a_pane.open_video(path)
        self.path_a_pane.open_button.hide()
        self.path_a_pane.open_caption_file_button.hide()
        self.path_a_pane.qa.bind_to_host(self)
        self.switch_to_mode("path_a")
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
        workspace.open_video_button.hide()
        self.path_b_workspace = workspace
        workspace.qa.bind_to_host(self)
        # Update or add page 1
        if self._stack.count() > 1:
            old_widget = self._stack.widget(1)
            self._stack.removeWidget(old_widget)
        self._stack.addWidget(workspace.qa.central_widget)
        splitter = workspace.qa.window.findChild(QSplitter)
        if splitter:
            splitter.setSizes([280, 640, 360])
        self.switch_to_mode("path_b")
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
        ocr_engine_factory=_ocr_engine_factory,
        db_path=db_path,
        on_open_caption_file=on_open_caption_file,
        enable_dev_ocr_profile_selector=_dev_ocr_profile_selector_enabled(),
        hybrid_detector_factory=_hybrid_detector_factory,
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
