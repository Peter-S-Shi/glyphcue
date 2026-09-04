import pytest
from PySide6.QtCore import QPointF, QRectF, Qt

from glyphcue.domain.roi import ROI
from glyphcue.ui.video_roi_overlay import (
    VideoRoiOverlay,
    calculate_video_frame_rect,
    map_normalized_roi_to_pixels,
    map_pixels_to_normalized_roi,
)


def test_calculate_video_frame_rect_letterbox():
    # 1920x1080 (16:9) video in 800x600 (4:3) widget -> letterbox bars top & bottom
    offset_x, offset_y, rendered_w, rendered_h = calculate_video_frame_rect(800, 600, 1920, 1080)
    assert offset_x == 0.0
    assert offset_y == 75.0
    assert rendered_w == 800.0
    assert rendered_h == 450.0


def test_calculate_video_frame_rect_pillarbox():
    # 1920x1080 (16:9) video in 1200x400 (3:1) widget -> pillarbox bars left & right
    offset_x, offset_y, rendered_w, rendered_h = calculate_video_frame_rect(1200, 400, 1920, 1080)
    assert offset_x == pytest.approx(244.4444, abs=0.01)
    assert offset_y == 0.0
    assert rendered_w == pytest.approx(711.1111, abs=0.01)
    assert rendered_h == 400.0


def test_calculate_video_frame_rect_fallback_on_zero_dimensions():
    offset_x, offset_y, rendered_w, rendered_h = calculate_video_frame_rect(500, 300, 0, 0)
    assert (offset_x, offset_y, rendered_w, rendered_h) == (0.0, 0.0, 500.0, 300.0)


def test_map_pixels_to_normalized_roi_standard_drag():
    # Frame is at (100, 50) with size (400, 200)
    frame_rect = (100.0, 50.0, 400.0, 200.0)
    p1 = (200.0, 100.0)
    p2 = (300.0, 150.0)
    roi = map_pixels_to_normalized_roi(p1, p2, frame_rect)
    assert roi == ROI(x=0.25, y=0.25, width=0.25, height=0.25)


def test_map_pixels_to_normalized_roi_inverted_drag():
    # Drag backwards from bottom-right (300, 150) to top-left (200, 100)
    frame_rect = (100.0, 50.0, 400.0, 200.0)
    p1 = (300.0, 150.0)
    p2 = (200.0, 100.0)
    roi = map_pixels_to_normalized_roi(p1, p2, frame_rect)
    assert roi == ROI(x=0.25, y=0.25, width=0.25, height=0.25)


def test_map_pixels_to_normalized_roi_clamps_to_video_frame():
    # Frame is at (100, 50) with size (400, 200). Drag starts in left pillarbox (-50, 20) and ends beyond right (600, 300)
    frame_rect = (100.0, 50.0, 400.0, 200.0)
    p1 = (50.0, 20.0)
    p2 = (600.0, 300.0)
    roi = map_pixels_to_normalized_roi(p1, p2, frame_rect)
    assert roi == ROI(x=0.0, y=0.0, width=1.0, height=1.0)


def test_map_normalized_roi_to_pixels():
    frame_rect = (100.0, 50.0, 400.0, 200.0)
    roi = ROI(x=0.1, y=0.2, width=0.5, height=0.4)
    x, y, w, h = map_normalized_roi_to_pixels(roi, frame_rect)
    assert x == 140.0
    assert y == 90.0
    assert w == 200.0
    assert h == 80.0


def test_video_roi_overlay_reset_roi_resets_and_emits_signal(qapp_guard):
    overlay = VideoRoiOverlay()
    overlay.set_roi(ROI(0.1, 0.2, 0.3, 0.4))
    emitted = []
    overlay.roiChanged.connect(emitted.append)

    overlay.reset_roi()

    assert overlay.roi == ROI(0.0, 0.0, 1.0, 1.0)
    assert emitted == [ROI(0.0, 0.0, 1.0, 1.0)]


def test_video_roi_overlay_drag_updates_roi_and_emits_signal(qapp_guard):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QMouseEvent

    overlay = VideoRoiOverlay()
    overlay.resize(800, 600)
    overlay.set_video_size(800, 600)  # perfect 1:1 fit

    emitted = []
    overlay.roiChanged.connect(emitted.append)

    # Press at (100, 100)
    press_event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(100.0, 100.0),
        QPointF(100.0, 100.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(press_event)

    # Release at (500, 400)
    release_event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(500.0, 400.0),
        QPointF(500.0, 400.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseReleaseEvent(release_event)

    assert overlay.roi.x == pytest.approx(0.125, abs=0.001)
    assert overlay.roi.y == pytest.approx(0.1667, abs=0.001)
    assert overlay.roi.width == pytest.approx(0.5, abs=0.001)
    assert overlay.roi.height == pytest.approx(0.5, abs=0.001)
    assert len(emitted) == 1
    assert emitted[0].width == pytest.approx(0.5, abs=0.001)
