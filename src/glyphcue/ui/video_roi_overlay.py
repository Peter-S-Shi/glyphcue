from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView, QWidget

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


class VideoRoiView(QGraphicsView):
    """Interactive video ROI viewport & overlay (DESIGN.md section 10 / 10.1).

    Renders video via QGraphicsVideoItem inside a QGraphicsScene with a
    QGraphicsRectItem ROI selection overlay composited directly over the video frames.
    Users can click and drag directly on top of the video to frame-select subtitles.
    Eliminates native Direct3D HWND airspace occlusion on Windows.
    """

    roiChanged = Signal(object)  # emits ROI

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.setStyleSheet("background-color: #000; border: none;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.video_item = QGraphicsVideoItem()
        self._scene.addItem(self.video_item)

        self.roi_item = QGraphicsRectItem()
        pen = QPen(QColor(Color.ACCENT), 2)
        pen.setCosmetic(True)  # width stays 2px regardless of zoom/scale
        self.roi_item.setPen(pen)
        self.roi_item.setBrush(QBrush(QColor(0, 153, 255, 40)))
        self.roi_item.setZValue(10)
        self._scene.addItem(self.roi_item)

        self._roi = ROI(0.0, 0.0, 1.0, 1.0)
        self._video_size = (0.0, 0.0)
        self._drag_start: tuple[float, float] | None = None

        self.video_item.nativeSizeChanged.connect(self._on_native_size_changed)

    @property
    def roi(self) -> ROI:
        return self._roi

    def set_roi(self, roi: ROI) -> None:
        self._roi = roi
        self._update_roi_rect()

    def reset_roi(self) -> None:
        """Resets ROI back to the full frame (0, 0, 1, 1)."""
        full_frame = ROI(0.0, 0.0, 1.0, 1.0)
        self.set_roi(full_frame)
        self.roiChanged.emit(full_frame)

    def set_video_size(self, width: float | int, height: float | int) -> None:
        self._video_size = (float(width), float(height))
        if width > 0 and height > 0:
            self.video_item.setSize(QRectF(0, 0, width, height).size())
            self._scene.setSceneRect(0, 0, width, height)
            self._update_roi_rect()
            self._fit_video()

    def _on_native_size_changed(self, size) -> None:
        if size.width() > 0 and size.height() > 0:
            self.set_video_size(size.width(), size.height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_video()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._fit_video()

    def _fit_video(self) -> None:
        if self._video_size[0] > 0 and self._video_size[1] > 0:
            self.fitInView(
                QRectF(0, 0, self._video_size[0], self._video_size[1]),
                Qt.AspectRatioMode.KeepAspectRatio,
            )

    def _update_roi_rect(self) -> None:
        vw, vh = self._video_size
        if vw > 0 and vh > 0:
            self.roi_item.setRect(
                self._roi.x * vw,
                self._roi.y * vh,
                self._roi.width * vw,
                self._roi.height * vh,
            )
        else:
            self.roi_item.setRect(0, 0, 0, 0)

    def frame_rect(self) -> tuple[float, float, float, float]:
        vw, vh = self._video_size
        return calculate_video_frame_rect(self.width(), self.height(), vw, vh)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._video_size[0] > 0
            and self._video_size[1] > 0
        ):
            pos = event.position()
            self._drag_start = (pos.x(), pos.y())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._video_size[0] > 0
            and self._video_size[1] > 0
        ):
            pos = event.position()
            p1 = self._drag_start
            p2 = (pos.x(), pos.y())
            frame = self.frame_rect()
            self._roi = map_pixels_to_normalized_roi(p1, p2, frame)
            self._update_roi_rect()
            self.roiChanged.emit(self._roi)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._drag_start is not None
            and self._video_size[0] > 0
            and self._video_size[1] > 0
        ):
            pos = event.position()
            p1 = self._drag_start
            p2 = (pos.x(), pos.y())
            self._drag_start = None

            frame = self.frame_rect()
            new_roi = map_pixels_to_normalized_roi(p1, p2, frame)
            if new_roi.width >= 0.005 and new_roi.height >= 0.005:
                self._roi = new_roi
                self._update_roi_rect()
                self.roiChanged.emit(self._roi)
            else:
                self._update_roi_rect()
        super().mouseReleaseEvent(event)


# Alias for backward compatibility
VideoRoiOverlay = VideoRoiView
