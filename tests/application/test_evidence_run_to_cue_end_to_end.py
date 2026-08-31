"""End-to-end proof that the real Milestone 4 -> Milestone 5 path
produces inspectable, persisted Cues with full provenance back to their
source Observations.

Uses the real `build_ocr_evidence_job` (M4) with a scripted
`FakeOcrEngine` (deterministic, no real OCR needed for this test --
`benchmarks/multi_frame_consensus/` covers the real-PaddleOCR evidence
separately) to produce real Observations from a real synthetic video,
then runs the real `reconstruct_cues_for_evidence_run` (M5) and persists
the result via the existing `CueRepository`.
"""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer

from glyphcue.adapters.ocr_types import OcrTextRegion
from glyphcue.adapters.pyav_media_source import probe_media
from glyphcue.application.evidence_run_reconstruction import reconstruct_cues_for_evidence_run
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.ocr_invocation_policy import ChangeTriggeredOcrPolicy
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI
from glyphcue.jobs.job import JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository
from glyphcue.persistence.repository import CueRepository

_FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)


def _write_test_video(path: Path, frames: list[tuple[int, int]]) -> None:
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


class _ScriptedOcrEngine:
    """A tiny FakeOcrEngine-like double that returns pre-scripted
    regions per call (matches the OcrEngine Protocol), to simulate real
    M4 OCR behavior: noisy repeated readings of one subtitle state,
    multi-region single-frame results, or confirmed-blank (no regions)
    calls."""

    def __init__(self, texts_by_call: list[str] | None = None, regions_by_call=None) -> None:
        if regions_by_call is not None:
            self._regions_by_call = regions_by_call
        else:
            self._regions_by_call = [
                [OcrTextRegion(text=text, confidence=0.9, language="en")] for text in texts_by_call
            ]
        self._call_index = 0
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def recognize(self, image):
        regions = self._regions_by_call[min(self._call_index, len(self._regions_by_call) - 1)]
        self._call_index += 1
        return regions

    def supported_languages(self):
        return ("en",)

    def runtime_info(self):
        from glyphcue.adapters.ocr_types import OcrRuntimeInfo

        return OcrRuntimeInfo(engine_name="scripted-fake", version="1.0", backend="cpu")

    def shutdown(self) -> None:
        self.initialized = False


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


def test_real_m4_evidence_reconstructs_into_a_persisted_cue_with_inspectable_provenance(
    qapp_guard, tmp_path
):
    # Same visual state held across 3 confirmations (gray=50), one of
    # them read slightly wrong by the "engine" -- real M4 selective-OCR
    # behavior: ChangeTriggeredOcrPolicy triggers on the first frame,
    # then periodically re-confirms an unchanged state.
    video_path = tmp_path / "evidence.mp4"
    _write_test_video(video_path, [(0, 50), (2000, 50), (4000, 50)])

    db_path = tmp_path / "glyphcue.sqlite3"
    engine = _ScriptedOcrEngine(["Hello world", "Hallo world", "Hello world"])
    metrics = PipelineMetrics()
    evidence_run_id = "run-e2e-1"
    job = build_ocr_evidence_job(
        video_path,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        engine,
        db_path,
        metrics,
        evidence_run_id,
    )
    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()
    assert job.state is JobState.SUCCEEDED

    observation_repository = ObservationRepository(connect(db_path))
    cues, diagnostics = reconstruct_cues_for_evidence_run(observation_repository, evidence_run_id)

    assert len(cues) == 1
    cue = cues[0]
    assert cue.language_layers[0].text == "Hello world"  # majority vote won over the misread
    assert diagnostics[0].had_disagreement is True

    cue_repository = CueRepository(connect(db_path))
    cue_repository.add(cue)

    persisted = cue_repository.get(cue.id)
    assert persisted == cue

    # Full provenance is inspectable: every supporting observation id on
    # the persisted Cue's layer resolves back to a real, persisted
    # Observation from this exact evidence run.
    supporting_ids = persisted.language_layers[0].observation_ids
    assert len(supporting_ids) == 3
    for observation_id in supporting_ids:
        observation = observation_repository.get(observation_id)
        assert observation is not None
        assert observation.text in ("Hello world", "Hallo world")


def test_two_region_single_language_frame_becomes_one_cue_not_two(qapp_guard, tmp_path):
    # Real M4->M5 regression: one OCR call on one frame returns TWO
    # regions (e.g. a two-line subtitle detected as two boxes). Without
    # same-frame aggregation, M5 would treat these as two sequential
    # states instead of one frame's combined reading. A second,
    # identical-content frame at 1.5s (under max_gap_seconds, so it does
    # NOT trigger a second OCR call) gives the video a real ~1.5s
    # duration -- a single-frame video has ~0 real duration, which would
    # make the "not a near-zero-duration Cue" assertion meaningless
    # regardless of what the production code does.
    video_path = tmp_path / "two_line.mp4"
    _write_test_video(video_path, [(0, 50), (1500, 50)])

    db_path = tmp_path / "glyphcue.sqlite3"
    engine = _ScriptedOcrEngine(
        regions_by_call=[
            [
                OcrTextRegion(text="Top line", confidence=0.9, language="en"),
                OcrTextRegion(text="Bottom line", confidence=0.85, language="en"),
            ]
        ]
    )
    metrics = PipelineMetrics()
    evidence_run_id = "run-two-region"
    job = build_ocr_evidence_job(
        video_path, ProcessingRange(), _FULL_FRAME_ROI, engine, db_path, metrics, evidence_run_id
    )
    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()
    assert job.state is JobState.SUCCEEDED

    observation_repository = ObservationRepository(connect(db_path))
    metadata = probe_media(video_path)
    cues, _diagnostics = reconstruct_cues_for_evidence_run(
        observation_repository, evidence_run_id, processing_end_time=metadata.duration_seconds
    )

    assert len(cues) == 1
    cue = cues[0]
    assert cue.language_layers[0].text == "Top lineBottom line"
    assert len(cue.language_layers[0].observation_ids) == 2
    # Not a zero/near-zero-duration Cue: it runs to the real processing
    # end, not a 1ms observation-instant marker.
    assert cue.end_time - cue.start_time > 0.01


def test_subtitle_blank_subtitle_produces_two_cues_not_three(qapp_guard, tmp_path):
    video_path = tmp_path / "blank_gap.mp4"
    _write_test_video(video_path, [(0, 50), (2000, 50), (4000, 200), (6000, 200), (8000, 50)])

    db_path = tmp_path / "glyphcue.sqlite3"
    # 5 OCR calls expected (first_frame, then a real pixel change at
    # each subsequent gray-value transition): a clean subtitle line
    # while gray=50, blank while gray=200, a CLEARLY DIFFERENT subtitle
    # line once gray=50 returns -- deliberately dissimilar text (not
    # just "A"/"B") so the blank-confirmation check (which compares the
    # reading after the blank against the reading before it) isn't
    # accidentally fooled by two texts that merely look alike.
    engine = _ScriptedOcrEngine(
        regions_by_call=[
            [OcrTextRegion(text="The quick brown fox", confidence=0.9, language="en")],
            [OcrTextRegion(text="The quick brown fox", confidence=0.9, language="en")],
            [],  # blank candidate
            [],  # blank candidate (periodic confirmation) -- 2 in a row confirms the gap
            [OcrTextRegion(text="Bright orange sunsets glow", confidence=0.9, language="en")],
        ]
    )
    metrics = PipelineMetrics()
    evidence_run_id = "run-blank-gap"
    job = build_ocr_evidence_job(
        video_path, ProcessingRange(), _FULL_FRAME_ROI, engine, db_path, metrics, evidence_run_id
    )
    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()
    assert job.state is JobState.SUCCEEDED

    observation_repository = ObservationRepository(connect(db_path))
    cues, _diagnostics = reconstruct_cues_for_evidence_run(observation_repository, evidence_run_id)

    assert [cue.language_layers[0].text for cue in cues] == [
        "The quick brown fox",
        "Bright orange sunsets glow",
    ]
    # The blank gap really shortened the first Cue -- it does not run
    # all the way to the second subtitle's start.
    assert cues[0].end_time < cues[1].start_time


def test_final_single_observation_uses_real_processing_end_not_a_1ms_cue(qapp_guard, tmp_path):
    video_path = tmp_path / "single.mp4"
    # A second, identical-content frame at 1.5s (under max_gap_seconds,
    # so no second OCR call) gives the video a real ~1.5s duration.
    _write_test_video(video_path, [(0, 50), (1500, 50)])

    db_path = tmp_path / "glyphcue.sqlite3"
    engine = _ScriptedOcrEngine(texts_by_call=["Only subtitle"])
    metrics = PipelineMetrics()
    evidence_run_id = "run-final-single"
    job = build_ocr_evidence_job(
        video_path, ProcessingRange(), _FULL_FRAME_ROI, engine, db_path, metrics, evidence_run_id
    )
    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()
    assert job.state is JobState.SUCCEEDED

    observation_repository = ObservationRepository(connect(db_path))
    metadata = probe_media(video_path)
    cues, _diagnostics = reconstruct_cues_for_evidence_run(
        observation_repository, evidence_run_id, processing_end_time=metadata.duration_seconds
    )

    assert len(cues) == 1
    assert cues[0].end_time == metadata.duration_seconds
    assert cues[0].end_time - cues[0].start_time > 0.01  # not a ~1ms instant marker


def test_visual_false_positive_change_detection_does_not_over_split(qapp_guard, tmp_path):
    """Real M4->M5 verification: an oscillating background (real pixel
    content that genuinely crosses ChangeTriggeredOcrPolicy's
    change_threshold every frame) fires real "change_detected" triggers
    repeatedly, while the (scripted) OCR reading itself never changes --
    exactly the "cheap visual detector flags a candidate that isn't a
    real state change" scenario the M5 corrective's confirmation rule
    exists for. Goes through the real ChangeTriggeredOcrPolicy (not a
    stub), the real state_trigger provenance stamping, and the real
    consensus grouping -- unlike benchmarks/multi_frame_consensus/,
    which evaluates real OCR output but does not exercise M4's
    invocation-policy/trigger semantics at all (see that benchmark's
    module docstring)."""
    video_path = tmp_path / "flicker.mp4"
    _write_test_video(
        video_path, [(0, 50), (200, 200), (400, 50), (600, 200), (800, 50), (1000, 200)]
    )

    db_path = tmp_path / "glyphcue.sqlite3"
    engine = _ScriptedOcrEngine(texts_by_call=["Stable subtitle text"])
    metrics = PipelineMetrics()
    evidence_run_id = "run-flicker"
    # A sensitive change_threshold guarantees the real oscillating gray
    # value (50 <-> 200) crosses it every single frame -- real,
    # repeated change_detected evidence, not a rare edge case.
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.01, max_gap_seconds=100.0)
    job = build_ocr_evidence_job(
        video_path,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        engine,
        db_path,
        metrics,
        evidence_run_id,
        policy=policy,
    )
    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()
    assert job.state is JobState.SUCCEEDED

    observation_repository = ObservationRepository(connect(db_path))
    all_observations = observation_repository.list_for_run(evidence_run_id)
    # Confirm the test actually exercised real change_detected evidence
    # (not just first_frame + periodic_confirmation) before trusting the
    # "did not over-split" assertion below.
    assert metrics.ocr_calls >= 5
    assert any(
        observation.provenance.detail.get("state_trigger") == "change_detected"
        for observation in all_observations
    )

    cues, _diagnostics = reconstruct_cues_for_evidence_run(observation_repository, evidence_run_id)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Stable subtitle text"
