from __future__ import annotations

from pathlib import Path

from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from glyphcue.ui.design_tokens import Spacing
from glyphcue.ui.main_window import MainWindow
from glyphcue.ui.playback_controller import PlaybackController


class PathAMediaPane:
    """Wires human playback (Milestone 2 scope: Play/Pause, seek) into
    the frozen three-pane shell's center pane.

    This is the media-systems foundation only -- no ROI overlay, no
    evidence workspace, no OCR. Those belong to later milestones.
    """

    def __init__(self, video_path: Path) -> None:
        self.controller = PlaybackController()
        self.video_widget = QVideoWidget()
        self.controller.set_video_output(self.video_widget)
        self.controller.load(video_path)

        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.play_button.clicked.connect(self.controller.play)
        self.pause_button.clicked.connect(self.controller.pause)

        center_pane = QWidget()
        layout = QVBoxLayout(center_pane)
        layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        layout.addWidget(self.video_widget)
        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.pause_button)
        layout.addLayout(controls)

        self.window = MainWindow(center_pane=center_pane)
