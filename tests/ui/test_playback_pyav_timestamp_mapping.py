from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtMultimedia import QMediaPlayer

from glyphcue.adapters.pyav_media_source import probe_media
from glyphcue.ui.playback_controller import PlaybackController


def _write_test_video(path: Path, duration_ms: int = 800) -> None:
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
def shared_video(tmp_path) -> Path:
    path = tmp_path / "shared.mp4"
    _write_test_video(path)
    return path


def _wait_for_media_status(player: QMediaPlayer, timeout_ms: int = 3000) -> None:
    if player.mediaStatus() in (
        QMediaPlayer.MediaStatus.LoadedMedia,
        QMediaPlayer.MediaStatus.InvalidMedia,
    ):
        return
    loop = QEventLoop()
    player.mediaStatusChanged.connect(
        lambda status: loop.quit()
        if status
        in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.InvalidMedia)
        else None
    )
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()


def test_qt_playback_and_pyav_analysis_agree_on_duration_for_the_same_source(
    qapp_guard, shared_video
):
    # Media playback (Qt Multimedia) and analysis (PyAV) are two
    # independent decoding paths over the same file; their timestamps
    # must map to the same real-world duration.
    pyav_metadata = probe_media(shared_video)

    controller = PlaybackController()
    controller.load(shared_video)
    _wait_for_media_status(controller.player)

    assert controller.duration_seconds == pytest.approx(
        pyav_metadata.duration_seconds, abs=0.05
    )
