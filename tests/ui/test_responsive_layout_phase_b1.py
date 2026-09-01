from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QWidget,
)

from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.app import GlyphCueWorkbench, create_app
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.path_b_workspace import PathBWorkspace
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace


def test_workbench_splitter_stretch_factors_and_minimum_widths(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    splitter = workbench.findChild(QSplitter)
    assert splitter is not None

    # Panes must not collapse
    assert not splitter.isCollapsible(0)
    assert not splitter.isCollapsible(1)
    assert not splitter.isCollapsible(2)

    # Minimum widths
    left = splitter.widget(0)
    center = splitter.widget(1)
    right = splitter.widget(2)
    assert left.minimumWidth() >= 260
    assert center.minimumWidth() >= 400
    assert right.minimumWidth() >= 320


def test_right_qa_inspector_has_vertical_scroll_area_and_reflowed_timing_grid(qapp_guard, tmp_path):
    cue = Cue(
        id="c1",
        start_time=1.0,
        end_time=3.0,
        language_layers=[LanguageLayer("ja", "こんにちは")],
        review_state=ReviewState.PENDING,
    )
    qa = ReconstructionQaWorkspace(
        cues=[cue],
        observations_by_id={},
        priorities_by_cue_id={
            "c1": ReviewPriority(cue_id="c1", score=1.0, level="High", components=())
        },
        center_widget=QWidget(),
    )

    # Right pane must be wrapped in a vertical scroll area
    scroll_area = qa.window.findChild(QScrollArea, "rightPaneScrollArea")
    assert scroll_area is not None
    assert scroll_area.widgetResizable()
    assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    # Timing card buttons must be reflowed in a 2x2 grid (not 4 buttons in 1 row)
    timing_card = qa.window.findChild(QWidget, "timingCard")
    assert timing_card is not None
    grid_layout = timing_card.findChild(QGridLayout)
    assert grid_layout is not None
    assert grid_layout.rowCount() == 2
    assert grid_layout.columnCount() == 2


def test_left_pane_structure_scroll_region_preserves_persistent_queue_usability(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    pane = workbench.path_a_pane
    assert pane is not None

    # Structure card region must be in a scroll area so it never starves the queue
    structure_scroll = workbench.findChild(QScrollArea, "leftPaneStructureScroll")
    assert structure_scroll is not None
    assert structure_scroll.widgetResizable()

    # Search and Queue must remain in the persistent left layout
    assert not pane.qa.search_edit.isHidden()
    assert not pane.qa.queue.isHidden()


def test_cue_identity_label_uses_human_readable_title_while_preserving_id_tooltip(qapp_guard, tmp_path):
    cue = Cue(
        id="c001-uuid-very-long-raw-identifier",
        start_time=1.234,
        end_time=3.456,
        language_layers=[LanguageLayer("ja", "テスト")],
        review_state=ReviewState.PENDING,
    )
    qa = ReconstructionQaWorkspace(
        cues=[cue],
        observations_by_id={},
        priorities_by_cue_id={
            cue.id: ReviewPriority(cue_id=cue.id, score=1.0, level="High", components=())
        },
        center_widget=QWidget(),
    )

    label = qa.cue_identity_label
    assert label.text().startswith("Cue #1 ·")
    assert "c001-uuid-very-long-raw-identifier" not in label.text()
    assert "c001-uuid-very-long-raw-identifier" in label.toolTip()


def test_persistent_workbench_hides_redundant_in_pane_open_actions(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    pane = workbench.path_a_pane
    assert pane is not None

    # Redundant in-pane actions in Path A must be hidden when hosted by workbench
    assert not pane.open_button.isVisible()
    assert not pane.open_caption_file_button.isVisible()
