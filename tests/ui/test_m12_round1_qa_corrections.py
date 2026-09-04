from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QListWidgetItem, QScrollArea, QSplitter, QWidget

from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.app import GlyphCueWorkbench, create_app
from glyphcue.ui.design_tokens import Color
from glyphcue.ui.reconstruction_qa_workspace import (
    REVIEW_STATE_ROLE,
    CueQueueItemDelegate,
    ReconstructionQaWorkspace,
    border_color_for_cue_item,
)


def _cue(cue_id: str, start: float, end: float, review_state=ReviewState.PENDING) -> Cue:
    return Cue(
        id=cue_id,
        start_time=start,
        end_time=end,
        language_layers=[LanguageLayer("en", f"Text for {cue_id}")],
        review_state=review_state,
    )


def test_border_color_for_cue_item_mapping_and_selection_override():
    # 1. Status -> Border mapping when unselected
    assert border_color_for_cue_item(ReviewState.APPROVED, is_selected=False) == Color.SUCCESS
    assert border_color_for_cue_item(ReviewState.PENDING, is_selected=False) == Color.BORDER_NEUTRAL_LIGHT
    assert border_color_for_cue_item(ReviewState.NEEDS_REVIEW, is_selected=False) == Color.WARNING
    assert border_color_for_cue_item(ReviewState.REJECTED, is_selected=False) == Color.DANGER

    # Also string representations
    assert border_color_for_cue_item("APPROVED", is_selected=False) == Color.SUCCESS
    assert border_color_for_cue_item("REJECTED", is_selected=False) == Color.DANGER
    assert border_color_for_cue_item("NEEDS_REVIEW", is_selected=False) == Color.WARNING
    assert border_color_for_cue_item(None, is_selected=False) == Color.BORDER_NEUTRAL_LIGHT

    # 2. Selection override has highest visual priority across all states
    for state in [
        ReviewState.APPROVED,
        ReviewState.PENDING,
        ReviewState.NEEDS_REVIEW,
        ReviewState.REJECTED,
        None,
    ]:
        assert border_color_for_cue_item(state, is_selected=True) == Color.ACCENT


def test_queue_items_store_review_state_role_and_update_on_review_actions(qapp_guard):
    cues = [
        _cue("c1", 0.0, 1.0, review_state=ReviewState.PENDING),
        _cue("c2", 1.0, 2.0, review_state=ReviewState.NEEDS_REVIEW),
    ]
    workspace = ReconstructionQaWorkspace(cues, {}, {}, QWidget())

    assert workspace.queue.count() == 2
    item1 = workspace.queue.item(0)
    item2 = workspace.queue.item(1)

    assert item1.data(REVIEW_STATE_ROLE) == ReviewState.PENDING
    assert item2.data(REVIEW_STATE_ROLE) == ReviewState.NEEDS_REVIEW

    # Approve c1
    workspace.queue.setCurrentRow(0)
    workspace.approve_and_advance()
    assert workspace.queue.item(0).data(REVIEW_STATE_ROLE) == ReviewState.APPROVED

    # Discard c2
    workspace.queue.setCurrentRow(1)
    workspace.discard_active_cue()
    assert workspace.queue.item(1).data(REVIEW_STATE_ROLE) == ReviewState.REJECTED


def test_queue_delegate_renders_without_crash(qapp_guard):
    cues = [
        _cue("c1", 0.0, 1.0, review_state=ReviewState.APPROVED),
        _cue("c2", 1.0, 2.0, review_state=ReviewState.REJECTED),
        _cue("c3", 2.0, 3.0, review_state=ReviewState.NEEDS_REVIEW),
        _cue("c4", 3.0, 4.0, review_state=ReviewState.PENDING),
    ]
    workspace = ReconstructionQaWorkspace(cues, {}, {}, QWidget())
    workspace.queue.resize(300, 300)

    img = QImage(300, 300, QImage.Format.Format_RGB32)
    workspace.queue.render(img)

    assert isinstance(workspace.queue.itemDelegate(), CueQueueItemDelegate)


def test_workbench_global_horizontal_scroll_area_configuration(qapp_guard, tmp_path):
    db_path = tmp_path / "test_scroll_config.sqlite3"
    _app, workbench = create_app(db_path=db_path)

    scroll_area = workbench.findChild(QScrollArea, "workbenchScrollArea")
    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True
    assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded

    # Child splitter is accessible
    splitter = workbench.findChild(QSplitter)
    assert splitter is not None
    assert splitter.count() == 3


def test_workbench_horizontal_overflow_activates_on_narrow_window_and_hides_on_normal(
    qapp_guard, tmp_path
):
    db_path = tmp_path / "test_scroll_overflow.sqlite3"
    _app, workbench = create_app(db_path=db_path)
    workbench.resize(1280, 720)
    workbench.show()

    for _ in range(5):
        qapp_guard.processEvents()

    scroll_area = workbench.findChild(QScrollArea, "workbenchScrollArea")
    assert scroll_area is not None
    h_bar = scroll_area.horizontalScrollBar()

    # Normal width (1280px >= 1160px min width) -> scrollbar max is 0 (not active)
    assert h_bar.maximum() == 0

    # Narrow width (900px < 1160px min width) -> scrollbar max > 0 (active overflow)
    workbench.resize(900, 720)
    for _ in range(5):
        qapp_guard.processEvents()

    assert h_bar.maximum() > 0

    # Switching mode to Path B preserves the scroll area structure
    workbench.switch_to_mode("path_b")
    for _ in range(5):
        qapp_guard.processEvents()

    assert workbench.findChild(QScrollArea, "workbenchScrollArea") is not None
