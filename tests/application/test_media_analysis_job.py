from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer

from glyphcue.application.media_analysis_job import build_media_analysis_job
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.jobs.job import JobState


def _write_test_video(path: Path, frame_times_ms: list[int]) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0
    for pts_ms in frame_times_ms:
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
def analysis_video(tmp_path) -> Path:
    path = tmp_path / "analysis.mp4"
    _write_test_video(path, [0, 100, 200, 300, 400, 500])
    return path


class _FinishedWaiter:
    def __init__(self, job, timeout: float = 3.0) -> None:
        self._job = job
        self._loop = QEventLoop()
        job.finished.connect(self._loop.quit)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._loop.quit)
        self._timer.start(int(timeout * 1000))

    def wait(self) -> None:
        self._loop.exec()
        self._job.wait(timeout=0.5)


def test_whole_media_analysis_job_decodes_every_frame_and_succeeds(qapp_guard, analysis_video):
    reported = []
    job = build_media_analysis_job(analysis_video, ProcessingRange())
    job.progress.connect(lambda phase, processed, total: reported.append((phase, processed, total)))

    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()

    assert job.state is JobState.SUCCEEDED
    assert [processed for _phase, processed, _total in reported] == [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    assert all(phase == "decoding" for phase, _p, _t in reported)


def test_selected_range_analysis_job_only_decodes_frames_in_range(qapp_guard, analysis_video):
    reported = []
    job = build_media_analysis_job(analysis_video, ProcessingRange(start_time=0.2, end_time=0.5))
    job.progress.connect(lambda phase, processed, total: reported.append(processed))

    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()

    assert job.state is JobState.SUCCEEDED
    assert reported == [0.2, 0.3, 0.4]


def test_cancelling_a_media_analysis_job_stops_before_the_end(qapp_guard, tmp_path):
    # A longer fixture so cancellation has room to land mid-decode.
    path = tmp_path / "long_analysis.mp4"
    _write_test_video(path, list(range(0, 2000, 20)))  # 100 frames, 20ms apart

    reported = []
    job = build_media_analysis_job(path, ProcessingRange())
    job.progress.connect(lambda phase, processed, total: reported.append(processed))

    waiter = _FinishedWaiter(job)
    job.start()
    job.request_cancel()
    waiter.wait()

    assert job.state is JobState.CANCELLED
    assert len(reported) < 100
