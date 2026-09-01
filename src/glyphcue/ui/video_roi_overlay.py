from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from glyphcue.domain.roi import ROI
from glyphcue.ui.design_tokens import Color


def calculate_video_frame_rect(
    widget_width: float, widget_height: float, video_width: float, video_height: float
) -> tuple[float, float, float, float]:
    """Computes the active video render rectangle (offset_x, offset_y, width, height)
    within the viewport widget, accounting for Qt.KeepAspectRatio letterboxing/pillarboxing.
    """
    if widget_width <= 0 or widget_height <= 0 or video_width <= 0 or video_height <= 0:
        return (0.0, 0.0, float(max(0.0, widget_width)), float(max(0.0, widget_height)))

    widget_aspect = widget_width / widget_height
    video_aspect = video_width / video_height

    if widget_aspect > video_aspect:
        # Pillarbox (black bars on left & right)
        rendered_h = float(widget_height)
        rendered_w = widget_height * video_aspect
        offset_x = (widget_width - rendered_w) / 2.0
        offset_y = 0.0
    else:
        # Letterbox (black bars on top & bottom)
        rendered_w = float(widget_width)
        rendered_h = widget_width / video_aspect
        offset_x = 0.0
        offset_y = (widget_height - rendered_h) / 2.0

    return (offset_x, offset_y, rendered_w, rendered_h)


def map_pixels_to_normalized_roi(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    frame_rect: tuple[float, float, float, float],
) -> ROI:
    """Converts widget pixel drag points (point_a, point_b) to normalized ROI [0.0, 1.0],
    clamped to the active video frame boundaries so letterbox bars are not included.
    """
    offset_x, offset_y, frame_w, frame_h = frame_rect
    if frame_w <= 0 or frame_h <= 0:
        return ROI(0.0, 0.0, 1.0, 1.0)

    x1, y1 = point_a
    x2, y2 = point_b

    x_min = min(x1, x2)
    x_max = max(x1, x2)
    y_min = min(y1, y2)
    y_max = max(y1, y2)

    # Clamp to frame rectangle bounds
    clamped_x_min = max(offset_x, min(offset_x + frame_w, x_min))
    clamped_x_max = max(offset_x, min(offset_x + frame_w, x_max))
    clamped_y_min = max(offset_y, min(offset_y + frame_h, y_min))
    clamped_y_max = max(offset_y, min(offset_y + frame_h, y_max))

    norm_x = (clamped_x_min - offset_x) / frame_w
    norm_y = (clamped_y_min - offset_y) / frame_h
    norm_w = (clamped_x_max - clamped_x_min) / frame_w
    norm_h = (clamped_y_max - clamped_y_min) / frame_h

    return ROI(
        x=round(norm_x, 4),
        y=round(norm_y, 4),
        width=round(norm_w, 4),
        height=round(norm_h, 4),
    )


def map_normalized_roi_to_pixels(
    roi: ROI, frame_rect: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """Maps normalized ROI [0.0, 1.0] to widget pixel coordinates (x, y, width, height)
    based on the active video frame rectangle.
    """
    offset_x, offset_y, frame_w, frame_h = frame_rect
    return (
        offset_x + roi.x * frame_w,
        offset_y + roi.y * frame_h,
        roi.width * frame_w,
        roi.height * frame_h,
    )


class VideoRoiOverlay(QWidget):
    """Interactive video ROI overlay (DESIGN.md section 10 / 10.1).

    Sits directly on top of the video viewport, letting users drag a rectangular
    box over the subtitle area. Automatically translates mouse coordinates to
    normalized [0.0, 1.0] ROI coordinates against the real video aspect ratio,
    accounting for letterboxing/pillarboxing.
    """

    roiChanged = Signal(object)  # emits ROI

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._roi = ROI(0.0, 0.0, 1.0, 1.0)
        self._video_size = (0, 0)
        self._drag_start: QPointF | None = None
        self._drag_current: QPointF | None = None

    @property
    def roi(self) -> ROI:
        return self._roi

    def set_roi(self, roi: ROI) -> None:
        self._roi = roi
        self.update()

    def reset_roi(self) -> None:
        """Resets ROI back to the full frame (0, 0, 1, 1)."""
        full_frame = ROI(0.0, 0.0, 1.0, 1.0)
        self.set_roi(full_frame)
        self.roiChanged.emit(full_frame)

    def set_video_size(self, width: int, height: int) -> None:
        self._video_size = (width, height)
        self.update()

    def frame_rect(self) -> tuple[float, float, float, float]:
        vw, vh = self._video_size
        return calculate_video_frame_rect(self.width(), self.height(), vw, vh)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position()
            self._drag_current = event.position()
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is not None:
            self._drag_current = event.position()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            p1 = (self._drag_start.x(), self._drag_start.y())
            p2 = (event.position().x(), event.position().y())
            self._drag_start = None
            self._drag_current = None

            frame = self.frame_rect()
            new_roi = map_pixels_to_normalized_roi(p1, p2, frame)

            # Minimum drag threshold: if width and height are negligible (< 0.005),
            # treat as an accidental click and do not replace the existing ROI.
            if new_roi.width >= 0.005 and new_roi.height >= 0.005:
                self._roi = new_roi
                self.roiChanged.emit(new_roi)
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        frame = self.frame_rect()
        offset_x, offset_y, frame_w, frame_h = frame
        frame_qrect = QRectF(offset_x, offset_y, frame_w, frame_h)

        if self._drag_start is not None and self._drag_current is not None:
            p1 = self._drag_start
            p2 = self._drag_current
            raw_rect = QRectF(
                min(p1.x(), p2.x()),
                min(p1.y(), p2.y()),
                abs(p2.x() - p1.x()),
                abs(p2.y() - p1.y()),
            )
            rect = raw_rect.intersected(frame_qrect)
        else:
            px, py, pw, ph = map_normalized_roi_to_pixels(self._roi, frame)
            rect = QRectF(px, py, pw, ph)

        if not rect.isEmpty():
            # Clear blue boundary (DESIGN.md 10.1) with semi-transparent highlight fill
            pen = QPen(QColor(Color.ACCENT))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(0, 153, 255, 40)))
            painter.drawRect(rect)
