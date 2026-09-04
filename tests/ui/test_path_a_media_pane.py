from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QWidget

from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.path_a_media_pane import PathAMediaPane


def _wait_for_media_status(player: QMediaPlayer, timeout_ms: int = 3000) -> None:
    if player.mediaStatus() in (
        QMediaPlayer.MediaStatus.LoadedMedia,
        QMediaPlayer.MediaStatus.InvalidMedia,
    ):
        return
    loop = QEventLoop()
    player.mediaStatusChanged.connect(
        lambda status: loop.quit()
        if status
        in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.InvalidMedia)
        else None
    )
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()


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
def repository(tmp_path):
    conn = connect(tmp_path / "glyphcue.sqlite3")
    return TrackGroupRepository(conn)


def test_pane_embeds_a_video_widget_in_the_frozen_shell(qapp_guard, repository):
    pane = PathAMediaPane(repository)

    assert isinstance(pane.video_widget, QWidget)
    assert pane.window.centralWidget().count() == 3


def test_video_widget_retains_visible_viewport_height_and_does_not_collapse(
    qapp_guard, repository, test_video
):
    pane = PathAMediaPane(repository)
    pane.window.resize(1200, 800)
    pane.window.show()
    pane.open_video(test_video)

    assert pane.video_widget.minimumHeight() >= 240
    assert pane.video_widget.height() >= 240


def test_open_video_loads_the_given_path(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)

    pane.open_video(test_video)

    assert Path(pane.controller.player.source().toLocalFile()) == test_video


def test_open_video_displays_basic_metadata(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)

    pane.open_video(test_video)

    text = pane.metadata_label.text()
    assert "32" in text  # width and height
    assert "h264" in text.lower()


def test_play_button_plays_and_pause_button_pauses(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)
    pane.open_video(test_video)
    _wait_for_media_status(pane.controller.player)

    pane.play_button.click()
    assert pane.controller.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    pane.pause_button.click()
    assert pane.controller.player.playbackState() == QMediaPlayer.PlaybackState.PausedState


def test_the_roi_controls_advise_leaving_margin_for_larger_captions(
    qapp_guard, repository
):
    """A caption the ROI does not cover is invisible to the detector for
    its whole duration -- no sampling, grouping or threshold change can
    recover it (see hybrid_evidence_job's residual risk). V1 answers that
    with advice rather than a gate, so the hint has to actually be there,
    next to the ROI fields, and it must not become a step: nothing blocks
    a tight ROI and nothing widens one automatically.
    """
    pane = PathAMediaPane(repository)

    assert pane.roi_hint_label.text() == (
        "Cover the full subtitle area and leave margin for wider/taller captions."
    )
    assert pane.roi_hint_label.wordWrap() is True
    # Advice only: the ROI the user set is still exactly the ROI in force.
    pane.roi_x_spin.setValue(0.2)
    pane.roi_y_spin.setValue(0.85)
    pane.roi_width_spin.setValue(0.5)
    pane.roi_height_spin.setValue(0.05)
    assert pane.current_roi() == ROI(x=0.2, y=0.85, width=0.5, height=0.05)


def test_roi_fields_default_to_the_full_frame_when_nothing_is_saved(qapp_guard, repository):
    pane = PathAMediaPane(repository)

    assert pane.current_roi() == ROI(x=0.0, y=0.0, width=1.0, height=1.0)


def test_saving_the_roi_persists_it_to_the_repository(qapp_guard, repository):
    pane = PathAMediaPane(repository, track_group_id="tg-1")
    pane.roi_x_spin.setValue(0.1)
    pane.roi_y_spin.setValue(0.8)
    pane.roi_width_spin.setValue(0.8)
    pane.roi_height_spin.setValue(0.15)

    pane.save_roi_button.click()

    saved = repository.get("tg-1")
    assert saved is not None
    assert saved.roi == ROI(x=0.1, y=0.8, width=0.8, height=0.15)


def test_reconstructing_the_pane_restores_the_previously_saved_roi(qapp_guard, repository):
    repository.save(
        TrackGroup(
            id="tg-1",
            roi=ROI(x=0.2, y=0.3, width=0.4, height=0.25),
            languages=("ja", "en"),
        )
    )

    pane = PathAMediaPane(repository, track_group_id="tg-1")

    assert pane.current_roi() == ROI(x=0.2, y=0.3, width=0.4, height=0.25)


def test_reconstructing_the_pane_replaces_a_legacy_und_language_with_the_canonical_default(
    qapp_guard, repository
):
    repository.save(
        TrackGroup(
            id="default",
            roi=ROI(x=0.0, y=0.0, width=1.0, height=1.0),
            languages=("und",),
        )
    )

    pane = PathAMediaPane(repository)

    assert pane.language_selection_panel.selected_languages() == ("en",)


def test_saving_the_roi_again_updates_it_rather_than_erroring(qapp_guard, repository):
    pane = PathAMediaPane(repository, track_group_id="tg-1")
    pane.roi_x_spin.setValue(0.1)
    pane.roi_y_spin.setValue(0.1)
    pane.roi_width_spin.setValue(0.5)
    pane.roi_height_spin.setValue(0.5)
    pane.save_roi_button.click()

    pane.roi_x_spin.setValue(0.2)
    pane.save_roi_button.click()

    assert repository.get("tg-1").roi == ROI(x=0.2, y=0.1, width=0.5, height=0.5)
    assert len(repository.list_all()) == 1


def test_reset_roi_button_resets_roi_to_full_frame(qapp_guard, repository):
    pane = PathAMediaPane(repository)
    pane.roi_x_spin.setValue(0.1)
    pane.roi_y_spin.setValue(0.2)
    pane.roi_width_spin.setValue(0.5)
    pane.roi_height_spin.setValue(0.4)

    pane.reset_roi_button.click()

    assert pane.current_roi() == ROI(0.0, 0.0, 1.0, 1.0)
    assert pane.video_overlay.roi == ROI(0.0, 0.0, 1.0, 1.0)
    assert pane.roi_x_spin.value() == 0.0
    assert pane.roi_y_spin.value() == 0.0
    assert pane.roi_width_spin.value() == 1.0
    assert pane.roi_height_spin.value() == 1.0


def test_video_overlay_drag_updates_spinboxes_and_current_roi(qapp_guard, repository):
    pane = PathAMediaPane(repository)
    new_roi = ROI(0.15, 0.25, 0.6, 0.35)

    pane.video_overlay.roiChanged.emit(new_roi)

    assert pane.current_roi() == new_roi
    assert pane.roi_x_spin.value() == 0.15
    assert pane.roi_y_spin.value() == 0.25
    assert pane.roi_width_spin.value() == 0.6
    assert pane.roi_height_spin.value() == 0.35


def test_spinbox_edits_update_video_overlay_roi(qapp_guard, repository):
    pane = PathAMediaPane(repository)

    pane.roi_x_spin.setValue(0.3)
    pane.roi_y_spin.setValue(0.4)

    assert pane.video_overlay.roi.x == 0.3
    assert pane.video_overlay.roi.y == 0.4


def test_open_video_sets_video_size_on_overlay(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)

    pane.open_video(test_video)

    assert pane.video_overlay._video_size == (32, 32)


def test_open_video_enables_dry_run_policy_action_and_preserves_run_ocr_semantics(
    qapp_guard, repository, test_video, tmp_path
):
    from tests.support.fake_ocr_engine import FakeOcrEngine

    db_path = tmp_path / "test_db.sqlite3"
    engine = FakeOcrEngine(regions=[])

    # Case 1: Fully wired with OCR engine and DB path
    pane = PathAMediaPane(repository, ocr_engine=engine, db_path=db_path)
    assert pane.dry_run_policy_button.isEnabled() is False
    assert pane.run_ocr_button.isEnabled() is True

    pane.open_video(test_video)

    assert pane.dry_run_policy_button.isEnabled() is True
    assert pane.run_ocr_button.isEnabled() is True

    # Case 2: Pane without OCR engine (Run OCR disabled, Dry Run enabled when video loaded)
    unwired_pane = PathAMediaPane(repository)
    assert unwired_pane.dry_run_policy_button.isEnabled() is False
    assert unwired_pane.run_ocr_button.isEnabled() is False

    unwired_pane.open_video(test_video)

    assert unwired_pane.dry_run_policy_button.isEnabled() is True
    assert unwired_pane.run_ocr_button.isEnabled() is False


