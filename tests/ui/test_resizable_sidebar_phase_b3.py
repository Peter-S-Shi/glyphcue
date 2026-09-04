from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QListWidget,
    QScrollArea,
    QSplitter,
    QWidget,
)

from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.app import create_app
from glyphcue.ui.collapsible_section import CollapsibleSection
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace


def test_left_sidebar_has_vertical_splitter_for_work_areas(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    qa = workbench.path_a_pane.qa

    splitter = workbench.findChild(QSplitter, "leftSidebarSplitter")
    assert splitter is not None
    assert splitter.orientation() == Qt.Orientation.Vertical
    assert not splitter.childrenCollapsible()

    # Splitter must contain structure_section and queue_section
    assert splitter.indexOf(qa.structure_section) != -1
    assert splitter.indexOf(qa.queue_section) != -1


def test_structure_section_has_internal_scroll_area_and_minimum_usable_height(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    qa = workbench.path_a_pane.qa

    # Structure section must have an internal scroll area
    scroll_area = qa.structure_section.findChild(QScrollArea)
    assert scroll_area is not None
    assert scroll_area.widgetResizable()
    assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    # When expanded, minimum usable height is preserved so widgets are not crushed
    assert qa.structure_section.min_expanded_height >= 120
    assert qa.structure_section.minimumHeight() >= 120


def test_collapsing_structure_section_locks_to_header_and_restores_on_expand(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    qa = workbench.path_a_pane.qa

    section = qa.structure_section
    assert section.is_expanded()
    assert section.maximumHeight() > 10000

    # Collapse locks height down to header height
    section.set_expanded(False)
    assert not section.is_expanded()
    assert section.maximumHeight() <= 36

    # Expand restores height bounds
    section.set_expanded(True)
    assert section.is_expanded()
    assert section.maximumHeight() > 10000
    assert section.minimumHeight() >= 120


def test_collapsing_queue_section_locks_to_header_and_restores_on_expand(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    qa = workbench.path_a_pane.qa

    section = qa.queue_section
    assert section.is_expanded()
    assert section.maximumHeight() > 10000

    # Collapse locks height down to header height
    section.set_expanded(False)
    assert not section.is_expanded()
    assert section.maximumHeight() <= 36

    # Expand restores height bounds
    section.set_expanded(True)
    assert section.is_expanded()
    assert section.maximumHeight() > 10000


def test_search_and_filter_fixed_at_top_of_queue_section_with_queue_scrolling(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    qa = workbench.path_a_pane.qa

    # Search and filter must be direct children of queue_section content above QListWidget
    assert qa.search_edit.parentWidget() == qa.queue_section.content_widget
    assert qa.filter_combo.parentWidget() == qa.queue_section.content_widget
    assert qa.queue.parentWidget() == qa.queue_section.content_widget
    assert isinstance(qa.queue, QListWidget)
