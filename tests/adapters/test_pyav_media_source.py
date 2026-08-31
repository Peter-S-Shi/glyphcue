from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media

# Deliberately NON-UNIFORM pts spacing (a VFR-style fixture): frames land at
# 0.0s, 0.1s, 0.5s, 0.6s -- nothing close to a constant frame interval. A
# naive `timestamp = frame_index / fps` implementation would place frame
# index 2 at 2 * (1/6.66) =~ 0.30s, nowhere near the real 0.5s.
_FRAME_TIMES_MS = [0, 100, 500, 600]
_FRAME_GRAY_LEVELS = [50, 100, 150, 200]
_WIDTH = 32
_HEIGHT = 32


def _write_variable_pts_fixture(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width = _WIDTH
    stream.height = _HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0

    for pts_ms, gray_level in zip(_FRAME_TIMES_MS, _FRAME_GRAY_LEVELS):
        array = np.full((_HEIGHT, _WIDTH, 3), gray_level, dtype=np.uint8)
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
    path = tmp_path / "variable_pts.mp4"
    _write_variable_pts_fixture(path)
    return path


def test_probe_media_reports_duration_and_dimensions(variable_pts_video):
    metadata = probe_media(variable_pts_video)

    assert metadata.width == _WIDTH
    assert metadata.height == _HEIGHT
    assert metadata.duration_seconds == pytest.approx(0.601, abs=0.01)


def test_frame_timestamps_match_real_pts_not_frame_index_over_fps(variable_pts_video):
    source = PyAvMediaFrameSource()
    source.open(variable_pts_video)
    try:
        decoded = list(source.frames(0.0, 10.0))
    finally:
        source.close()

    actual_timestamps = [timestamp for timestamp, _frame in decoded]
    expected_timestamps = [ms / 1000.0 for ms in _FRAME_TIMES_MS]
    assert actual_timestamps == pytest.approx(expected_timestamps, abs=0.001)

    # The naive universal-time-model formula would place frame index 2 at a
    # completely different timestamp than its real PTS -- prove our result
    # is NOT that wrong value.
    nominal_fps = 4000 / 601  # what PyAV reports as the container's average_rate
    naive_timestamp_for_index_2 = 2 / nominal_fps
    assert actual_timestamps[2] != pytest.approx(naive_timestamp_for_index_2, abs=0.01)


def test_frames_returns_numpy_arrays(variable_pts_video):
    source = PyAvMediaFrameSource()
    source.open(variable_pts_video)
    try:
        _timestamp, frame = next(iter(source.frames(0.0, 10.0)))
    finally:
        source.close()

    assert isinstance(frame, np.ndarray)
    assert frame.shape == (_HEIGHT, _WIDTH, 3)


def test_selected_range_decoding_excludes_frames_outside_the_range(variable_pts_video):
    source = PyAvMediaFrameSource()
    source.open(variable_pts_video)
    try:
        decoded = list(source.frames(0.4, 0.6))
    finally:
        source.close()

    timestamps = [timestamp for timestamp, _frame in decoded]
    assert timestamps == [0.5]


def test_selected_range_decoding_preserves_absolute_source_timeline(variable_pts_video):
    # Preserve source timeline by default: a mid-file range's timestamps
    # remain absolute (relative to the whole source), not renumbered
    # relative to the start of the selection.
    source = PyAvMediaFrameSource()
    source.open(variable_pts_video)
    try:
        decoded = list(source.frames(0.5, 10.0))
    finally:
        source.close()

    timestamps = [timestamp for timestamp, _frame in decoded]
    assert timestamps == pytest.approx([0.5, 0.6], abs=0.001)
