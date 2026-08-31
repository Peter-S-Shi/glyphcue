from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from glyphcue.domain.roi import ROI
from glyphcue.ui.design_tokens import Color


class RoiVisualization(QWidget):
    """DESIGN.md section 10 / 10.1: the active ROI must be visually
    distinguishable, not only four numeric spin-box values. This is a
    minimal frame-outline diagram with the ROI fraction drawn to
    scale -- not a live pixel overlay composited onto `QVideoWidget`
    (whose native surface makes reliable transparent compositing a
    real engineering risk, especially under the offscreen Qt platform
    CI runs under), but a real, always-visible visual representation
    of the same ROI, kept live via `set_roi`."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(60)
        self.roi = ROI(0.0, 0.0, 1.0, 1.0)

    def set_roi(self, roi: ROI) -> None:
        self.roi = roi
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        margin = 4.0
        frame_rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)

        frame_pen = QPen(QColor(Color.BORDER_MEDIUM))
        frame_pen.setWidth(1)
        painter.setPen(frame_pen)
        painter.drawRect(frame_rect)

        roi_rect = QRectF(
            frame_rect.x() + self.roi.x * frame_rect.width(),
            frame_rect.y() + self.roi.y * frame_rect.height(),
            self.roi.width * frame_rect.width(),
            self.roi.height * frame_rect.height(),
        )
        roi_pen = QPen(QColor(Color.ACCENT))
        roi_pen.setWidth(2)
        painter.setPen(roi_pen)
        painter.drawRect(roi_rect)
