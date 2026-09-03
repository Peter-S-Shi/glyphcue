from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QMessageBox

from glyphcue.adapters.ocr_types import OcrTextRegion
from glyphcue.adapters.pyav_media_source import probe_media
from glyphcue.application.processing_range import ProcessingRange
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


class _FakeSharedDetector:
    """Milestone 11 Architecture B: multilingual runs need a shared
    detector wired (`hybrid_detector_factory`), same as
    EXPERIMENTAL_HYBRID already does. `FakeOcrEngine` isn't a
    RegionOcrEngine, so the job always falls back to plain `recognize()`
    regardless of what this returns -- an empty polygon list is enough."""

    def initialize(self) -> None:
        pass

    def __call__(self, roi_frame):
        return []

    def shutdown(self) -> None:
        pass


def _fake_detector_factory() -> _FakeSharedDetector:
    return _FakeSharedDetector()


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
    # A Track Group configured with 2 languages must actually drive the
    # real multilingual job (shared detector + universal engine) and
    # reconstruction path -- not silently fall back to a single engine
    # / single layer -- and the result
    # must land somewhere the user can see it (LanguageLayersPanel).
    source_id = normalize_source_id(test_video)
    track_group_repository.save(
        TrackGroup(id=f"tg:{source_id}", roi=ROI(0.0, 0.0, 1.0, 1.0), languages=("en", "zh"))
    )
    engine_calls: list[str] = []
    # One shared universal engine returns every real region in one call
    # (Architecture B) -- real script content per region (not just a
    # distinct string) is what the real production separation signal
    # (script detection, see docs/multilingual/track_group_reconstruction.md)
    # actually keys off, so a fake engine's text has to actually look
    # like its language for the separation to succeed.
    def factory(language: str) -> FakeOcrEngine:
        engine_calls.append(language)
        return FakeOcrEngine(
            regions=[
                OcrTextRegion(text="Hello there", language=None, confidence=0.9),
                OcrTextRegion(text="你好朋友", language=None, confidence=0.9),
            ]
        )

    pane = PathAMediaPane(track_group_repository, ocr_engine_factory=factory, hybrid_detector_factory=_fake_detector_factory, db_path=db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    # One shared engine constructed (Architecture B) -- proof this did
    # not silently run a per-language multi-engine job.
    assert engine_calls == ["en"]
    assert len(pane.qa.language_layers_panel.cards) == 2
    texts_by_language = {card.language: card.current_text() for card in pane.qa.language_layers_panel.cards}
    assert texts_by_language == {"en": "Hello there", "zh": "你好朋友"}


def test_single_language_track_group_still_uses_the_single_engine_job(
    qapp_guard, track_group_repository, db_path, test_video
):
    # A single-language Track Group (M4/M5's existing behavior) must
    # not be routed through the multi-engine path just because a
    # factory is available -- only one engine gets constructed, and the
    # single-language M5 reconstruction (not M6's multilingual path)
    # produces exactly one language layer -- never a multilingual Cue.
    source_id = normalize_source_id(test_video)
    track_group_repository.save(
        TrackGroup(id=f"tg:{source_id}", roi=ROI(0.0, 0.0, 1.0, 1.0), languages=("en",))
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
    assert len(pane.qa.language_layers_panel.cards) == 1


def test_single_language_factory_follows_the_live_selection_when_plain_engine_is_also_wired(
    qapp_guard, track_group_repository, db_path, test_video
):
    # Production used to wire both PaddleOcrEngine() and
    # PaddleOcrEngine.  The live Track Group language must choose the
    # factory engine rather than silently reusing that default-English
    # plain engine.
    default_english_engine = FakeOcrEngine()
    factory_calls: list[str] = []

    def factory(language: str) -> FakeOcrEngine:
        factory_calls.append(language)
        return FakeOcrEngine(
            regions=[OcrTextRegion(text="你好朋友", language=language, confidence=0.9)]
        )

    pane = PathAMediaPane(
        track_group_repository,
        ocr_engine=default_english_engine,
        ocr_engine_factory=factory,
        db_path=db_path,
    )
    pane.open_video(test_video)
    pane.language_selection_panel.set_languages(("zh",))

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert factory_calls == ["zh"]
    assert default_english_engine.recognize_call_count == 0


def test_legacy_und_is_removed_before_a_restored_zh_track_group_runs(
    qapp_guard, track_group_repository, db_path, test_video
):
    source_id = normalize_source_id(test_video)
    track_group_repository.save(
        TrackGroup(
            id=f"tg:{source_id}",
            roi=ROI(0.0, 0.0, 1.0, 1.0),
            languages=("und", "zh"),
        )
    )
    factory_calls: list[str] = []

    def factory(language: str) -> FakeOcrEngine:
        factory_calls.append(language)
        return FakeOcrEngine(
            regions=[OcrTextRegion(text="你好朋友", language=language, confidence=0.9)]
        )

    pane = PathAMediaPane(track_group_repository, ocr_engine_factory=factory, db_path=db_path)
    pane.open_video(test_video)
    assert pane.language_selection_panel.selected_languages() == ("zh",)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert factory_calls == ["zh"]


def test_user_configured_language_selection_persists_and_drives_the_real_multi_engine_run(
    qapp_guard, track_group_repository, db_path, test_video
):
    # No test-code shortcut of pre-seeding a multilingual TrackGroup
    # directly into the repository -- the user configures it through
    # the real UI surface, saves it, and a FRESH pane instance (a
    # stand-in for reopening the app) must restore and run with it.
    # One shared universal engine returns every real region in one call
    # (Architecture B), regardless of which language label it was
    # constructed with.
    def factory(language: str) -> FakeOcrEngine:
        return FakeOcrEngine(
            regions=[
                OcrTextRegion(text="Hello there", language=None, confidence=0.9),
                OcrTextRegion(text="你好朋友", language=None, confidence=0.9),
            ]
        )

    first_pane = PathAMediaPane(track_group_repository, ocr_engine_factory=factory, hybrid_detector_factory=_fake_detector_factory, db_path=db_path)
    first_pane.open_video(test_video)
    # Starts as a single legal language, never the "und" placeholder.
    assert first_pane.language_selection_panel.selected_languages() == ("en",)

    first_pane.language_selection_panel.add_combo.setCurrentText("zh")
    first_pane.language_selection_panel.add_button.click()
    assert first_pane.language_selection_panel.selected_languages() == ("en", "zh")
    first_pane.save_roi_button.click()

    # Simulate reopening the app: a brand new pane over the same
    # repository, not the same live widget.
    second_pane = PathAMediaPane(track_group_repository, ocr_engine_factory=factory, hybrid_detector_factory=_fake_detector_factory, db_path=db_path)
    second_pane.open_video(test_video)
    assert second_pane.language_selection_panel.selected_languages() == ("en", "zh")

    second_pane.run_ocr_button.click()
    _wait_for(second_pane.current_ocr_job)

    assert second_pane.current_ocr_job.state is JobState.SUCCEEDED
    assert len(second_pane.qa.language_layers_panel.cards) == 2
    texts_by_language = {
        card.language: card.current_text() for card in second_pane.qa.language_layers_panel.cards
    }
    assert texts_by_language == {"en": "Hello there", "zh": "你好朋友"}


def test_final_multilingual_cue_uses_the_real_processing_range_end_not_a_1ms_instant(
    qapp_guard, track_group_repository, db_path, test_video
):
    # A subtitle state that runs to the end of the whole-media
    # processing range must have its final Cue's end_time reflect the
    # real resolved range end, not the ~1ms OCR-instant-marker fallback
    # (ROADMAP M5's frozen final-boundary contract, extended here to
    # multilingual reconstruction).
    source_id = normalize_source_id(test_video)
    track_group_repository.save(
        TrackGroup(id=f"tg:{source_id}", roi=ROI(0.0, 0.0, 1.0, 1.0), languages=("en", "zh"))
    )
    def factory(language: str) -> FakeOcrEngine:
        return FakeOcrEngine(
            regions=[
                OcrTextRegion(text="Hello there", language=None, confidence=0.9),
                OcrTextRegion(text="你好朋友", language=None, confidence=0.9),
            ]
        )

    pane = PathAMediaPane(track_group_repository, ocr_engine_factory=factory, hybrid_detector_factory=_fake_detector_factory, db_path=db_path)
    pane.open_video(test_video)
    real_range_end = probe_media(test_video).duration_seconds

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert pane.last_reconstructed_cues is not None
    assert len(pane.last_reconstructed_cues) == 1
    final_cue = pane.last_reconstructed_cues[-1]
    assert final_cue.end_time == pytest.approx(real_range_end)
    assert final_cue.end_time - final_cue.start_time > 0.01  # not a ~1ms instant marker


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


def test_processing_range_defaults_to_whole_media(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)

    assert pane.current_processing_range() == ProcessingRange()


def test_limiting_the_processing_range_via_ui_produces_a_real_restricted_range(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)

    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.1)
    pane.processing_range_end_spin.setValue(0.3)

    assert pane.current_processing_range() == ProcessingRange(start_time=0.1, end_time=0.3)


def test_run_ocr_uses_the_live_processing_range_selection(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="Hello there", language="en", confidence=0.9)])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.1)
    pane.processing_range_end_spin.setValue(0.3)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert pane._current_processing_end_time == pytest.approx(0.3)


def test_reversed_processing_range_shows_invalid_status_and_never_starts_a_job(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="Hello there", language="en", confidence=0.9)])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.3)
    pane.processing_range_end_spin.setValue(0.1)

    pane.run_ocr_button.click()

    assert pane.current_ocr_job is None
    assert "invalid" in pane.ocr_status_label.text().lower()


def test_zero_duration_processing_range_shows_invalid_status_and_never_starts_a_job(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="Hello there", language="en", confidence=0.9)])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.0)
    pane.processing_range_end_spin.setValue(0.0)

    pane.run_ocr_button.click()

    assert pane.current_ocr_job is None
    assert "invalid" in pane.ocr_status_label.text().lower()


def test_out_of_media_processing_range_shows_invalid_status_and_never_starts_a_job(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="Hello there", language="en", confidence=0.9)])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)
    real_duration = probe_media(test_video).duration_seconds

    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.0)
    # setRange() during open_video already caps the spin box at the
    # real duration -- force a value past it to prove the boundary
    # application layer (not just the widget) refuses it too.
    pane.processing_range_end_spin.setRange(0.0, real_duration * 10)
    pane.processing_range_end_spin.setValue(real_duration + 5.0)

    pane.run_ocr_button.click()

    assert pane.current_ocr_job is None
    assert "invalid" in pane.ocr_status_label.text().lower()


def test_valid_limited_processing_range_still_starts_a_real_job(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="Hello there", language="en", confidence=0.9)])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.0)
    pane.processing_range_end_spin.setValue(0.3)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert "invalid" not in pane.ocr_status_label.text().lower()


def test_left_pane_shows_no_video_context_before_a_video_is_loaded(
    qapp_guard, track_group_repository, db_path
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)

    context_text = pane.context_label.text().lower()
    assert "no video" in context_text


def test_left_pane_shows_video_roi_languages_and_range_context_after_loading(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)
    pane.roi_x_spin.setValue(0.1)
    pane.roi_width_spin.setValue(0.5)
    pane.language_selection_panel.set_languages(("en", "zh"))
    pane.save_roi_button.click()

    context_text = pane.context_label.text()
    assert test_video.name in context_text
    assert "0.1" in context_text
    assert "en" in context_text and "zh" in context_text
    assert "whole media" in context_text.lower()


def test_left_pane_context_reflects_a_limited_processing_range(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)

    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.1)
    pane.processing_range_end_spin.setValue(0.3)

    context_text = pane.context_label.text()
    assert "0.1" in context_text
    assert "0.3" in context_text


def test_left_pane_context_live_refreshes_languages_on_add_and_remove_without_save(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)

    pane.language_selection_panel.add_combo.setCurrentText("zh")
    pane.language_selection_panel.add_button.click()

    context_text = pane.context_label.text()
    assert "zh" in context_text

    pane.language_selection_panel.language_list.setCurrentRow(
        pane.language_selection_panel.selected_languages().index("zh")
    )
    pane.language_selection_panel.remove_button.click()

    context_text = pane.context_label.text()
    assert "zh" not in context_text


def test_opening_a_video_shows_the_roi_visualization_matching_current_roi(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)

    pane.roi_x_spin.setValue(0.2)
    pane.roi_width_spin.setValue(0.4)

    assert pane.roi_visualization.roi == pane.current_roi()


def test_opening_a_video_populates_the_time_navigation_slider_range(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    real_duration = probe_media(test_video).duration_seconds

    pane.open_video(test_video)

    assert pane.position_slider.maximum() == pytest.approx(round(real_duration * 1000), abs=1)


def test_seeking_via_the_slider_calls_controller_seek_with_the_real_position(
    qapp_guard, track_group_repository, db_path, test_video
):
    # QMediaPlayer's own eventual playback position is async and not
    # something GlyphCue controls or should assert on directly in a
    # headless test -- what GlyphCue owns is the wiring from the
    # slider to a real seek call, which is what this verifies.
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)
    seeked_to: list[float] = []
    pane.controller.seek = seeked_to.append

    pane.position_slider.setValue(100)

    assert seeked_to == [0.1]


def test_current_cue_relationship_label_shows_no_cue_before_any_reconstruction(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)

    assert "no cue" in pane.current_cue_relationship_label.text().lower()


def test_current_cue_relationship_label_names_the_cue_containing_the_playhead(
    qapp_guard, track_group_repository, db_path
):
    from glyphcue.domain.cue import Cue
    from glyphcue.domain.language_layer import LanguageLayer

    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    cue = Cue(
        id="c1", start_time=0.0, end_time=5.0,
        language_layers=(LanguageLayer(language="en", text="hello"),),
    )
    pane.qa.set_cues_and_priorities([cue], {}, {})

    pane._on_playback_position_changed(2000)

    assert "c1" in pane.current_cue_relationship_label.text()


def test_timeline_reflects_reconstructed_cue_spans(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.cue import Cue
    from glyphcue.domain.language_layer import LanguageLayer

    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(test_video)
    cue = Cue(
        id="c1", start_time=0.0, end_time=0.1,
        language_layers=(LanguageLayer(language="en", text="hello"),),
    )

    pane.qa.set_cues_and_priorities([cue], {}, {})

    assert len(pane.timeline.spans) == 1
    assert pane.timeline.spans[0][:2] == (0.0, 0.1)


def test_reopen_video_restores_persisted_cues_and_review_state(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    engine = FakeOcrEngine([
        OcrTextRegion(text="First Line", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane1 = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane1.open_video(test_video)
    pane1.run_ocr_button.click()
    _wait_for(pane1.current_ocr_job)

    assert len(pane1.qa.cues) >= 1
    pane1.qa.approve_and_advance()
    assert pane1.qa.cues[0].review_state == ReviewState.APPROVED

    # Open a second pane over the same db_path and reopen the video
    pane2 = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane2.open_video(test_video)

    assert len(pane2.qa.cues) >= 1
    assert pane2.qa.cues[0].review_state == ReviewState.APPROVED


def test_source_bound_track_group_isolation(
    qapp_guard, track_group_repository, db_path, tmp_path
):
    video_a = tmp_path / "video_a.mp4"
    video_b = tmp_path / "video_b.mp4"
    _write_test_video(video_a)
    _write_test_video(video_b)

    pane = PathAMediaPane(track_group_repository, db_path=db_path)

    # Open video A, set custom ROI, click save
    pane.open_video(video_a)
    pane.set_roi(ROI(0.1, 0.2, 0.3, 0.4))
    pane.save_roi_button.click()

    # Open video B -> should have default ROI (0, 0, 1, 1), not video A's
    pane.open_video(video_b)
    assert pane.current_roi() == ROI(0.0, 0.0, 1.0, 1.0)

    # Set video B ROI, click save
    pane.set_roi(ROI(0.5, 0.5, 0.2, 0.2))
    pane.save_roi_button.click()

    # Reopen video A -> restores video A's ROI
    pane.open_video(video_a)
    assert pane.current_roi() == ROI(0.1, 0.2, 0.3, 0.4)

    # Reopen video B -> restores video B's ROI
    pane.open_video(video_b)
    assert pane.current_roi() == ROI(0.5, 0.5, 0.2, 0.2)


def test_incremental_processing_range_appends_cues_and_preserves_approved(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    engine = FakeOcrEngine([
        OcrTextRegion(text="Hello", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    # First run: range 0.0s - 0.2s
    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.0)
    pane.processing_range_end_spin.setValue(0.2)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert len(pane.qa.cues) >= 1
    pane.qa.approve_and_advance()
    assert pane.qa.cues[0].review_state == ReviewState.APPROVED
    first_cue_id = pane.qa.cues[0].id

    # Second run: range 0.2s - 0.5s
    pane.processing_range_start_spin.setValue(0.2)
    pane.processing_range_end_spin.setValue(0.5)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    # Both cues are in the workspace, first cue is still APPROVED
    cues = pane.qa.cues
    assert len(cues) >= 2
    assert any(c.id == first_cue_id and c.review_state == ReviewState.APPROVED for c in cues)


def test_overlapping_reprocessing_preserves_needs_review_and_approved_cues(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    engine = FakeOcrEngine([
        OcrTextRegion(text="Line 1", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    assert len(pane.qa.cues) >= 1

    # Nudge timing -> transitions to NEEDS_REVIEW (human edit)
    pane.qa.nudge_end_later_button.click()
    assert pane.qa.cues[0].review_state == ReviewState.NEEDS_REVIEW
    nudged_id = pane.qa.cues[0].id

    # Re-run OCR over same video range
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    # Human-edited NEEDS_REVIEW cue is preserved and not overwritten
    cues = pane.qa.cues
    assert any(c.id == nudged_id and c.review_state == ReviewState.NEEDS_REVIEW for c in cues)


def test_cancelled_or_failed_ocr_preserves_persisted_workspace(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    engine = FakeOcrEngine([
        OcrTextRegion(text="Initial line", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    assert len(pane.qa.cues) >= 1
    pane.qa.approve_and_advance()
    assert pane.qa.cues[0].review_state == ReviewState.APPROVED
    original_cue_id = pane.qa.cues[0].id

    # Run failing job
    failing_engine = FakeOcrEngine(fail_recognize_with=RuntimeError("OCR error"))
    failing_pane = PathAMediaPane(track_group_repository, ocr_engine=failing_engine, db_path=db_path)
    failing_pane.open_video(test_video)
    assert len(failing_pane.qa.cues) >= 1

    failing_pane.run_ocr_button.click()
    _wait_for(failing_pane.current_ocr_job)
    assert failing_pane.current_ocr_job.state is JobState.FAILED

    # Existing workspace cues are preserved, not cleared
    assert len(failing_pane.qa.cues) >= 1
    assert failing_pane.qa.cues[0].id == original_cue_id
    assert failing_pane.qa.cues[0].review_state == ReviewState.APPROVED


def test_succeeded_ocr_with_zero_observations_merges_incrementally_without_clearing_entire_workspace(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    engine = FakeOcrEngine([
        OcrTextRegion(text="Start line", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    # First run in 0.0 - 0.2s
    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.0)
    pane.processing_range_end_spin.setValue(0.2)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    assert len(pane.qa.cues) >= 1
    cue_id = pane.qa.cues[0].id

    # Second run in 0.3 - 0.5s with zero observations
    empty_engine = FakeOcrEngine([])
    pane._ocr_engine = empty_engine
    pane.processing_range_start_spin.setValue(0.3)
    pane.processing_range_end_spin.setValue(0.5)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    assert pane.current_ocr_job.state is JobState.SUCCEEDED

    # Cue at 0.0 - 0.2s is still retained in workspace
    assert any(c.id == cue_id for c in pane.qa.cues)


def test_switching_video_or_closing_window_commits_pending_text_edits(
    qapp_guard, track_group_repository, db_path, tmp_path
):
    from glyphcue.domain.review_state import ReviewState

    video_a = tmp_path / "video_a.mp4"
    video_b = tmp_path / "video_b.mp4"
    _write_test_video(video_a)
    _write_test_video(video_b)

    engine = FakeOcrEngine([
        OcrTextRegion(text="Original Text", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(video_a)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    assert len(pane.qa.cues) >= 1

    # User modifies text in the editor without clicking Approve or pressing Enter
    pane.qa.language_layers_panel.cards[0].text_edit.setPlainText("Human Hand-Edited Text")

    # User switches video
    pane.open_video(video_b)

    # Reopen video A in a fresh pane -> verify hand-edited text was persisted with NEEDS_REVIEW
    fresh_pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    fresh_pane.open_video(video_a)
    assert len(fresh_pane.qa.cues) >= 1
    assert fresh_pane.qa.cues[0].language_layers[0].text == "Human Hand-Edited Text"
    assert fresh_pane.qa.cues[0].review_state == ReviewState.NEEDS_REVIEW


def test_new_source_does_not_inherit_legacy_default_track_group(
    qapp_guard, track_group_repository, db_path, tmp_path
):
    # Seed legacy unassigned "default" track group
    track_group_repository.save(
        TrackGroup(id="default", roi=ROI(0.2, 0.2, 0.5, 0.5), languages=("zh",))
    )

    new_video = tmp_path / "new_video.mp4"
    _write_test_video(new_video)

    pane = PathAMediaPane(track_group_repository, db_path=db_path)
    pane.open_video(new_video)

    # Must NOT inherit legacy "default" settings; must use clean product defaults
    assert pane.current_roi() == ROI(0.0, 0.0, 1.0, 1.0)
    assert pane.language_selection_panel.selected_languages() == ("en",)


def test_resumed_cues_have_neutral_review_priority(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    engine = FakeOcrEngine([
        OcrTextRegion(text="Sample line", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane1 = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane1.open_video(test_video)
    pane1.run_ocr_button.click()
    _wait_for(pane1.current_ocr_job)
    assert len(pane1.qa.cues) >= 1

    pane2 = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane2.open_video(test_video)

    assert len(pane2.qa.cues) >= 1
    for cue in pane2.qa.cues:
        priority = pane2.qa._priority_for(cue.id)
        assert priority.level == "None"
        assert priority.score == 0.0


def test_discard_latest_ocr_run_restores_pre_run_workspace_and_persisted_db(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    engine = FakeOcrEngine([
        OcrTextRegion(text="First run line", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    assert pane.discard_latest_run_button.isEnabled() is False

    # Run 1: 0.0 - 0.2s
    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.0)
    pane.processing_range_end_spin.setValue(0.2)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    assert len(pane.qa.cues) >= 1
    assert pane.discard_latest_run_button.isEnabled() is True
    pane.qa.approve_and_advance()
    assert pane.qa.cues[0].review_state == ReviewState.APPROVED
    first_cue_id = pane.qa.cues[0].id
    # Manual approve invalidated Run 1 rollback
    assert pane.discard_latest_run_button.isEnabled() is False

    # Run 2: 0.3 - 0.5s with different text
    engine2 = FakeOcrEngine([
        OcrTextRegion(text="Second bad run line", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane._ocr_engine = engine2
    pane.processing_range_start_spin.setValue(0.3)
    pane.processing_range_end_spin.setValue(0.5)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    assert pane.discard_latest_run_button.isEnabled() is True

    # Workspace now has cues from both runs
    assert len(pane.qa.cues) >= 2
    assert any(c.id == first_cue_id for c in pane.qa.cues)
    assert any("Second bad run line" in l.text for c in pane.qa.cues for l in c.language_layers)

    # Click Discard Latest OCR Run (confirm via safety dialog)
    with patch.object(QMessageBox, "exec", return_value=None):
        with patch.object(
            QMessageBox,
            "clickedButton",
            lambda self: next((b for b in self.buttons() if "Discard" in b.text()), None),
        ):
            pane.discard_latest_run_button.click()

    # Workspace is restored to the state before Run 2 (only first cue, which is APPROVED)
    assert len(pane.qa.cues) == 1
    assert pane.qa.cues[0].id == first_cue_id
    assert pane.qa.cues[0].review_state == ReviewState.APPROVED
    assert not any("Second bad run line" in l.text for c in pane.qa.cues for l in c.language_layers)
    assert pane.discard_latest_run_button.isEnabled() is False
    assert "discarded" in pane.ocr_status_label.text().lower()

    # Reopening video verifies persistence matches restored snapshot
    pane_fresh = PathAMediaPane(track_group_repository, db_path=db_path)
    pane_fresh.open_video(test_video)
    assert len(pane_fresh.qa.cues) == 1
    assert pane_fresh.qa.cues[0].id == first_cue_id


def test_ocr_job_progress_and_completion_metrics_ui(
    qapp_guard, track_group_repository, db_path, test_video
):
    engine = FakeOcrEngine([
        OcrTextRegion(text="Performance Test", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    assert hasattr(pane, "ocr_progress_bar")

    pane._ocr_start_time = 1000.0
    pane._on_ocr_progress("reading", 0.25, 0.5)
    assert pane.ocr_progress_bar.value() == 50
    assert "0.2s" in pane.ocr_status_label.text() or "0.3s" in pane.ocr_status_label.text()
    assert "Elapsed:" in pane.ocr_status_label.text()

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert pane.ocr_progress_bar.value() == 100
    status_text = pane.ocr_status_label.text()
    assert "Done:" in status_text
    assert "media in" in status_text
    assert "realtime" in status_text
    assert "frames analyzed" in status_text
    assert "OCR calls" in status_text
    assert "observations" in status_text
    assert "cues" in status_text


def test_manual_cue_mutation_after_ocr_run_invalidates_discard_snapshot(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    engine = FakeOcrEngine([
        OcrTextRegion(text="Line to edit", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.discard_latest_run_button.isEnabled() is True
    assert pane._last_pre_run_cues is not None

    # User performs a manual text edit in QA pane
    pane.qa.language_layers_panel.cards[0].text_edit.setPlainText("Manually Edited Text")
    pane.qa._commit_displayed_edits()

    # Discard snapshot must now be invalidated and button disabled to protect manual work
    assert pane._last_pre_run_cues is None
    assert pane.discard_latest_run_button.isEnabled() is False


def test_discard_latest_ocr_run_clears_evidence_pane_while_retaining_qa_raw_evidence(
    qapp_guard, track_group_repository, db_path, test_video
):
    from glyphcue.domain.review_state import ReviewState

    # Run 1: first OCR run produces initial cue with obs1
    engine1 = FakeOcrEngine([
        OcrTextRegion(text="First run obs", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane = PathAMediaPane(track_group_repository, ocr_engine=engine1, db_path=db_path)
    pane.open_video(test_video)
    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.0)
    pane.processing_range_end_spin.setValue(0.2)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)
    pane.qa.approve_and_advance()

    # Run 2: second run produces bad obs
    engine2 = FakeOcrEngine([
        OcrTextRegion(text="Second bad run obs", confidence=0.9, geometry=((0, 0), (10, 0), (10, 10), (0, 10)), language="en")
    ])
    pane._ocr_engine = engine2
    pane.processing_range_start_spin.setValue(0.3)
    pane.processing_range_end_spin.setValue(0.5)
    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    # Lower evidence pane currently shows Run 2 observations
    assert len(pane.evidence_pane._observations) > 0
    assert any("Second bad run obs" in obs.text for obs in pane.evidence_pane._observations)

    # Discard latest run
    with patch.object(QMessageBox, "exec", return_value=None):
        with patch.object(
            QMessageBox,
            "clickedButton",
            lambda self: next((b for b in self.buttons() if "Discard" in b.text()), None),
        ):
            pane.discard_latest_run_button.click()

    # Evidence pane must no longer display discarded machine observations
    assert len(pane.evidence_pane._observations) == 0

    # QA pane for the restored Cue still has its own raw OCR evidence intact
    assert len(pane.qa.cues) == 1
    assert "First run obs" in pane.qa.evidence_view.toPlainText()





