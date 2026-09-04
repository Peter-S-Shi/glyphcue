from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.adapters.ocr_types import OcrRuntimeInfo, OcrTextRegion
from glyphcue.application.evidence_job_profile import (
    EvidenceJobProfile,
    build_evidence_job_for_profile,
)
from glyphcue.application.hybrid_evidence_job import build_hybrid_ocr_evidence_job
from glyphcue.application.ocr_evidence_job import (
    STATE_TRIGGER_DETAIL_KEY,
    build_ocr_evidence_job,
)
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI
from glyphcue.domain.caption_identity import ROLE_KEY, caption_identity_evidence
from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository

_WIDTH, _HEIGHT = 320, 96
_FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)
_CAPTION_TOP = 60


def _poly(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _frame(spacing: int | None, distractor_shift: int) -> np.ndarray:
    """A moving object in the upper frame (the presenter) plus an
    optional caption in the lower band."""
    frame = np.full((_HEIGHT, _WIDTH, 3), 210, dtype=np.uint8)
    for column in range(distractor_shift % 24, _WIDTH, 24):
        frame[6:50, column : column + 9] = 40
    if spacing is not None:
        frame[_CAPTION_TOP + 4 : _CAPTION_TOP + 22, 30:290:spacing] = 20
    return frame


def _write(path: Path, plan) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width, stream.height = _WIDTH, _HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0
    for index, pts_ms in enumerate(range(0, 4000, 40)):
        video_frame = av.VideoFrame.from_ndarray(plan(index, pts_ms), format="rgb24").reformat(
            format="yuv420p"
        )
        video_frame.pts = pts_ms
        video_frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(video_frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


@pytest.fixture
def two_caption_video(tmp_path) -> Path:
    """Caption A for 0-2s, caption B for 2-4s, with the presenter moving
    throughout -- the shape the whole research gate was fought over."""
    path = tmp_path / "two_captions.mp4"
    _write(path, lambda index, pts: _frame(6 if pts < 2000 else 13, index * 3))
    return path


@pytest.fixture
def caption_then_blank_video(tmp_path) -> Path:
    path = tmp_path / "caption_then_blank.mp4"
    _write(path, lambda index, pts: _frame(6 if pts < 2000 else None, index * 3))
    return path


class _FakeDetector:
    """Localization only: reports the caption band when it has ink."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, roi_frame: np.ndarray):
        self.calls += 1
        luminance = roi_frame.mean(axis=2) if roi_frame.ndim == 3 else roi_frame
        band = luminance[_CAPTION_TOP + 2 : _CAPTION_TOP + 24, 20:300]
        if not bool((band < 30).any()):
            return []
        return [_poly(30, _CAPTION_TOP, 290, _CAPTION_TOP + 24)]


class _FakeOcrEngine:
    """Reads the caption band and reports its stroke spacing as text, so
    a wrong representative frame produces demonstrably wrong text."""

    def __init__(self) -> None:
        self.recognize_calls = 0
        self.initialized = 0
        self.shutdowns = 0

    def initialize(self) -> None:
        self.initialized += 1

    def shutdown(self) -> None:
        self.shutdowns += 1

    def runtime_info(self) -> OcrRuntimeInfo:
        return OcrRuntimeInfo(
            engine_name="fake", version="1.0", backend="test", backend_version="1.0"
        )

    def supported_languages(self) -> tuple[str, ...]:
        return ("en",)

    def recognize(self, roi_frame: np.ndarray):

        self.recognize_calls += 1
        luminance = roi_frame.mean(axis=2) if roi_frame.ndim == 3 else roi_frame
        row = luminance[_CAPTION_TOP + 10, :]
        ink_columns = np.flatnonzero(row < 30)
        if ink_columns.size < 2:
            return []
        spacing = int(np.median(np.diff(ink_columns)[np.diff(ink_columns) > 1]))
        return [
            OcrTextRegion(text=f"caption-{spacing}", confidence=0.9, language="en", geometry=None)
        ]


class _CancellingDetector(_FakeDetector):
    """Cancels the job from inside the run, after a fixed number of
    detector calls -- deterministic, and through the real public
    `request_cancel` path rather than a hand-made context."""

    def __init__(self, after_calls: int) -> None:
        super().__init__()
        self._after = after_calls
        self.job = None

    def __call__(self, roi_frame: np.ndarray):
        result = super().__call__(roi_frame)
        if self.job is not None and self.calls >= self._after:
            self.job.request_cancel()
        return result


def _run_job(job) -> None:
    job.start()
    job.wait(timeout=120)


def _hybrid_job(video: Path, db_path: Path, detector, engine, metrics):
    return build_hybrid_ocr_evidence_job(
        video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        engine,
        db_path,
        metrics,
        "run-hybrid",
        detect=detector,
    )


def _run_hybrid(video: Path, db_path: Path, detector=None, engine=None):
    detector = detector if detector is not None else _FakeDetector()
    engine = engine if engine is not None else _FakeOcrEngine()
    metrics = PipelineMetrics()
    job = _hybrid_job(video, db_path, detector, engine, metrics)
    if isinstance(detector, _CancellingDetector):
        detector.job = job
    _run_job(job)
    return metrics, detector, engine


def _observations(db_path: Path, run_id: str = "run-hybrid"):
    conn = connect(db_path)
    try:
        return ObservationRepository(conn).list_for_run(run_id)
    finally:
        conn.close()


# --- the saving this profile exists for ---------------------------------


def test_recognition_is_bounded_per_coarse_envelope_and_metrics_count_probes(
    two_caption_video, tmp_path
):
    db_path = tmp_path / "hybrid.db"
    metrics, detector, engine = _run_hybrid(two_caption_video, db_path)

    # Two real captions over four seconds: recognition should cost a
    # handful of calls, far below both the detector's own call count and
    # the analyzed frame count.
    evidence = [e for o in _observations(db_path) if (e := caption_identity_evidence(o)) is not None]
    assert all(len(e.probes) <= e.probe_budget for e in evidence)
    assert engine.recognize_calls <= sum(e.probe_budget for e in evidence)
    assert engine.recognize_calls <= detector.calls
    assert detector.calls < metrics.frames_analyzed
    assert metrics.ocr_calls == engine.recognize_calls


def test_the_hybrid_profile_reads_both_captions_correctly(two_caption_video, tmp_path):
    db_path = tmp_path / "hybrid.db"
    _run_hybrid(two_caption_video, db_path)

    texts = {observation.text for observation in _observations(db_path) if observation.text}

    # The fake engine encodes each caption's own stroke spacing, so this
    # fails if a state's representative frame came from the wrong state.
    assert {"caption-6", "caption-13"} <= texts
    # Non-medoid probes expose a compressed-frame fake-OCR misread that the
    # former medoid-only path hid. Keep it as raw evidence, not a winning span.
    cues, diagnostics = reconstruct_cues_with_consensus(_observations(db_path))
    assert cues and any(d.had_disagreement for d in diagnostics)


def test_bounded_verification_reports_its_extra_calls_without_claiming_a_saving(
    two_caption_video, tmp_path
):
    production_engine = _FakeOcrEngine()
    production_metrics = PipelineMetrics()
    _run_job(
        build_ocr_evidence_job(
            two_caption_video,
            ProcessingRange(),
            _FULL_FRAME_ROI,
            production_engine,
            tmp_path / "production.db",
            production_metrics,
            "run-production",
        )
    )

    hybrid_metrics, _detector, hybrid_engine = _run_hybrid(
        two_caption_video, tmp_path / "hybrid.db"
    )

    # Correctness probing replaces the old once-per-state cost promise. This
    # fixture records its real extra calls; it is not a performance acceptance.
    assert hybrid_engine.recognize_calls > production_engine.recognize_calls
    assert hybrid_metrics.ocr_calls == hybrid_engine.recognize_calls
    assert hybrid_metrics.detector_calls > 0
    assert production_metrics.detector_calls == 0


def test_a_detector_confirmed_blank_state_costs_no_recognition_call(
    caption_then_blank_video, tmp_path
):
    db_path = tmp_path / "blank.db"
    _metrics, _detector, engine = _run_hybrid(caption_then_blank_video, db_path)

    observations = _observations(db_path)
    blank_markers = [o for o in observations if not o.text and o.provenance.detail.get(ROLE_KEY) == "raw_probe"]

    # The blank state is still recorded as evidence (M5 needs to know
    # the subtitle went away, not merely that nothing was OCR'd) --
    # but the detector already answered it, so no call was spent.
    assert blank_markers
    assert all(
        o.provenance.detail[STATE_TRIGGER_DETAIL_KEY] == "blank" for o in blank_markers
    )
    text_evidence = [e for o in observations if (e := caption_identity_evidence(o)) is not None
                     and o.provenance.detail[STATE_TRIGGER_DETAIL_KEY] != "blank"]
    assert engine.recognize_calls == sum(len(e.probes) for e in text_evidence)


# --- the contracts it must not break ------------------------------------


@pytest.fixture
def late_short_caption_video(tmp_path) -> Path:
    """A different caption for only the final 0.2s of the range -- the
    sample_b state 5 shape: a real state shorter than the sentinel
    interval, sitting at the very end of the processing range."""
    path = tmp_path / "late_short.mp4"
    _write(path, lambda index, pts: _frame(6 if pts < 3800 else 13, index * 3))
    return path


def test_a_state_that_exists_only_at_the_end_of_the_range_is_still_observed(
    late_short_caption_video, tmp_path
):
    # A sentinel that comes due after the range ends never fires, so
    # without the boundary rule this state is never looked at. The rule
    # observes the last grid point nothing else claimed.
    db_path = tmp_path / "late.db"
    _run_hybrid(late_short_caption_video, db_path)

    texts = {observation.text for observation in _observations(db_path) if observation.text}

    assert "caption-13" in texts


def test_observations_keep_the_production_shape(two_caption_video, tmp_path):
    db_path = tmp_path / "hybrid.db"
    _run_hybrid(two_caption_video, db_path)

    for observation in _observations(db_path):
        assert observation.end_time > observation.start_time
        assert observation.roi == _FULL_FRAME_ROI
        assert observation.provenance.source == "fake"
        assert observation.frame_reference.endswith("s")
        assert STATE_TRIGGER_DETAIL_KEY in observation.provenance.detail


def test_the_job_analyzes_exactly_the_users_roi_with_no_context_expansion(
    two_caption_video, tmp_path
):
    """Pins the verdict of the M11 bounded ROI Normalization / Context
    Expansion Gate: NO normalization rule was adopted, so the pixels the
    detector and the engine see are exactly the user's own ROI crop.

    The gate asked whether one uniform, fixture-independent expansion of
    the user's ROI (a fixed fraction of the ROI's own height on all four
    sides -- the only fixture-independent scale available at this seam)
    could make plausibly tighter or looser hand-drawn ROIs behave like
    the frozen research ROI, whose signature margins the whole gate was
    decided on. Replaying the frozen ROI, the real hand-drawn tighter
    ROI and six systematic perturbations under that one rule showed it
    is NOT a stable improvement: it did recover the short state that a
    too-tight ROI swallows, but it also cost a different real state on
    the frozen research ROI itself, and on one perturbation -- trading
    one state for another rather than removing the sensitivity. So the
    rule was rejected rather than tuned, since tuning it per fixture is
    exactly what would invalidate the frozen gate.

    This test therefore guards a DECISION, not a mechanism: if a future
    round adds an expansion here, this fails and forces that round to
    argue for it on its own evidence rather than inherit silence.
    """
    seen_shapes: list[tuple[int, int]] = []
    roi = ROI(x=0.0, y=0.5, width=1.0, height=0.5)

    def recording_detector(roi_frame: np.ndarray):
        seen_shapes.append(roi_frame.shape[:2])
        return []

    engine = _FakeOcrEngine()
    db_path = tmp_path / "roi.db"
    _run_job(
        build_hybrid_ocr_evidence_job(
            two_caption_video,
            ProcessingRange(),
            roi,
            engine,
            db_path,
            PipelineMetrics(),
            "run-hybrid",
            detect=recording_detector,
        )
    )

    assert seen_shapes
    # The user asked for the lower half and got the lower half. Any
    # padding rule would grow this crop (and, clamped at the frame's
    # bottom edge, shift its top).
    assert set(seen_shapes) == {(_HEIGHT // 2, _WIDTH)}
    assert all(observation.roi == roi for observation in _observations(db_path))


def test_evidence_is_persisted_per_state_so_a_cancel_keeps_what_was_found(
    two_caption_video, tmp_path
):
    db_path = tmp_path / "cancelled.db"
    _run_hybrid(two_caption_video, db_path, detector=_CancellingDetector(after_calls=14))

    # Cancelled partway, but the states that had already closed are
    # still on disk -- the M4 partial-working-state contract.
    assert _observations(db_path)


def test_the_engine_is_shut_down_even_when_the_run_is_cancelled(
    two_caption_video, tmp_path
):
    engine = _FakeOcrEngine()
    _run_hybrid(
        two_caption_video,
        tmp_path / "cancelled.db",
        detector=_CancellingDetector(after_calls=2),
        engine=engine,
    )

    assert engine.initialized == 1
    assert engine.shutdowns == 1


def test_a_completed_run_reports_the_whole_range_as_processed(
    two_caption_video, tmp_path
):
    # The same completion contract the production job has: a successful
    # run reports 100% of the range, not "close to it" -- the last
    # frame's own timestamp always falls a little short.
    metrics, _detector, _engine = _run_hybrid(two_caption_video, tmp_path / "hybrid.db")

    assert metrics.media_seconds_processed == pytest.approx(3.96, abs=0.05)
    assert metrics.frames_analyzed > 0


def test_observations_are_tagged_with_their_own_run(two_caption_video, tmp_path):
    db_path = tmp_path / "hybrid.db"
    _run_hybrid(two_caption_video, db_path)

    assert _observations(db_path, "run-hybrid")
    assert _observations(db_path, "some-other-run") == []


# --- the profile switch --------------------------------------------------


def test_the_production_profile_is_still_the_one_that_needs_no_detector(
    two_caption_video, tmp_path
):
    job = build_evidence_job_for_profile(
        EvidenceJobProfile.PRODUCTION_TRIGGER,
        two_caption_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _FakeOcrEngine(),
        tmp_path / "production.db",
        PipelineMetrics(),
        "run-production",
    )

    assert job is not None


def test_the_experimental_profile_refuses_to_run_without_a_detector(
    two_caption_video, tmp_path
):
    # Falling back to the production path here would produce a run whose
    # profile label was a lie.
    with pytest.raises(ValueError):
        build_evidence_job_for_profile(
            EvidenceJobProfile.EXPERIMENTAL_HYBRID,
            two_caption_video,
            ProcessingRange(),
            _FULL_FRAME_ROI,
            _FakeOcrEngine(),
            tmp_path / "hybrid.db",
            PipelineMetrics(),
            "run-hybrid",
        )


def test_the_hybrid_job_rejects_a_non_positive_sampling_fps(two_caption_video, tmp_path):
    with pytest.raises(ValueError):
        build_hybrid_ocr_evidence_job(
            two_caption_video,
            ProcessingRange(),
            _FULL_FRAME_ROI,
            _FakeOcrEngine(),
            tmp_path / "hybrid.db",
            PipelineMetrics(),
            "run-hybrid",
            detect=_FakeDetector(),
            sampling_fps=0.0,
        )


class _FakeRegionOcrEngine(_FakeOcrEngine):
    def __init__(self) -> None:
        super().__init__()
        self.recognize_regions_calls = 0
        self.received_regions = []

    def recognize(self, roi_frame: np.ndarray):
        raise AssertionError("recognize() should not be called when recognize_regions is supported")

    def recognize_regions(self, roi_frame: np.ndarray, regions: object):
        self.recognize_regions_calls += 1
        self.received_regions.append(regions)
        return super().recognize(roi_frame)


def test_hybrid_job_uses_recognize_regions_when_supported(two_caption_video, tmp_path):
    db_path = tmp_path / "region_ocr.db"
    detector = _FakeDetector()
    engine = _FakeRegionOcrEngine()
    metrics = PipelineMetrics()

    job = _hybrid_job(two_caption_video, db_path, detector, engine, metrics)
    _run_job(job)

    assert engine.recognize_regions_calls > 0
    assert len(engine.received_regions) == engine.recognize_regions_calls
    assert all(r is not None for r in engine.received_regions)

    # Verify complete public seam: persisted evidence and downstream Cue reconstruction
    observations = _observations(db_path)
    assert observations
    texts = {o.text for o in observations if o.text}
    assert {"caption-6", "caption-13"} <= texts

    cues, diagnostics = reconstruct_cues_with_consensus(observations)
    assert cues
    assert any(d.had_disagreement for d in diagnostics)



