from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from glyphcue.ui.design_tokens import Color

_ROLE_COLORS = {
    "clean": Color.SUCCESS,
    "reconstructed": Color.SUCCESS,
    "source": Color.INFO,
    "flagged": Color.WARNING,
    "collision": Color.DANGER,
}


class CompactTimeline(QWidget):
    """DESIGN.md section 49's shared "compact timeline" workbench
    grammar: a read-only temporal strip, not an NLE timeline -- no
    tracks, keyframes, or editing tools.

    Reused identically by both paths with different span data: Path A
    passes Cue spans (colored by whether they carry a real Review
    Priority flag) plus a live playhead; Path B passes source-
    observation / reconstructed-Cue spans for the active Cue, with a
    "collision" role when `PathBDiagnostics.timing_collision` fired.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(28)
        self.duration_seconds: float = 0.0
        self.spans: list[tuple[float, float, str]] = []
        self.playhead_seconds: float | None = None

    def set_data(
        self,
        duration_seconds: float,
        spans: list[tuple[float, float, str]],
        playhead_seconds: float | None = None,
    ) -> None:
        self.duration_seconds = duration_seconds
        self.spans = spans
        self.playhead_seconds = playhead_seconds
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        width, height = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(Color.SURFACE_1))

        if self.duration_seconds <= 0:
            return

        for start, end, role in self.spans:
            x0 = (start / self.duration_seconds) * width
            x1 = (end / self.duration_seconds) * width
            color = QColor(_ROLE_COLORS.get(role, Color.TEXT_MUTED))
            painter.fillRect(QRectF(x0, 3, max(x1 - x0, 2.0), height - 6), color)

        if self.playhead_seconds is not None:
            x = (self.playhead_seconds / self.duration_seconds) * width
            pen = QPen(QColor(Color.ACCENT))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(int(x), 0, int(x), height)
