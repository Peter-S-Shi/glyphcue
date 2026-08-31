from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository
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
    """
    app = QApplication.instance() or QApplication(sys.argv)
    conn = connect(db_path)
    track_group_repository = TrackGroupRepository(conn)
    observation_repository = ObservationRepository(conn)
    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine=PaddleOcrEngine(),
        observation_repository=observation_repository,
    )
    return app, pane


def main(db_path: Path | None = None) -> int:
    """Production entrypoint: the M2 minimal Path A workflow.

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
