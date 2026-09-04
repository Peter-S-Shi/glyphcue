from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QMessageBox, QWidget

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.jobs.job import JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.repository import CueRepository
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.compact_timeline import CompactTimeline
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace


def _make_cue(id_, start, end, state=ReviewState.PENDING, text="test"):
    layer = LanguageLayer(language="en", text=text, observation_ids=())
    return Cue(id=id_, start_time=start, end_time=end, language_layers=(layer,), review_state=state)


def test_queue_strict_chronological_ordering_regardless_of_priority_or_state(qapp_guard):
    cues = [
        _make_cue("c3", 10.0, 12.0, state=ReviewState.APPROVED),
        _make_cue("c1", 1.0, 3.0, state=ReviewState.REJECTED),
        _make_cue("c2", 5.0, 7.0, state=ReviewState.NEEDS_REVIEW),
    ]
    priorities = {
        "c3": MagicMock(score=0.1, level="Low"),
        "c1": MagicMock(score=0.9, level="High"),
        "c2": MagicMock(score=0.5, level="Medium"),
    }
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    # Order must strictly follow timeline: c1 (1s), c2 (5s), c3 (10s)
    ordered_ids = [workspace.cue_id_for_row(i) for i in range(workspace.queue.count())]
    assert ordered_ids == ["c1", "c2", "c3"]
    assert "[1.00s]" in workspace.queue.item(0).text()
    assert "[5.00s]" in workspace.queue.item(1).text()
    assert "[10.00s]" in workspace.queue.item(2).text()


def test_queue_multi_select_and_batch_purge_discarded(qapp_guard):
    cues = [
        _make_cue("c1", 0.0, 1.0, state=ReviewState.APPROVED),
        _make_cue("c2", 1.0, 2.0, state=ReviewState.REJECTED),
        _make_cue("c3", 2.0, 3.0, state=ReviewState.REJECTED),
        _make_cue("c4", 3.0, 4.0, state=ReviewState.PENDING),
    ]
    workspace = ReconstructionQaWorkspace(cues, {}, {}, QWidget())

    # Multi-select c2, c3, and c4
    workspace.queue.clearSelection()
    workspace.queue.item(1).setSelected(True)
    workspace.queue.item(2).setSelected(True)
    workspace.queue.item(3).setSelected(True)

    # Click Purge Discarded
    workspace.purge_discarded_button.click()

    # c2 and c3 are purged because they are REJECTED
    # c1 (Approved) and c4 (Pending) are preserved
    remaining_ids = [c.id for c in workspace.cues]
    assert remaining_ids == ["c1", "c4"]
    assert workspace.queue.count() == 2
    assert workspace.cue_id_for_row(0) == "c1"
    assert workspace.cue_id_for_row(1) == "c4"


def test_timeline_endpoint_marker_and_resume_controls(qapp_guard, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = connect(db_path)
    tg_repo = TrackGroupRepository(conn)
    pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane._video_path = tmp_path / "dummy.mp4"
    pane._source_id = "dummy"
    pane._video_duration_seconds = 60.0

    # Initially, resume button disabled
    assert not pane.resume_from_last_end_button.isEnabled()
    assert pane.timeline.last_processed_end is None

    # Simulate OCR succeeded at 15.5s
    pane._current_processing_end_time = 15.5
    mock_job = MagicMock()
    mock_job.state = JobState.SUCCEEDED
    pane.current_ocr_job = mock_job
    pane._processing_range = MagicMock(start_time=0.0, end_time=15.5)

    with patch("glyphcue.ui.path_a_media_pane.play_ocr_completion_chime") as mock_chime:
        pane._on_ocr_finished()
        mock_chime.assert_called_once()

    # Timeline marker updated
    assert pane.timeline.last_processed_end == 15.5
    # Resume button enabled
    assert pane.resume_from_last_end_button.isEnabled()
    # Next range start auto-prefilled to 15.5s
    assert pane.limit_processing_range_checkbox.isChecked()
    assert abs(pane.processing_range_start_spin.value() - 15.5) < 0.01

    # Clicking "Resume from Last End" sets start spin and seeks
    with patch.object(pane.controller, "seek") as mock_seek:
        pane.processing_range_start_spin.setValue(0.0)
        pane.resume_from_last_end_button.click()
        assert abs(pane.processing_range_start_spin.value() - 15.5) < 0.01
        mock_seek.assert_called_with(15.5)


def test_timeline_click_to_seek_interaction(qapp_guard):
    timeline = CompactTimeline()
    timeline.set_data(duration_seconds=120.0, spans=[])
    timeline.resize(240, 28)

    received_seeks = []
    timeline.seek_requested.connect(received_seeks.append)

    # Click at x=60 (quarter of 240) -> 30.0s
    pos = QPointF(60.0, 10.0)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pos,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    timeline.mousePressEvent(event)

    assert len(received_seeks) == 1
    assert abs(received_seeks[0] - 30.0) < 0.1


def test_clear_current_video_cues_with_confirmation(qapp_guard, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = connect(db_path)
    cue_repo = CueRepository(conn)
    tg_repo = TrackGroupRepository(conn)
    # Save cues for two distinct sources
    source_a = "video_a"
    source_b = "video_b"
    cues_a = [_make_cue("ca1", 0.0, 2.0), _make_cue("ca2", 2.0, 4.0)]
    cues_b = [_make_cue("cb1", 1.0, 3.0)]
    cue_repo.save_cues_for_source(source_a, cues_a)
    cue_repo.save_cues_for_source(source_b, cues_b)

    pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane._source_id = source_a
    pane._video_path = Path("video_a.mp4")
    pane.qa.set_cues_and_priorities(cues_a, {}, {})
    pane.clear_video_cues_button.setEnabled(True)

    # 1. User cancels confirmation -> nothing cleared
    with patch.object(QMessageBox, "exec", return_value=0):
        with patch.object(QMessageBox, "clickedButton", return_value=None):
            pane.clear_video_cues_button.click()
            assert len(cue_repo.list_for_source(source_a)) == 2
            assert len(pane.qa.cues) == 2

    # 2. User confirms -> cues for source_a cleared, source_b completely preserved
    pane._clear_current_video_cues()

    assert cue_repo.list_for_source(source_a) == []
    assert len(cue_repo.list_for_source(source_b)) == 1
    assert pane.qa.cues == []
    assert pane.timeline.last_processed_end is None
    assert not pane.clear_video_cues_button.isEnabled()
    assert not pane.resume_from_last_end_button.isEnabled()
