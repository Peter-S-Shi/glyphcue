from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer

from glyphcue.adapters.ocr_types import OcrRuntimeInfo, OcrTextRegion
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.ocr_invocation_policy import NaiveDenseOcrPolicy
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.provenance import ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.jobs.job import JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository
from tests.support.fake_ocr_engine import FakeOcrEngine

_FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)
_db_counter = 0


def _new_repository(tmp_path: Path) -> ObservationRepository:
    global _db_counter
    _db_counter += 1
    conn = connect(tmp_path / f"db_{_db_counter}.sqlite3")
    return ObservationRepository(conn)


def _write_test_video(path: Path, frames: list[tuple[int, int]]) -> None:
    """Write a synthetic h264 video with explicit per-frame PTS (ms) and
    flat grayscale content, so cheap frame-difference detection has real
    pixel-level signal to react to (not just distinct PTS values)."""
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0
    for pts_ms, gray in frames:
        array = np.full((32, 32, 3), gray, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


class _FinishedWaiter:
    def __init__(self, job, timeout: float = 5.0) -> None:
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


def _run(job) -> None:
    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()


@pytest.fixture
def changing_subtitle_video(tmp_path) -> Path:
    # gray=50 for 3 frames, gray=200 for 2 frames, back to gray=50 for 1
    # frame: 3 real state changes worth confirming (start, change, change).
    path = tmp_path / "changing.mp4"
    _write_test_video(
        path,
        [(0, 50), (100, 50), (200, 50), (300, 200), (400, 200), (500, 50)],
    )
    return path


def _fake_engine(text: str = "hello") -> FakeOcrEngine:
    return FakeOcrEngine(
        regions=[
            OcrTextRegion(
                text=text,
                confidence=0.9,
                language="en",
                geometry=((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0)),
            )
        ],
        runtime_info=OcrRuntimeInfo(
            engine_name="fake", version="1.0", backend="cpu", backend_version="9.9"
        ),
    )


def test_job_produces_observations_with_source_correct_pts(
    qapp_guard, tmp_path, changing_subtitle_video
):
    repository = _new_repository(tmp_path)
    engine = _fake_engine()
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        engine,
        repository,
        PipelineMetrics(),
    )

    _run(job)

    assert job.state is JobState.SUCCEEDED
    observed_pts = sorted(obs.start_time for obs in repository.list_all())
    # Real per-frame PTS (0.0, 0.3, 0.5s), never frame_index/fps.
    assert observed_pts == [0.0, 0.3, 0.5]


def test_job_only_produces_observations_within_the_processing_range(
    qapp_guard, tmp_path, changing_subtitle_video
):
    repository = _new_repository(tmp_path)
    engine = _fake_engine()
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(start_time=0.15, end_time=0.45),
        _FULL_FRAME_ROI,
        engine,
        repository,
        PipelineMetrics(),
    )

    _run(job)

    assert job.state is JobState.SUCCEEDED
    for observation in repository.list_all():
        assert 0.15 <= observation.start_time < 0.45


def test_selective_policy_produces_materially_fewer_ocr_calls_than_dense_baseline(
    qapp_guard, tmp_path
):
    path = tmp_path / "long_static.mp4"
    frames = [(i * 100, 50) for i in range(10)]  # static
    frames += [(i * 100, 200) for i in range(10, 15)]  # one real change
    frames += [(i * 100, 50) for i in range(15, 20)]  # one more real change
    _write_test_video(path, frames)

    selective_metrics = PipelineMetrics()
    selective_job = build_ocr_evidence_job(
        path,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _fake_engine(),
        _new_repository(tmp_path),
        selective_metrics,
    )
    _run(selective_job)

    dense_metrics = PipelineMetrics()
    dense_repository = _new_repository(tmp_path)
    dense_job = build_ocr_evidence_job(
        path,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _fake_engine(),
        dense_repository,
        dense_metrics,
        policy=NaiveDenseOcrPolicy(),
    )
    _run(dense_job)

    assert selective_job.state is JobState.SUCCEEDED
    assert dense_job.state is JobState.SUCCEEDED
    assert selective_metrics.frames_analyzed == 20
    assert dense_metrics.frames_analyzed == 20
    assert dense_metrics.ocr_calls == 20  # naive baseline OCRs every frame
    assert selective_metrics.ocr_calls == 3  # baseline + 2 real changes
    assert selective_metrics.ocr_calls < dense_metrics.ocr_calls
    # Selective still captured meaningful evidence, not nothing.
    assert selective_metrics.observations_created > 0
    assert len(dense_repository.list_all()) == dense_metrics.observations_created


def test_cancelling_the_job_stops_before_the_end_and_keeps_partial_evidence(qapp_guard, tmp_path):
    path = tmp_path / "cancel_target.mp4"
    _write_test_video(path, [(i * 20, 50 + (i % 2) * 150) for i in range(100)])  # 100 frames, alternating

    repository = _new_repository(tmp_path)
    metrics = PipelineMetrics()
    job = build_ocr_evidence_job(
        path, ProcessingRange(), _FULL_FRAME_ROI, _fake_engine(), repository, metrics
    )

    job.start()
    job.request_cancel()
    waiter = _FinishedWaiter(job)
    waiter.wait()

    assert job.state is JobState.CANCELLED
    assert metrics.frames_analyzed < 100
    # Whatever evidence was already found before cancellation stays saved.
    assert len(repository.list_all()) == metrics.observations_created


def test_observation_provenance_preserves_required_evidence_fields(
    qapp_guard, tmp_path, changing_subtitle_video
):
    repository = _new_repository(tmp_path)
    roi = ROI(x=0.1, y=0.2, width=0.5, height=0.3)
    engine = _fake_engine(text="captured text")
    job = build_ocr_evidence_job(
        changing_subtitle_video, ProcessingRange(), roi, engine, repository, PipelineMetrics()
    )

    _run(job)

    observation = repository.list_all()[0]
    assert observation.text == "captured text"
    assert observation.confidence == 0.9
    assert observation.language == "en"
    assert observation.roi == roi
    assert observation.geometry == ((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0))
    assert observation.provenance.kind is ProvenanceKind.OCR_ENGINE
    assert observation.provenance.source == "fake"
    assert observation.provenance.detail["engine_version"] == "1.0"
    assert observation.provenance.detail["backend"] == "cpu"
    assert observation.provenance.detail["backend_version"] == "9.9"
    assert observation.frame_reference is not None
    assert str(changing_subtitle_video) in observation.frame_reference


def test_instrumentation_counts_match_the_real_execution_path(
    qapp_guard, tmp_path, changing_subtitle_video
):
    repository = _new_repository(tmp_path)
    metrics = PipelineMetrics()
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _fake_engine(),
        repository,
        metrics,
    )

    _run(job)

    assert metrics.frames_analyzed == 6
    assert metrics.ocr_calls == 3
    assert metrics.observations_created == len(repository.list_all())
    assert metrics.elapsed_seconds > 0
    assert metrics.ocr_calls_per_minute == pytest.approx(
        metrics.ocr_calls / metrics.elapsed_seconds * 60.0
    )
    assert metrics.effective_processing_speed == pytest.approx(
        metrics.media_seconds_processed / metrics.elapsed_seconds
    )
