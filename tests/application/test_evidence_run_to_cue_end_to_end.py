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
from glyphcue.application.evidence_run_reconstruction import reconstruct_cues_for_evidence_run
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
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
    """A tiny FakeOcrEngine-like double that returns a different,
    pre-scripted region per call, to simulate noisy repeated readings of
    one real subtitle state (matches the OcrEngine Protocol)."""

    def __init__(self, texts_by_call: list[str]) -> None:
        self._texts = list(texts_by_call)
        self._call_index = 0
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def recognize(self, image):
        text = self._texts[min(self._call_index, len(self._texts) - 1)]
        self._call_index += 1
        return [OcrTextRegion(text=text, confidence=0.9, language="en")]

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
