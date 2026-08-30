import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp_guard():
    app = QApplication.instance() or QApplication([])
    yield app
