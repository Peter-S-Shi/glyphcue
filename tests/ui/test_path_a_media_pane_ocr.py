from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer

from glyphcue.adapters.ocr_types import OcrTextRegion
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


def test_run_ocr_button_is_disabled_without_ocr_wiring(qapp_guard, track_group_repository):
    pane = PathAMediaPane(track_group_repository)

    assert pane.run_ocr_button.isEnabled() is False


def test_run_ocr_button_is_enabled_when_ocr_is_wired(qapp_guard, track_group_repository, db_path):
    pane = PathAMediaPane(track_group_repository, ocr_engine=FakeOcrEngine(), db_path=db_path)

    assert pane.run_ocr_button.isEnabled() is True


def test_successful_run_populates_the_evidence_pane_and_says_done(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)
    pane.roi_x_spin.setValue(0.0)
    pane.roi_y_spin.setValue(0.0)
    pane.roi_width_spin.setValue(1.0)
    pane.roi_height_spin.setValue(1.0)

    pane.run_ocr_button.click()
    assert pane.current_ocr_job is not None
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert pane.evidence_pane.list_widget.count() > 0
    status = pane.ocr_status_label.text()
    assert "Done" in status
    assert "Cancelled" not in status
    assert "Failed" not in status


def test_evidence_pane_only_shows_the_current_run_not_database_history(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="first run", confidence=0.9)])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    first_run_count = pane.evidence_pane.list_widget.count()
    assert first_run_count > 0

    pane._ocr_engine = FakeOcrEngine(regions=[OcrTextRegion(text="second run", confidence=0.9)])
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    # The pane shows only the second run's evidence, not first+second.
    assert pane.evidence_pane.list_widget.count() == first_run_count


def test_cancel_ocr_button_shows_cancelled_status_and_keeps_partial_evidence(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    job = pane.current_ocr_job
    pane.cancel_ocr_button.click()
    _wait_for(job)

    assert job.state is JobState.CANCELLED
    status = pane.ocr_status_label.text()
    assert "Cancelled" in status
    assert "Done" not in status


def test_multilingual_track_group_uses_the_multi_engine_job_and_shows_layers(
    qapp_guard, track_group_repository, db_path, test_video
):
    # A Track Group configured with 2 languages must actually drive a
    # per-language engine set and the multilingual reconstruction path
    # -- not silently fall back to a single engine -- and the result
    # must land somewhere the user can see it (LanguageLayersPanel).
    track_group_repository.save(
        TrackGroup(id="default", roi=ROI(0.0, 0.0, 1.0, 1.0), languages=("en", "zh"))
    )
    engine_calls: list[str] = []
    # Real script content per language (not just a distinct string) --
    # script detection is the real production separation signal (see
    # docs/multilingual/track_group_reconstruction.md), so a fake
    # engine's text has to actually look like its language for the
    # separation to succeed, exactly like real PaddleOCR output would.
    texts = {"en": "Hello there", "zh": "你好朋友"}

    def factory(language: str) -> FakeOcrEngine:
        engine_calls.append(language)
        return FakeOcrEngine(
            regions=[OcrTextRegion(text=texts[language], language=language, confidence=0.9)]
        )

    pane = PathAMediaPane(track_group_repository, ocr_engine_factory=factory, db_path=db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    # Both configured languages' engines were actually constructed and
    # used -- proof this did not silently run a single-engine job.
    assert set(engine_calls) == {"en", "zh"}
    assert len(pane.language_layers_panel.cards) == 2
    texts_by_language = {card.language: card.text_label.text() for card in pane.language_layers_panel.cards}
    assert texts_by_language == {"en": "Hello there", "zh": "你好朋友"}


def test_single_language_track_group_still_uses_the_single_engine_job(
    qapp_guard, track_group_repository, db_path, test_video
):
    # A single-language Track Group (M4/M5's existing behavior) must
    # not be routed through the multi-engine path just because a
    # factory is available -- only one engine gets constructed, and the
    # layer presentation panel stays empty (no multilingual Cue was
    # ever reconstructed for it here).
    track_group_repository.save(
        TrackGroup(id="default", roi=ROI(0.0, 0.0, 1.0, 1.0), languages=("en",))
    )
    engine_calls: list[str] = []

    def factory(language: str) -> FakeOcrEngine:
        engine_calls.append(language)
        return FakeOcrEngine(regions=[OcrTextRegion(text="captured", language=language, confidence=0.9)])

    pane = PathAMediaPane(track_group_repository, ocr_engine_factory=factory, db_path=db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert engine_calls == ["en"]
    assert pane.language_layers_panel.cards == []


def test_failed_ocr_job_shows_failed_status_never_done(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(fail_initialize_with=RuntimeError("boom"))
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.FAILED
    status = pane.ocr_status_label.text()
    assert "Failed" in status
    assert "Done" not in status
