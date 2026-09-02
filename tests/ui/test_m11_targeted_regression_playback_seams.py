"""M11 Targeted Regression -- A-B preview loop / Cue Replay takeover seam.

Seam under test: `PlaybackController`'s public playback surface
(`set_ab_loop`, `play_span`, `pause`, `is_loop_enabled`, `loop_range`)
-- the same seam `tests/ui/test_preview_ab_loop_and_playhead_range_actions.py`
already exercises for the happy path (span runs to completion).

These cover the paths a human actually takes that the happy-path test
does not: a Cue Replay that never reaches its own span end because the
user paused it.
"""

from glyphcue.ui.playback_controller import PlaybackController


def test_manual_pause_during_cue_replay_restores_the_suspended_ab_loop(qapp_guard):
    controller = PlaybackController()
    assert controller.set_ab_loop(0.1, 0.3, enabled=True) is True

    controller.play_span(0.4, 0.8)
    assert controller.is_loop_enabled is False  # suspended for the replay

    # The user pauses mid-replay instead of letting the span finish.
    controller.pause()

    assert controller.is_loop_enabled is True
    assert controller.loop_range == (0.1, 0.3)


def test_manual_pause_during_cue_replay_does_not_leave_a_stale_span_armed(qapp_guard):
    """A span abandoned by a manual pause must not keep the loop's own
    wrap-around suppressed: once the replay is over, crossing the loop's
    B point has to seek back to A again, exactly as it did before the
    replay started."""
    controller = PlaybackController()
    controller.set_ab_loop(0.1, 0.3, enabled=True)
    controller.play_span(0.4, 0.8)

    controller.pause()
    controller.play()

    # Ordinary looped playback crosses B (300ms).
    controller._on_playback_position_changed(350)

    assert controller.position_seconds == 0.1


def test_cue_replay_without_an_active_loop_leaves_the_loop_off_after_a_manual_pause(qapp_guard):
    controller = PlaybackController()
    assert controller.is_loop_enabled is False

    controller.play_span(0.4, 0.8)
    controller.pause()

    assert controller.is_loop_enabled is False
    assert controller.loop_range is None


def test_replaying_a_second_cue_mid_replay_retargets_the_span(qapp_guard):
    """Clicking Replay on another Cue while one replay is still running
    moves the span, and the single completion still hands the loop back."""
    controller = PlaybackController()
    controller.set_ab_loop(0.1, 0.3, enabled=True)

    controller.play_span(0.4, 0.8)
    controller.play_span(1.0, 1.4)
    assert controller.is_loop_enabled is False

    controller._on_position_changed_during_span(1450)

    assert controller.is_loop_enabled is True
    assert controller.loop_range == (0.1, 0.3)
