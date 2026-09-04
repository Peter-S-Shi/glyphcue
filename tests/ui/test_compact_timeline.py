from glyphcue.ui.compact_timeline import CompactTimeline


def test_default_timeline_has_zero_duration_and_no_spans(qapp_guard):
    widget = CompactTimeline()

    assert widget.duration_seconds == 0.0
    assert widget.spans == []
    assert widget.playhead_seconds is None


def test_set_data_updates_the_public_state(qapp_guard):
    widget = CompactTimeline()

    widget.set_data(
        duration_seconds=10.0,
        spans=[(0.0, 2.0, "clean"), (2.0, 4.0, "flagged")],
        playhead_seconds=3.5,
    )

    assert widget.duration_seconds == 10.0
    assert widget.spans == [(0.0, 2.0, "clean"), (2.0, 4.0, "flagged")]
    assert widget.playhead_seconds == 3.5


def test_paints_without_crashing_at_a_real_size(qapp_guard):
    widget = CompactTimeline()
    widget.set_data(
        duration_seconds=10.0,
        spans=[(0.0, 2.0, "clean"), (2.0, 4.0, "flagged"), (4.0, 6.0, "collision")],
        playhead_seconds=5.0,
    )
    widget.resize(300, 32)

    widget.repaint()


def test_paints_without_crashing_with_zero_duration(qapp_guard):
    # A degenerate/empty state (nothing loaded yet) must not divide by
    # zero or otherwise crash the paint pass.
    widget = CompactTimeline()
    widget.resize(300, 32)

    widget.repaint()


def test_last_processed_end_marker_updates_and_paints(qapp_guard):
    widget = CompactTimeline()
    widget.set_data(
        duration_seconds=100.0,
        spans=[(0.0, 50.0, "clean")],
        playhead_seconds=25.0,
    )
    widget.resize(400, 32)
    widget.set_last_processed_end(50.0)

    assert widget.last_processed_end == 50.0
    widget.repaint()


def test_mouse_click_emits_seek_requested(qapp_guard):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    widget = CompactTimeline()
    widget.set_data(duration_seconds=100.0, spans=[])
    widget.resize(200, 30)

    received: list[float] = []
    widget.seek_requested.connect(received.append)

    # Simulate mouse click at x=100 (50% of 200 width) -> 50.0s
    pos = QPointF(100.0, 15.0)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pos,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)

    assert len(received) == 1
    assert abs(received[0] - 50.0) < 0.1

