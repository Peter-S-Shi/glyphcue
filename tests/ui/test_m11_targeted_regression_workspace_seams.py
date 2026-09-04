"""M11 Targeted Regression -- the high-risk seams this round's corrective
hardening touched.

Deliberately narrow: this is not a full regression, and it does not
re-open any OCR research question. Each test names one seam and asserts
one invariant a human would notice breaking.

Seams under test (all already-public surfaces, nothing reached into):
  * `PathAMediaPane` -- ROI inputs/persistence, processing range, run /
    cancel / discard, source switching, diagnostics
  * `ReconstructionQaWorkspace` -- queue ordering vs. Cue ordering,
    review-state badges
  * `build_evidence_job_for_profile` -- profile isolation
"""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QWidget

from glyphcue.adapters.ocr_types import OcrTextRegion
from glyphcue.application.evidence_job_profile import (
    EvidenceJobProfile,
    build_evidence_job_for_profile,
)
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.review_priority import ReviewPriority
from glyphcue.application.source_identity import normalize_source_id
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.domain.roi import ROI
from glyphcue.jobs.job import JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace
from tests.support.fake_ocr_engine import FakeOcrEngine


def _write_test_video(path: Path, frames: int = 5) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, frames * 100, 100):
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
def other_video(tmp_path) -> Path:
    path = tmp_path / "other.mp4"
    _write_test_video(path, frames=8)
    return path


@pytest.fixture
def track_group_repository(tmp_path):
    return TrackGroupRepository(connect(tmp_path / "track_groups.sqlite3"))


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "observations.sqlite3"


def _wait_for(job, timeout: float = 10.0) -> None:
    loop = QEventLoop()
    job.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(timeout * 1000))
    loop.exec()
    job.wait(timeout=0.5)


def _run_ocr(pane) -> None:
    pane.run_ocr_button.click()
    assert pane.current_ocr_job is not None, pane.ocr_status_label.text()
    _wait_for(pane.current_ocr_job)


class _FakeDetector:
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


def _pane(track_group_repository, db_path, **kwargs) -> PathAMediaPane:
    engine = kwargs.pop(
        "engine", FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)])
    )
    return PathAMediaPane(track_group_repository, ocr_engine=engine, db_path=db_path, **kwargs)


# --- Seam 1: the production profile builder never reaches an unrelated
# supplied detector (M11 Legacy Pipeline Retirement Corrective Gate,
# 2026-09-04: EXPERIMENTAL_HYBRID is no longer product/DevQA-reachable,
# so isolation between it and PRODUCTION_TRIGGER via the pane is now
# proven only by test_launchers.py's
# test_neither_launcher_can_select_the_retired_hybrid_pipeline; this
# builder-level seam remains real and still worth its own regression) --


def test_the_production_profile_never_reaches_a_supplied_detector(qapp_guard, db_path, test_video):
    """A detector handed to the profile seam stays unused by the
    production profile -- the builder ignores it even if one is passed."""
    detector = _FakeDetector()
    job = build_evidence_job_for_profile(
        EvidenceJobProfile.PRODUCTION_TRIGGER,
        test_video,
        ProcessingRange(),
        ROI(0.0, 0.0, 1.0, 1.0),
        FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)]),
        db_path,
        PipelineMetrics(),
        "run-production",
        detect=detector,
    )
    job.start()
    _wait_for(job)

    assert job.state is JobState.SUCCEEDED
    assert detector.detect_calls == 0


# --- Seam 2: ROI persistence, and no silent modification ------------------


def test_a_completed_run_leaves_the_users_roi_inputs_untouched(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    pane.roi_x_spin.setValue(0.1)
    pane.roi_y_spin.setValue(0.7)
    pane.roi_width_spin.setValue(0.8)
    pane.roi_height_spin.setValue(0.25)
    before = pane.current_roi()

    _run_ocr(pane)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert pane.current_roi() == before


def test_a_saved_roi_survives_a_reopen_without_being_silently_altered(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    pane.set_roi(ROI(0.1234, 0.7654, 0.8, 0.2))
    saved = pane.current_roi()
    pane.save_roi_button.click()

    pane.open_video(test_video)

    assert pane.current_roi() == saved


def test_a_second_video_does_not_inherit_the_first_videos_roi(
    qapp_guard, track_group_repository, db_path, test_video, other_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    pane.set_roi(ROI(0.1, 0.6, 0.8, 0.3))
    pane.save_roi_button.click()

    pane.open_video(other_video)

    assert pane.current_roi() == ROI(0.0, 0.0, 1.0, 1.0)
    # and the first video's own ROI is still exactly what was saved
    first = track_group_repository.get("tg:" + normalize_source_id(test_video))
    assert first is not None
    assert first.roi == ROI(0.1, 0.6, 0.8, 0.3)


# --- Seam 3: processing range boundaries stay on the source timeline ------


def test_a_partial_range_run_produces_cues_on_the_source_timeline(
    qapp_guard, track_group_repository, db_path, test_video
):
    """A range starting at 0.2s yields Cues timed from 0.2s onward in
    source seconds -- never renumbered as if the range began at zero."""
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.2)
    pane.processing_range_end_spin.setValue(0.4)

    _run_ocr(pane)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert pane.qa.cues, pane.ocr_status_label.text()
    for cue in pane.qa.cues:
        assert cue.start_time >= 0.2
        assert cue.end_time <= 0.4 + 1e-6


def test_the_range_controls_cannot_be_pushed_past_the_real_media_duration(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)

    pane.processing_range_end_spin.setValue(9999.0)

    assert pane.processing_range_end_spin.value() == pytest.approx(
        pane.processing_range_end_spin.maximum()
    )
    assert pane.processing_range_end_spin.maximum() < 5.0


# --- Seam 4: the A-B preview loop and the processing range are separate ---


def test_changing_the_processing_range_does_not_touch_the_preview_loop(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    pane.loop_a_spin.setValue(0.05)
    pane.loop_b_spin.setValue(0.15)
    pane.preview_loop_checkbox.setChecked(True)

    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.2)
    pane.processing_range_end_spin.setValue(0.4)

    assert pane.controller.is_loop_enabled is True
    assert pane.controller.loop_range == (0.05, 0.15)


def test_enabling_the_preview_loop_does_not_touch_the_processing_range(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.1)
    pane.processing_range_end_spin.setValue(0.3)
    before = pane.current_processing_range()

    pane.loop_a_spin.setValue(0.35)
    pane.loop_b_spin.setValue(0.45)
    pane.preview_loop_checkbox.setChecked(True)
    pane.play_loop_button.click()

    assert pane.current_processing_range() == before


# --- Seam 6: Discard Latest OCR Run -----------------------------------
#
# This seam's Hybrid-flavored regression was removed in the M11 Legacy
# Pipeline Retirement Corrective Gate (2026-09-04): EXPERIMENTAL_HYBRID
# is no longer product/DevQA-reachable (test_launchers.py's
# test_neither_launcher_can_select_the_retired_hybrid_pipeline covers
# that). Discard Latest OCR Run on the production path already has
# dedicated coverage elsewhere (test_path_a_media_pane_ocr.py,
# test_discard_latest_run_safety_dialog.py), so no seam is left uncovered.
    assert pane.discard_latest_run_button.isEnabled() is False


# --- Seam 7/8: repeated runs merge non-destructively, without duplicates --


def test_a_repeated_run_keeps_an_approved_cue_and_does_not_duplicate_it(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)

    _run_ocr(pane)
    assert pane.qa.cues
    first_run_cue_count = len(pane.qa.cues)
    pane.qa.approve_and_advance()
    approved = [cue for cue in pane.qa.cues if cue.review_state is ReviewState.APPROVED]
    assert len(approved) == 1
    approved_id = approved[0].id

    _run_ocr(pane)

    ids = [cue.id for cue in pane.qa.cues]
    assert approved_id in ids  # the human decision survived the re-run
    assert len(ids) == len(set(ids))  # no duplicate Cue identities
    assert len(pane.qa.cues) == first_run_cue_count  # no duplicated user-facing Cue


def test_overlapping_machine_observations_do_not_multiply_user_facing_cues(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(0.0)
    pane.processing_range_end_spin.setValue(0.4)
    _run_ocr(pane)
    assert pane.qa.cues

    # a second, overlapping run over a wider range
    pane.processing_range_end_spin.setValue(0.5)
    _run_ocr(pane)

    spans = [(round(c.start_time, 3), round(c.end_time, 3)) for c in pane.qa.cues]
    assert len(spans) == len(set(spans))


# --- Seam 9/10: Review Priority ordering vs. the playback timeline --------


def test_queue_orders_cues_chronologically_by_timeline(qapp_guard):
    """The queue and `cues` both follow strictly temporal ordering per M12 workflow recovery."""
    early = Cue(
        id="early",
        start_time=0.0,
        end_time=1.0,
        language_layers=[LanguageLayer(language="en", text="first")],
    )
    late = Cue(
        id="late",
        start_time=5.0,
        end_time=6.0,
        language_layers=[LanguageLayer(language="en", text="do not say it")],
    )
    qa = ReconstructionQaWorkspace([], {}, {}, QWidget())
    qa.set_cues_and_priorities(
        [early, late],
        {},
        {
            "early": ReviewPriority(cue_id="early", score=0.1, level="Low", components=()),
            "late": ReviewPriority(cue_id="late", score=0.9, level="High", components=()),
        },
    )

    assert qa.cue_id_for_row(0) == "early"  # strictly chronological timeline order
    assert qa.cue_id_for_row(1) == "late"
    assert [cue.id for cue in qa.cues] == ["early", "late"]  # timeline untouched


def test_a_high_priority_pending_cue_reads_as_pending_not_as_reviewed(qapp_guard):
    cue = Cue(
        id="flagged",
        start_time=5.0,
        end_time=6.0,
        language_layers=[LanguageLayer(language="en", text="do not say it")],
    )
    qa = ReconstructionQaWorkspace([], {}, {}, QWidget())
    qa.set_cues_and_priorities(
        [cue],
        {},
        {"flagged": ReviewPriority(cue_id="flagged", score=0.9, level="High", components=())},
    )

    label = qa.queue.item(0).text()
    assert "[High]" in label
    assert "Pending" in label
    assert qa.cues[0].review_state is ReviewState.PENDING


# --- Seam 11: switching source cleans the workspace up --------------------


def test_switching_video_clears_the_previous_sources_workspace_state(
    qapp_guard, track_group_repository, db_path, test_video, other_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    pane.loop_a_spin.setValue(0.05)
    pane.loop_b_spin.setValue(0.2)
    pane.preview_loop_checkbox.setChecked(True)
    _run_ocr(pane)
    assert pane.qa.cues
    assert pane.evidence_pane.list_widget.count() > 0

    pane.open_video(other_video)

    assert pane.qa.cues == []
    assert pane.controller.is_loop_enabled is False
    assert pane.discard_latest_run_button.isEnabled() is False
    assert pane.ocr_progress_bar.isVisible() is False
    assert pane._source_id == normalize_source_id(other_video)


def test_reopening_the_first_video_brings_back_only_its_own_cues(
    qapp_guard, track_group_repository, db_path, test_video, other_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    _run_ocr(pane)
    first_ids = {cue.id for cue in pane.qa.cues}
    assert first_ids

    pane.open_video(other_video)
    assert pane.qa.cues == []

    pane.open_video(test_video)

    assert {cue.id for cue in pane.qa.cues} == first_ids


# --- Seam 13: progress, cancellation and the diagnostic report ------------


def test_cancelling_a_run_is_reported_and_leaves_discard_unavailable(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)

    pane.run_ocr_button.click()
    assert pane.current_ocr_job is not None
    pane.cancel_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state in (JobState.CANCELLED, JobState.SUCCEEDED)
    if pane.current_ocr_job.state is JobState.CANCELLED:
        assert "Cancelled" in pane.ocr_status_label.text()
        assert pane.discard_latest_run_button.isEnabled() is False


def test_the_diagnostic_report_actions_unlock_only_after_a_dry_run(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)

    assert pane.view_diagnostic_report_button.isEnabled() is False
    assert pane.save_diagnostic_json_button.isEnabled() is False

    pane.dry_run_policy_button.click()

    assert pane.view_diagnostic_report_button.isEnabled() is True
    assert pane.save_diagnostic_json_button.isEnabled() is True
    assert "Dry Run" in pane.diagnostics_summary_label.text()


# --- Seam 2 (residual): a hand-drawn ROI vs. the ROI that actually runs ---


def test_a_drawn_roi_reaches_the_run_within_the_controls_own_precision(
    qapp_guard, track_group_repository, db_path, test_video
):
    """Recorded residual, not a regression from this round: the ROI spin
    boxes have carried 3 decimals since M2, so a hand-drawn ROI is
    quantized before it runs. This pins how far the run's ROI may sit
    from the drawn one, so that gap cannot silently widen."""
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    drawn = ROI(0.12345, 0.76543, 0.75318, 0.21197)

    pane.video_widget.roiChanged.emit(drawn)
    running = pane.current_roi()

    assert pane.video_widget.roi == drawn  # what the overlay draws
    for drawn_value, running_value in (
        (drawn.x, running.x),
        (drawn.y, running.y),
        (drawn.width, running.width),
        (drawn.height, running.height),
    ):
        assert abs(drawn_value - running_value) <= 0.0005


# --- Seam 12: Path A / Path B stay isolated across a mode switch ----------


def test_switching_between_path_a_and_path_b_does_not_move_cues_between_them(
    qapp_guard, tmp_path, test_video
):
    from glyphcue.ui.app import create_app

    _app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    pane = workbench.path_a_pane
    pane._ocr_engine = FakeOcrEngine(regions=[OcrTextRegion(text="captured", confidence=0.9)])
    pane._ocr_engine_factory = None
    pane.open_video(test_video)
    _run_ocr(pane)
    path_a_ids = {cue.id for cue in pane.qa.cues}
    assert path_a_ids

    caption = tmp_path / "captions.srt"
    caption.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nWorld\n",
        encoding="utf-8",
    )
    workbench.open_caption_file(caption)

    assert workbench.current_mode == "path_b"
    path_b = workbench.path_b_workspace
    assert path_b is not None
    path_b_ids = {cue.id for cue in path_b.qa.cues}
    assert path_b_ids
    assert path_b_ids.isdisjoint(path_a_ids)

    workbench.switch_to_mode("path_a")

    assert {cue.id for cue in pane.qa.cues} == path_a_ids


def test_a_hand_edited_cue_survives_a_repeated_run_with_its_text_intact(
    qapp_guard, track_group_repository, db_path, test_video
):
    """The merge protects a human edit, not just an explicit Approve."""
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)
    _run_ocr(pane)
    assert pane.qa.cues

    card = pane.qa.language_layers_panel.cards[0]
    card.text_edit.setPlainText("a human wrote this")
    pane.qa.commit_pending_edits()
    edited = [cue for cue in pane.qa.cues if cue.review_state is ReviewState.NEEDS_REVIEW]
    assert len(edited) == 1
    edited_id = edited[0].id

    _run_ocr(pane)

    survivor = next((cue for cue in pane.qa.cues if cue.id == edited_id), None)
    assert survivor is not None
    assert survivor.review_state is ReviewState.NEEDS_REVIEW
    assert survivor.language_layers[0].text == "a human wrote this"


def test_a_successful_run_completes_the_progress_bar_and_reports_its_metrics(
    qapp_guard, track_group_repository, db_path, test_video
):
    pane = _pane(track_group_repository, db_path)
    pane.open_video(test_video)

    _run_ocr(pane)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert pane.ocr_progress_bar.value() == 100
    status = pane.ocr_status_label.text()
    for expected in ("Done", "realtime", "frames analyzed", "OCR calls", "observations", "new cues"):
        assert expected in status
