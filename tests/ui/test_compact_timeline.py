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
