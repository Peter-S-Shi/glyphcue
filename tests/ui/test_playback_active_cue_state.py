from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace


def _cue(id_, start, end, texts=None):
    texts = texts or {"en": f"Text for {id_}"}
    layers = tuple(
        LanguageLayer(language=language, text=text, observation_ids=())
        for language, text in texts.items()
    )
    return Cue(id=id_, start_time=start, end_time=end, language_layers=layers)


def _none_priority(cue_id):
    return ReviewPriority(cue_id=cue_id, score=0.0, level="None", components=())


def _write_test_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, 3000, 100):
        array = np.full((32, 32, 3), 100, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def test_reconstruction_qa_workspace_playback_active_cue_does_not_steal_editing_selection(
    qapp_guard,
):
    c1 = _cue("c1", 0.0, 1.0, {"en": "Original C1 Text"})
    c2 = _cue("c2", 1.0, 2.0, {"en": "Original C2 Text"})
    cues = [c1, c2]
    priorities = {"c1": _none_priority("c1"), "c2": _none_priority("c2")}

    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    # User explicitly selects c1 and types uncommitted edits into language layer text edit
    workspace.queue.setCurrentRow(0)
    assert workspace.active_cue.id == "c1"
    assert workspace.playback_active_cue_id is None

    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Dirty Uncommitted C1 Text")

    # Playback reaches time 1.5s (which corresponds to c2)
    workspace.set_playback_active_cue_id("c2")

    # Verify DOG-007: playback-active cue is c2, but user-selected/editing cue remains c1
    assert workspace.playback_active_cue_id == "c2"
    assert workspace.active_cue.id == "c1"
    assert (
        workspace.language_layers_panel.cards[0].text_edit.toPlainText()
        == "Dirty Uncommitted C1 Text"
    )

    # Setting playback active back to None or c1 maintains c1 selection
    workspace.set_playback_active_cue_id(None)
    assert workspace.playback_active_cue_id is None
    assert workspace.active_cue.id == "c1"


def test_queue_item_shows_playback_active_visual_state(qapp_guard):
    c1 = _cue("c1", 0.0, 1.0, {"en": "First"})
    c2 = _cue("c2", 1.0, 2.0, {"en": "Second"})
    workspace = ReconstructionQaWorkspace(
        [c1, c2], {}, {"c1": _none_priority("c1"), "c2": _none_priority("c2")}, QWidget()
    )

    workspace.set_playback_active_cue_id("c2")

    # Item c2 should reflect playback active indicator
    item_c2 = workspace.queue.item(1)
    assert item_c2.data(Qt.ItemDataRole.UserRole) == "c2"
    assert "▶" in item_c2.text() or item_c2.data(Qt.ItemDataRole.UserRole + 1) == "playback-active"

    # Item c1 should not have playback active marker
    item_c1 = workspace.queue.item(0)
    assert "▶" not in item_c1.text()


def test_path_a_media_pane_playback_updates_playback_active_cue_without_clobbering_selected_cue(
    qapp_guard, tmp_path
):
    video_path = tmp_path / "test.mp4"
    _write_test_video(video_path)

    conn = connect(tmp_path / "db.sqlite3")
    repo = TrackGroupRepository(conn)
    pane = PathAMediaPane(repo, db_path=tmp_path / "db.sqlite3")
    pane.open_video(video_path)

    c1 = _cue("c1", 0.0, 1.0, {"en": "Cue 1 Text"})
    c2 = _cue("c2", 1.0, 2.0, {"en": "Cue 2 Text"})
    pane.qa.set_cues_and_priorities(
        [c1, c2], {}, {"c1": _none_priority("c1"), "c2": _none_priority("c2")}
    )

    # User selects c1
    pane.qa.queue.setCurrentRow(0)
    assert pane.qa.active_cue.id == "c1"

    # Playback position moves to 1.5s (1500 ms) inside c2
    pane._on_playback_position_changed(1500)

    # Active cue being edited remains c1, while playback active cue is c2
    assert pane.qa.playback_active_cue_id == "c2"
    assert pane.qa.active_cue.id == "c1"
    assert "Cue c2" in pane.current_cue_relationship_label.text()
