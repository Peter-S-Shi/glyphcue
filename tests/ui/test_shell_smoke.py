from PySide6.QtWidgets import QApplication, QSplitter

from glyphcue.persistence.database import connect
from glyphcue.persistence.repository import CueRepository
from glyphcue.ui.main_window import MainWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_main_window_constructs_and_shows(qapp_guard):
    window = MainWindow()

    assert window.windowTitle() == "GlyphCue"


def test_main_window_has_three_pane_splitter(qapp_guard):
    window = MainWindow()

    splitter = window.centralWidget()
    assert isinstance(splitter, QSplitter)
    assert splitter.count() == 3


def test_main_window_accepts_injected_repository(qapp_guard, tmp_path):
    conn = connect(tmp_path / "glyphcue.sqlite3")
    repository = CueRepository(conn)

    window = MainWindow(cue_repository=repository)

    assert window.cue_repository is repository


def test_main_window_shows_local_first_status(qapp_guard):
    window = MainWindow()

    assert "Local-first" in window.statusBar().currentMessage()
