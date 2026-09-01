from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtMultimedia import QMediaPlayer

from glyphcue.ui.playback_controller import PlaybackController


def _write_test_video(path: Path, duration_ms: int = 600) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, duration_ms, 100):
        array = np.full((32, 32, 3), 100, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


@pytest.fixture
def test_video(tmp_path) -> Path:
    path = tmp_path / "playback.mp4"
    _write_test_video(path)
    return path


def _wait_for_media_status(player: QMediaPlayer, timeout_ms: int = 3000) -> None:
    if player.mediaStatus() in (
        QMediaPlayer.MediaStatus.LoadedMedia,
        QMediaPlayer.MediaStatus.InvalidMedia,
    ):
        return
    loop = QEventLoop()

    def on_status_changed(status):
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
        ):
            loop.quit()

    player.mediaStatusChanged.connect(on_status_changed)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()


def test_load_sets_the_media_source_and_prerolls_paused_state(qapp_guard, test_video):
    controller = PlaybackController()

    controller.load(test_video)

    assert Path(controller.player.source().toLocalFile()) == test_video
    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PausedState
    assert controller.position_seconds == pytest.approx(0.0, abs=0.01)


def test_play_and_pause_update_playback_state(qapp_guard, test_video):
    controller = PlaybackController()
    controller.load(test_video)
    _wait_for_media_status(controller.player)

    controller.play()
    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    controller.pause()
    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PausedState


def test_toggle_play_pause_plays_when_paused_and_pauses_when_playing(qapp_guard, test_video):
    controller = PlaybackController()
    controller.load(test_video)
    _wait_for_media_status(controller.player)

    controller.toggle_play_pause()
    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    controller.toggle_play_pause()
    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PausedState


def test_seek_sets_position_from_seconds(qapp_guard, test_video):
    controller = PlaybackController()
    controller.load(test_video)
    _wait_for_media_status(controller.player)

    controller.seek(0.3)

    assert controller.position_seconds == pytest.approx(0.3, abs=0.01)


def test_play_span_seeks_to_the_start_and_plays(qapp_guard, test_video):
    controller = PlaybackController()
    controller.load(test_video)
    _wait_for_media_status(controller.player)

    controller.play_span(0.2, 0.5)

    assert controller.position_seconds == pytest.approx(0.2, abs=0.01)
    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState


def test_play_span_pauses_once_position_reaches_the_end(qapp_guard, test_video):
    controller = PlaybackController()
    controller.load(test_video)
    _wait_for_media_status(controller.player)

    controller.play_span(0.0, 0.3)
    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # Simulate playback reaching the span's end position.
    controller.player.setPosition(300)

    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PausedState


def test_play_span_does_not_pause_early_before_the_end_is_reached(qapp_guard, test_video):
    controller = PlaybackController()
    controller.load(test_video)
    _wait_for_media_status(controller.player)

    controller.play_span(0.0, 0.3)
    controller.player.setPosition(150)

    assert controller.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
