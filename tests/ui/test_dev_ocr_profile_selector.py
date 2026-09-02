"""M11: the developer/manual-QA-only OCR profile selector seam.

Seams under test:
  * `PathAMediaPane.__init__`'s `enable_dev_ocr_profile_selector` /
    `hybrid_detector_factory` params
  * `pane.dev_ocr_profile_combo` (present/absent, default selection)
  * `pane.run_ocr_button.click()` with Hybrid selected, through the real
    `EXPERIMENTAL_HYBRID` job path, using a fake detector -- no real
    PaddleOCR involved
"""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer

from glyphcue.adapters.ocr_types import OcrTextRegion
from glyphcue.application.evidence_job_profile import EvidenceJobProfile
from glyphcue.application.source_identity import normalize_source_id
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.jobs.job import JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from tests.support.fake_ocr_engine import FakeOcrEngine


def _write_test_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, 500, 100):
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
def test_video(tmp_path) -> Path:
    path = tmp_path / "pane.mp4"
    _write_test_video(path)
    return path


@pytest.fixture
def track_group_repository(tmp_path):
    conn = connect(tmp_path / "track_groups.sqlite3")
    return TrackGroupRepository(conn)


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "observations.sqlite3"


def _wait_for(job, timeout: float = 5.0) -> None:
    loop = QEventLoop()
    job.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(timeout * 1000))
    loop.exec()
    job.wait(timeout=0.5)


class _FakeDetector:
    """Localization only, matching `hybrid_evidence_job.TextDetector`
    plus the initialize()/shutdown() lifecycle the pane manages."""

    def __init__(self) -> None:
        self.initialize_calls = 0
        self.shutdown_calls = 0
        self.detect_calls = 0

    def initialize(self) -> None:
        self.initialize_calls += 1

    def __call__(self, roi_frame: np.ndarray):
        self.detect_calls += 1
        return [[[0, 0], [10, 0], [10, 10], [0, 10]]]

    def shutdown(self) -> None:
        self.shutdown_calls += 1


# --- the selector stays absent by default ---------------------------------


def test_the_profile_selector_is_absent_by_default(qapp_guard, track_group_repository, db_path):
    pane = PathAMediaPane(track_group_repository, ocr_engine=FakeOcrEngine(), db_path=db_path)

    assert pane.dev_ocr_profile_combo is None


def test_enabling_the_selector_defaults_to_production(qapp_guard, track_group_repository, db_path):
    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine=FakeOcrEngine(),
        db_path=db_path,
        enable_dev_ocr_profile_selector=True,
    )

    assert pane.dev_ocr_profile_combo is not None
    assert pane.dev_ocr_profile_combo.currentData() is EvidenceJobProfile.PRODUCTION_TRIGGER


# --- a real Hybrid run through the pane, with a fake detector -------------


def test_selecting_hybrid_runs_the_real_hybrid_job_and_shuts_the_detector_down(
    qapp_guard, track_group_repository, db_path, test_video
):
    detector = _FakeDetector()
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)])
    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine=engine,
        db_path=db_path,
        enable_dev_ocr_profile_selector=True,
        hybrid_detector_factory=lambda: detector,
    )
    pane.open_video(test_video)
    pane.roi_x_spin.setValue(0.0)
    pane.roi_y_spin.setValue(0.0)
    pane.roi_width_spin.setValue(1.0)
    pane.roi_height_spin.setValue(1.0)
    pane.dev_ocr_profile_combo.setCurrentIndex(1)  # Experimental Hybrid

    pane.run_ocr_button.click()
    assert pane.current_ocr_job is not None
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert detector.initialize_calls == 1
    assert detector.shutdown_calls == 1
    assert detector.detect_calls > 0
    assert pane.evidence_pane.list_widget.count() > 0


def test_production_still_runs_when_the_selector_is_present_but_left_at_default(
    qapp_guard, track_group_repository, db_path, test_video
):
    # The selector existing must not change the shipped behavior when
    # nobody touches it.
    detector = _FakeDetector()
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)])
    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine=engine,
        db_path=db_path,
        enable_dev_ocr_profile_selector=True,
        hybrid_detector_factory=lambda: detector,
    )
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert detector.initialize_calls == 0  # never touched


# --- explicit failure, never a silent fallback -----------------------------


def test_hybrid_without_a_detector_factory_refuses_the_run_explicitly(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)])
    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine=engine,
        db_path=db_path,
        enable_dev_ocr_profile_selector=True,
        hybrid_detector_factory=None,
    )
    pane.open_video(test_video)
    pane.dev_ocr_profile_combo.setCurrentIndex(1)  # Experimental Hybrid

    pane.run_ocr_button.click()

    assert pane.current_ocr_job is None
    assert "detector" in pane.ocr_status_label.text().lower()


def test_hybrid_with_multiple_languages_refuses_the_run_explicitly(
    qapp_guard, track_group_repository, db_path, test_video
):
    source_id = normalize_source_id(test_video)
    track_group_repository.save(
        TrackGroup(id=f"tg:{source_id}", roi=ROI(0.0, 0.0, 1.0, 1.0), languages=("en", "zh"))
    )
    detector = _FakeDetector()
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)])
    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine=engine,
        db_path=db_path,
        enable_dev_ocr_profile_selector=True,
        hybrid_detector_factory=lambda: detector,
    )
    pane.open_video(test_video)
    pane.dev_ocr_profile_combo.setCurrentIndex(1)  # Experimental Hybrid

    pane.run_ocr_button.click()

    assert pane.current_ocr_job is None
    assert detector.initialize_calls == 0
    assert "single language" in pane.ocr_status_label.text().lower()
