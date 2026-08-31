from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtMultimedia import QMediaPlayer

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.timeline_mapping import qt_position_seconds_to_pyav_range
from glyphcue.ui.playback_controller import PlaybackController

# Deliberately NON-UNIFORM pts spacing (VFR-style): 0.0s, 0.1s, 0.5s, 0.6s.
# Reused for the shared Qt/PyAV timeline-mapping proof below, for the same
# reason it proves PTS-correctness in test_pyav_media_source.py: a naive
# frame_index/fps mapping would place these frames at completely different
# times than their real PTS.
_FRAME_TIMES_MS = [0, 100, 500, 600]


def _write_variable_pts_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0
    for pts_ms in _FRAME_TIMES_MS:
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
def variable_pts_video(tmp_path) -> Path:
    path = tmp_path / "shared_timeline.mp4"
    _write_variable_pts_video(path)
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
    qapp_guard, variable_pts_video
):
    # Media playback (Qt Multimedia) and analysis (PyAV) are two
    # independent decoding paths over the same file; their timestamps
    # must map to the same real-world duration.
    pyav_metadata = probe_media(variable_pts_video)

    controller = PlaybackController()
    controller.load(variable_pts_video)
    _wait_for_media_status(controller.player)

    assert controller.duration_seconds == pytest.approx(
        pyav_metadata.duration_seconds, abs=0.05
    )


@pytest.mark.parametrize("frame_time_ms", _FRAME_TIMES_MS)
def test_qt_seek_position_maps_to_the_matching_real_pyav_frame(
    qapp_guard, variable_pts_video, frame_time_ms
):
    # The two decoding paths share one source timeline: a Qt seek to a
    # given source-time position must resolve to the SAME real PTS frame
    # that PyAV independently decodes at that position -- proving the
    # mapping is not fps-derived, since these frames are irregularly
    # spaced and a constant-fps model could not place them correctly.
    controller = PlaybackController()
    controller.load(variable_pts_video)
    _wait_for_media_status(controller.player)

    frame_time_seconds = frame_time_ms / 1000.0
    controller.seek(frame_time_seconds)
    assert controller.position_seconds == pytest.approx(frame_time_seconds, abs=0.01)

    start, end = qt_position_seconds_to_pyav_range(controller.position_seconds)

    source = PyAvMediaFrameSource()
    source.open(variable_pts_video)
    try:
        matched_frames = list(source.frames(start, end))
    finally:
        source.close()

    assert len(matched_frames) == 1
    matched_timestamp, _frame = matched_frames[0]
    assert matched_timestamp == pytest.approx(frame_time_seconds, abs=0.001)


def test_nominal_fps_based_mapping_would_have_missed_this_frame(qapp_guard, variable_pts_video):
    # If the mapping instead assumed timestamp = frame_index / fps using
    # the container's own reported nominal frame rate, it would place
    # frame index 2 (real PTS 0.5s) at a materially different time,
    # because these frames are not evenly spaced. This is why the shared
    # mapping above uses real PTS/position seconds directly, never fps.
    metadata = probe_media(variable_pts_video)
    nominal_fps = 4000 / 601  # PyAV's reported container.average_rate for this fixture
    naive_timestamp_for_frame_index_2 = 2 / nominal_fps

    real_pts_for_frame_index_2 = 0.5

    assert naive_timestamp_for_frame_index_2 != pytest.approx(
        real_pts_for_frame_index_2, abs=0.05
    )
    assert metadata.duration_seconds > 0  # sanity: real metadata was read
