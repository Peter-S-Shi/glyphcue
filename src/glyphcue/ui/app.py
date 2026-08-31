from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.application.thin_path_b import parse_and_reconstruct
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.design_tokens import Spacing, base_stylesheet
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.path_b_workspace import PathBWorkspace

DEFAULT_DB_PATH = Path.home() / ".glyphcue" / "glyphcue.sqlite3"


class GlyphCueEntry:
    """The single production entrypoint's first-launch / empty state
    (DESIGN.md section 85): Path A and Path B are peer evidence-source
    modes of one product (DESIGN.md section 9), reached from the same
    launch screen rather than two separate tools. This is intentionally
    thin -- `Open Video` / `Open Caption File` only, no dashboard
    (DESIGN.md section 86) -- and hands off to the existing, unmodified
    `PathAMediaPane` / `PathBWorkspace` shells once a source is picked.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self.path_a_pane: PathAMediaPane | None = None
        self.path_b_workspace: PathBWorkspace | None = None

        self.window = QMainWindow()
        self.window.setWindowTitle("GlyphCue")
        self.window.setStyleSheet(base_stylesheet())

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        layout.addWidget(QLabel("GlyphCue"))
        layout.addWidget(
            QLabel(
                "Open Video for Path A (visual/OCR evidence), or "
                "Open Caption File for Path B (timed caption evidence)."
            )
        )
        self.open_video_button = QPushButton("Open Video…")
        self.open_caption_button = QPushButton("Open Caption File…")
        layout.addWidget(self.open_video_button)
        layout.addWidget(self.open_caption_button)
        self.window.setCentralWidget(central)

        self.open_video_button.clicked.connect(self._on_open_video_clicked)
        self.open_caption_button.clicked.connect(self._on_open_caption_clicked)

    def open_video(self, path: Path) -> PathAMediaPane:
        """Switch from the entry state into a real Path A workflow
        window for `path`, reusing `create_path_a_app`'s own runtime
        wiring (PaddleOcrEngine factory, TrackGroup persistence) so
        production behavior is identical to before this entrypoint
        existed."""
        _app, pane = create_path_a_app(db_path=self._db_path)
        pane.open_video(path)
        self.path_a_pane = pane
        self.window.hide()
        pane.window.show()
        return pane

    def open_caption_file(self, path: Path) -> PathBWorkspace:
        """Switch from the entry state into a real Path B workflow
        window for `path`: import -> normalize (M8's
        `parse_and_reconstruct`) -> QA -> export, with M8's per-event
        import warnings threaded through to the workspace rather than
        silently discarded (ROADMAP M9)."""
        cues, observations_by_id, diagnostics_by_cue_id, import_warnings = parse_and_reconstruct(
            path
        )
        destination = path.with_name(f"{path.stem}.reconstructed{path.suffix}")
        workspace = PathBWorkspace(
            cues,
            observations_by_id,
            path,
            destination,
            diagnostics_by_cue_id=diagnostics_by_cue_id,
            import_warnings=import_warnings,
        )
        self.path_b_workspace = workspace
        self.window.hide()
        workspace.window.show()
        return workspace

    def _on_open_video_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            None, "Open Video", "", "Video files (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if path_str:
            self.open_video(Path(path_str))

    def _on_open_caption_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            None, "Open Caption File", "", "Subtitle files (*.srt *.vtt)"
        )
        if path_str:
            self.open_caption_file(Path(path_str))


def create_app(db_path: Path = DEFAULT_DB_PATH) -> tuple[QApplication, GlyphCueEntry]:
    """Build the QApplication and the production entry state."""
    app = QApplication.instance() or QApplication(sys.argv)
    entry = GlyphCueEntry(db_path=db_path)
    return app, entry


def create_path_a_app(db_path: Path = DEFAULT_DB_PATH) -> tuple[QApplication, PathAMediaPane]:
    """Build the QApplication and the Path A media pane, with
    TrackGroup/ROI and OCR-evidence (Observation) persistence wired in.

    `PaddleOcrEngine` is the V1 default runtime (see
    docs/adr/0001-ocr-runtime-selection.md). It is wired as a factory so
    the live Track Group language selects the engine that is actually
    constructed. The real `paddleocr` import remains deferred until
    the Run OCR Evidence button calls `.initialize()`, so this stays
    safe to construct even when the optional `[ocr]` extra isn't
    installed.

    `PathAMediaPane` is given `db_path` (not a ready-made
    ObservationRepository) so it can open its own connection for
    UI-thread reads, kept separate from the connection the OCR job
    opens on its own worker thread when it runs.

    Only `ocr_engine_factory=PaddleOcrEngine` is wired (Milestone 6):
    `PathAMediaPane` uses it once per configured language, including a
    single-language Track Group. A plain `ocr_engine` remains available
    only to direct callers as a test/injection compatibility fallback.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    conn = connect(db_path)
    track_group_repository = TrackGroupRepository(conn)
    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine_factory=PaddleOcrEngine,
        db_path=db_path,
    )
    return app, pane


def main(db_path: Path | None = None) -> int:
    """Production entrypoint (ROADMAP M9): the shared GlyphCue product
    entry -- Open Video (Path A) or Open Caption File (Path B) from one
    launch screen, not a Path-A-only launcher.

    `db_path` defaults to the real user database (DEFAULT_DB_PATH),
    resolved at call time rather than baked in as a mutable default
    argument, so it can be overridden (e.g. in tests) without relying on
    monkeypatching a module-level constant that a default argument would
    have already captured at import time.
    """
    app, entry = create_app(db_path=db_path or DEFAULT_DB_PATH)
    entry.window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
