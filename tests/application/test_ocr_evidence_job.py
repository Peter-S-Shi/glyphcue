import uuid
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


def _new_db_path(tmp_path: Path) -> Path:
    global _db_counter
    _db_counter += 1
    return tmp_path / f"db_{_db_counter}.sqlite3"


def _read_repository(db_path: Path) -> ObservationRepository:
    # A fresh connection on the calling (test) thread, separate from
    # whatever connection the job opened on its own worker thread --
    # see tests/persistence/test_database.py for the connection-
    # separation contract this relies on.
    return ObservationRepository(connect(db_path))


def _new_run_id() -> str:
    return str(uuid.uuid4())


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
    db_path = _new_db_path(tmp_path)
    engine = _fake_engine()
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        engine,
        db_path,
        PipelineMetrics(),
        _new_run_id(),
    )

    _run(job)

    assert job.state is JobState.SUCCEEDED
    observed_pts = sorted(obs.start_time for obs in _read_repository(db_path).list_all())
    # Real per-frame PTS (0.0, 0.3, 0.5s), never frame_index/fps.
    assert observed_pts == [0.0, 0.3, 0.5]


def test_job_only_produces_observations_within_the_processing_range(
    qapp_guard, tmp_path, changing_subtitle_video
):
    db_path = _new_db_path(tmp_path)
    engine = _fake_engine()
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(start_time=0.15, end_time=0.45),
        _FULL_FRAME_ROI,
        engine,
        db_path,
        PipelineMetrics(),
        _new_run_id(),
    )

    _run(job)

    assert job.state is JobState.SUCCEEDED
    for observation in _read_repository(db_path).list_all():
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
        _new_db_path(tmp_path),
        selective_metrics,
        _new_run_id(),
    )
    _run(selective_job)

    dense_metrics = PipelineMetrics()
    dense_db_path = _new_db_path(tmp_path)
    dense_job = build_ocr_evidence_job(
        path,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _fake_engine(),
        dense_db_path,
        dense_metrics,
        _new_run_id(),
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
    assert len(_read_repository(dense_db_path).list_all()) == dense_metrics.observations_created


def test_cancelling_the_job_stops_before_the_end_and_keeps_partial_evidence(qapp_guard, tmp_path):
    path = tmp_path / "cancel_target.mp4"
    _write_test_video(path, [(i * 20, 50 + (i % 2) * 150) for i in range(100)])  # 100 frames, alternating

    db_path = _new_db_path(tmp_path)
    metrics = PipelineMetrics()
    job = build_ocr_evidence_job(
        path, ProcessingRange(), _FULL_FRAME_ROI, _fake_engine(), db_path, metrics, _new_run_id()
    )

    job.start()
    job.request_cancel()
    waiter = _FinishedWaiter(job)
    waiter.wait()

    assert job.state is JobState.CANCELLED
    assert metrics.frames_analyzed < 100
    # Whatever evidence was already found before cancellation stays saved.
    assert len(_read_repository(db_path).list_all()) == metrics.observations_created


def test_observation_provenance_preserves_required_evidence_fields(
    qapp_guard, tmp_path, changing_subtitle_video
):
    db_path = _new_db_path(tmp_path)
    roi = ROI(x=0.1, y=0.2, width=0.5, height=0.3)
    engine = _fake_engine(text="captured text")
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(),
        roi,
        engine,
        db_path,
        PipelineMetrics(),
        _new_run_id(),
    )

    _run(job)

    observation = _read_repository(db_path).list_all()[0]
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
    db_path = _new_db_path(tmp_path)
    metrics = PipelineMetrics()
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _fake_engine(),
        db_path,
        metrics,
        _new_run_id(),
    )

    _run(job)

    assert metrics.frames_analyzed == 6
    assert metrics.ocr_calls == 3
    assert metrics.observations_created == len(_read_repository(db_path).list_all())
    assert metrics.elapsed_seconds > 0
    assert metrics.ocr_calls_per_minute == pytest.approx(
        metrics.ocr_calls / metrics.elapsed_seconds * 60.0
    )
    assert metrics.effective_processing_speed == pytest.approx(
        metrics.media_seconds_processed / metrics.elapsed_seconds
    )


def test_evidence_run_id_scopes_observations_from_one_job_run(
    qapp_guard, tmp_path, changing_subtitle_video
):
    db_path = _new_db_path(tmp_path)
    run_id = _new_run_id()
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _fake_engine(),
        db_path,
        PipelineMetrics(),
        run_id,
    )

    _run(job)

    repository = _read_repository(db_path)
    assert len(repository.list_for_run(run_id)) == len(repository.list_all())
    assert repository.list_for_run("a-different-run-id") == []


def test_a_second_run_does_not_pollute_the_first_runs_evidence(
    qapp_guard, tmp_path, changing_subtitle_video
):
    db_path = _new_db_path(tmp_path)
    first_run_id = _new_run_id()
    first_job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _fake_engine(text="first run text"),
        db_path,
        PipelineMetrics(),
        first_run_id,
    )
    _run(first_job)

    second_run_id = _new_run_id()
    second_job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _fake_engine(text="second run text"),
        db_path,
        PipelineMetrics(),
        second_run_id,
    )
    _run(second_job)

    repository = _read_repository(db_path)
    first_run_texts = {obs.text for obs in repository.list_for_run(first_run_id)}
    second_run_texts = {obs.text for obs in repository.list_for_run(second_run_id)}
    assert first_run_texts == {"first run text"}
    assert second_run_texts == {"second run text"}


def test_processing_range_progress_and_media_seconds_processed_are_relative_to_the_range(
    qapp_guard, tmp_path, changing_subtitle_video
):
    # Range covers [0.2, 0.5) of a video whose absolute PTS run up to
    # 0.5s: frames at 0.2, 0.3, 0.4s fall inside. If instrumentation
    # used absolute source PTS directly, media_seconds_processed would
    # end near 0.4 (close to the *source* offset) instead of near 0.2
    # (the actual amount of the *range* processed).
    db_path = _new_db_path(tmp_path)
    metrics = PipelineMetrics()
    reported = []
    job = build_ocr_evidence_job(
        changing_subtitle_video,
        ProcessingRange(start_time=0.2, end_time=0.5),
        _FULL_FRAME_ROI,
        _fake_engine(),
        db_path,
        metrics,
        _new_run_id(),
    )
    job.progress.connect(lambda phase, processed, total: reported.append((processed, total)))

    _run(job)

    assert job.state is JobState.SUCCEEDED
    range_length = 0.5 - 0.2
    # Every reported "total" is the range length (0.3s), never the
    # source's absolute duration.
    assert all(total == pytest.approx(range_length) for _processed, total in reported)
    # Progress is relative to range start: first frame at source PTS
    # 0.2s reports ~0.0 processed, not 0.2.
    processed_values = [processed for processed, _total in reported]
    assert processed_values[0] == pytest.approx(0.0)
    assert max(processed_values) <= range_length + 1e-9
    # media_seconds_processed reflects range-relative progress, so
    # effective_processing_speed isn't inflated by the 0.2s source
    # offset: it must not exceed what the range length could produce.
    assert metrics.media_seconds_processed <= range_length + 1e-9
    assert metrics.media_seconds_processed > 0


def test_partial_range_effective_processing_speed_is_not_amplified_by_source_offset(
    qapp_guard, tmp_path
):
    # A range starting far into a longer source: if media_seconds_processed
    # used absolute PTS, effective_processing_speed would be inflated by
    # the ~2s source offset even though only ~0.3s of range was processed.
    path = tmp_path / "offset_source.mp4"
    _write_test_video(path, [(ms, 50) for ms in range(0, 2500, 100)])  # 0..2.4s

    db_path = _new_db_path(tmp_path)
    metrics = PipelineMetrics()
    job = build_ocr_evidence_job(
        path,
        ProcessingRange(start_time=2.0, end_time=2.3),
        _FULL_FRAME_ROI,
        _fake_engine(),
        db_path,
        metrics,
        _new_run_id(),
    )

    _run(job)

    assert job.state is JobState.SUCCEEDED
    range_length = 2.3 - 2.0
    # If the ~2.0s source offset had leaked into media_seconds_processed
    # (e.g. by using absolute PTS directly), this would be violated --
    # only ~0.3s of range was actually processed, not ~2.3s.
    assert metrics.media_seconds_processed <= range_length + 1e-9
    assert metrics.media_seconds_processed > 0
