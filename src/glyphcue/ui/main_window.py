from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QSplitter, QVBoxLayout, QWidget

from glyphcue.persistence.repository import CueRepository
from glyphcue.ui.design_tokens import Spacing, base_stylesheet


def _placeholder_pane(title: str, subtitle: str) -> QWidget:
    """A structural placeholder for a shell region.

    Milestone 0 proves the three-pane shell can exist; it does not
    implement Path A/B evidence, QA, or export content (see ROADMAP.md
    Milestone 0 non-goals).
    """
    pane = QWidget()
    pane.setObjectName(title.replace(" ", ""))
    label = QLabel(f"{title}\n\n{subtitle}")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)

    layout = QVBoxLayout(pane)
    layout.setContentsMargins(
        Spacing.PANEL_MAJOR,
        Spacing.PANEL_MAJOR,
        Spacing.PANEL_MAJOR,
        Spacing.PANEL_MAJOR,
    )
    layout.addWidget(label)
    return pane


class MainWindow(QMainWindow):
    """The frozen three-pane GlyphCue shell (DESIGN.md section 6).

    Structure + Queue | Primary Evidence Workspace | Reconstruction QA
    over a footer status region. Shared services (e.g. a CueRepository)
    are injected via the constructor rather than constructed globally.
    """

    def __init__(
        self,
        cue_repository: CueRepository | None = None,
        left_pane: QWidget | None = None,
        center_pane: QWidget | None = None,
        right_pane: QWidget | None = None,
    ) -> None:
        super().__init__()
        self._cue_repository = cue_repository

        self.setWindowTitle("GlyphCue")
        self.setStyleSheet(base_stylesheet())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = left_pane or _placeholder_pane("Structure + Queue", "Left pane — reconstruction queue")
        center = center_pane or _placeholder_pane("Primary Evidence Workspace", "Center pane — Path A/B evidence")
        right = right_pane or _placeholder_pane("Reconstruction QA", "Right pane — QA + supporting evidence")

        left.setMinimumWidth(260)
        center.setMinimumWidth(400)
        right.setMinimumWidth(320)

        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)

        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        splitter.setSizes([280, 640, 360])

        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Local-first · Idle")

    @property
    def cue_repository(self) -> CueRepository | None:
        return self._cue_repository
