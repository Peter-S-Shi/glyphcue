from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

from glyphcue.ui.path_a_media_pane import PathAMediaPane


def _write_test_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, 500, 100):
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
    path = tmp_path / "pane.mp4"
    _write_test_video(path)
    return path


def test_pane_embeds_a_video_widget_in_the_frozen_shell(qapp_guard, test_video):
    pane = PathAMediaPane(test_video)

    assert isinstance(pane.video_widget, QVideoWidget)
    assert pane.window.centralWidget().count() == 3


def test_play_button_plays_and_pause_button_pauses(qapp_guard, test_video):
    pane = PathAMediaPane(test_video)

    pane.play_button.click()
    assert pane.controller.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    pane.pause_button.click()
    assert pane.controller.player.playbackState() == QMediaPlayer.PlaybackState.PausedState


def test_pane_loads_the_given_video_path(qapp_guard, test_video):
    pane = PathAMediaPane(test_video)

    assert Path(pane.controller.player.source().toLocalFile()) == test_video
