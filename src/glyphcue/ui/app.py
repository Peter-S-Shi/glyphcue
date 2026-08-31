from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.persistence.database import connect
from glyphcue.persistence.repository import CueRepository
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.main_window import MainWindow
from glyphcue.ui.path_a_media_pane import PathAMediaPane

DEFAULT_DB_PATH = Path.home() / ".glyphcue" / "glyphcue.sqlite3"


def create_app(db_path: Path = DEFAULT_DB_PATH) -> tuple[QApplication, MainWindow]:
    """Build the QApplication and MainWindow with persistence wired in."""
    app = QApplication.instance() or QApplication(sys.argv)
    conn = connect(db_path)
    repository = CueRepository(conn)
    window = MainWindow(cue_repository=repository)
    return app, window


def create_path_a_app(db_path: Path = DEFAULT_DB_PATH) -> tuple[QApplication, PathAMediaPane]:
    """Build the QApplication and the Path A media pane, with
    TrackGroup/ROI and OCR-evidence (Observation) persistence wired in.

    `PaddleOcrEngine` is the V1 default runtime (see
    docs/adr/0001-ocr-runtime-selection.md). Constructing it here does
    not import the real `paddleocr` package -- that import is deferred
    until the Run OCR Evidence button actually calls `.initialize()` --
    so this stays safe to construct even when the optional `[ocr]`
    extra isn't installed.

    `PathAMediaPane` is given `db_path` (not a ready-made
    ObservationRepository) so it can open its own connection for
    UI-thread reads, kept separate from the connection the OCR job
    opens on its own worker thread when it runs.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    conn = connect(db_path)
    track_group_repository = TrackGroupRepository(conn)
    pane = PathAMediaPane(track_group_repository, ocr_engine=PaddleOcrEngine(), db_path=db_path)
    return app, pane


def main(db_path: Path | None = None) -> int:
    """Production entrypoint: the current Path A workflow.

    `db_path` defaults to the real user database (DEFAULT_DB_PATH),
    resolved at call time rather than baked in as a mutable default
    argument, so it can be overridden (e.g. in tests) without relying on
    monkeypatching a module-level constant that a default argument would
    have already captured at import time.
    """
    app, pane = create_path_a_app(db_path=db_path or DEFAULT_DB_PATH)
    pane.window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
