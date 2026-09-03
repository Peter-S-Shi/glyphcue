"""End-to-end proof that the real evidence-production path
(`build_multilingual_ocr_evidence_job`, Milestone 11 Architecture B: one
shared detector, one scripted universal engine) feeds real Observations
into the real reconstruction (`reconstruct_multilingual_cues_for_track_group`)
and produces stable, correctly-ordered multi-layer Cues -- not just the
pure-function unit tests in test_multilingual_reconstruction.py.
"""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer

from glyphcue.adapters.ocr_types import OcrRuntimeInfo, OcrTextRegion
from glyphcue.application.multilingual_ocr_evidence_job import build_multilingual_ocr_evidence_job
from glyphcue.application.multilingual_reconstruction import (
    reconstruct_multilingual_cues_for_track_group,
)
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.jobs.job import JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository

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


class _ScriptedUniversalEngine:
    """A scripted OcrEngine double standing in for Architecture B's one
    shared universal recognizer: each call returns every region for
    every language at once (real universal recognition doesn't run once
    per language), tagged with a single "universal" label -- a real
    engine's own tag is only a hint anyway (see
    assign_observations_to_languages), so callers must reconstruct real
    per-language layers from script content, not from this tag."""

    def __init__(self, texts_by_call: list[list[str]]) -> None:
        self._texts_by_call = texts_by_call
        self._call_index = 0
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def recognize(self, image):
        texts = self._texts_by_call[min(self._call_index, len(self._texts_by_call) - 1)]
        self._call_index += 1
        return [OcrTextRegion(text=text, confidence=0.9, language=None) for text in texts]

    def supported_languages(self):
        return ("en", "zh", "ja")

    def runtime_info(self):
        return OcrRuntimeInfo(engine_name="scripted-universal-fake", version="1.0", backend="cpu")

    def shutdown(self) -> None:
        self.initialized = False


def _no_op_detect(image):
    """A shared-detector double that finds no polygons -- the job falls
    back to the scripted engine's plain `recognize()`, exactly like a
    real caller-supplied `OcrEngine` that isn't a `RegionOcrEngine`."""
    return []


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


def test_bilingual_evidence_reconstructs_into_two_stable_layers(qapp_guard, tmp_path):
    video_path = tmp_path / "bilingual.mp4"
    # A single frame -- exactly one triggered OCR event (first_frame),
    # read by both engines.
    _write_test_video(video_path, [(0, 50)])

    db_path = tmp_path / "glyphcue.sqlite3"
    engine = _ScriptedUniversalEngine([["Hello there", "你好朋友"]])
    metrics = PipelineMetrics()
    evidence_run_id = "run-bilingual"
    track_group = TrackGroup(id="tg-1", roi=_FULL_FRAME_ROI, languages=("en", "zh"))

    job = build_multilingual_ocr_evidence_job(
        video_path,
        ProcessingRange(),
        track_group,
        engine,
        db_path,
        metrics,
        evidence_run_id,
        detect=_no_op_detect,
    )
    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()
    assert job.state is JobState.SUCCEEDED
    # One shared recognition call for the one triggered frame -- not one
    # per Track Group language (Milestone 11 Architecture B).
    assert metrics.ocr_calls == 1

    observation_repository = ObservationRepository(connect(db_path))
    observations = observation_repository.list_for_run(evidence_run_id)
    cues, diagnostics = reconstruct_multilingual_cues_for_track_group(observations, track_group)

    assert len(cues) == 1
    layers = cues[0].language_layers
    assert [layer.language for layer in layers] == ["en", "zh"]
    assert layers[0].text == "Hello there"
    assert layers[1].text == "你好朋友"
    assert diagnostics[0].missing_languages == ()


def test_asymmetric_evidence_produces_a_missing_layer_diagnostic(qapp_guard, tmp_path):
    # The Chinese engine finds nothing at all -- real asymmetric source
    # material, not a synthetic Observation constructed by hand.
    video_path = tmp_path / "asymmetric.mp4"
    _write_test_video(video_path, [(0, 50)])

    db_path = tmp_path / "glyphcue.sqlite3"
    # The universal engine only ever finds the English line -- no
    # Chinese text exists anywhere in this frame's real evidence.
    engine = _ScriptedUniversalEngine([["Hello there"]])
    metrics = PipelineMetrics()
    evidence_run_id = "run-asymmetric"
    track_group = TrackGroup(id="tg-2", roi=_FULL_FRAME_ROI, languages=("en", "zh"))

    job = build_multilingual_ocr_evidence_job(
        video_path,
        ProcessingRange(),
        track_group,
        engine,
        db_path,
        metrics,
        evidence_run_id,
        detect=_no_op_detect,
    )
    waiter = _FinishedWaiter(job)
    job.start()
    waiter.wait()
    assert job.state is JobState.SUCCEEDED

    observation_repository = ObservationRepository(connect(db_path))
    observations = observation_repository.list_for_run(evidence_run_id)
    cues, diagnostics = reconstruct_multilingual_cues_for_track_group(observations, track_group)

    assert len(cues) == 1
    layers = cues[0].language_layers
    assert layers[0].language == "en"
    assert layers[0].text == "Hello there"
    assert layers[1].language == "zh"
    assert layers[1].text == ""
    assert diagnostics[0].missing_languages == ("zh",)
