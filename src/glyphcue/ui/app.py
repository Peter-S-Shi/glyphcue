from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from glyphcue.persistence.database import connect
from glyphcue.persistence.repository import CueRepository
from glyphcue.ui.main_window import MainWindow

DEFAULT_DB_PATH = Path.home() / ".glyphcue" / "glyphcue.sqlite3"


def create_app(db_path: Path = DEFAULT_DB_PATH) -> tuple[QApplication, MainWindow]:
    """Build the QApplication and MainWindow with persistence wired in."""
    app = QApplication.instance() or QApplication(sys.argv)
    conn = connect(db_path)
    repository = CueRepository(conn)
    window = MainWindow(cue_repository=repository)
    return app, window


def main() -> int:
    app, window = create_app()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
