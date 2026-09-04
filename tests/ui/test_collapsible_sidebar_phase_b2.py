from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QWidget,
)

from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.app import create_app
from glyphcue.ui.collapsible_section import CollapsibleSection
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace


def test_collapsible_section_toggle_and_indicator(qapp_guard):
    content = QLabel("Section Inner Content")
    section = CollapsibleSection("STRUCTURE & REGION", content=content, expanded=True)

    assert section.is_expanded()
    assert "▼" in section.header_text()
    assert not content.isHidden()

    # Toggle to collapsed
    section.toggle()
    assert not section.is_expanded()
    assert "▶" in section.header_text()
    assert content.isHidden()

    # Set expanded True
    section.set_expanded(True)
    assert section.is_expanded()
    assert "▼" in section.header_text()
    assert not content.isHidden()


def test_left_sidebar_has_independent_collapsible_work_areas(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    qa = workbench.path_a_pane.qa

    assert hasattr(qa, "structure_section")
    assert hasattr(qa, "queue_section")
    assert hasattr(qa, "context_section")

    # Verify default expanded states
    assert qa.structure_section.is_expanded()
    assert qa.queue_section.is_expanded()
    assert not qa.context_section.is_expanded()

    # Non-exclusive behavior: collapsing structure section keeps queue section expanded
    qa.structure_section.set_expanded(False)
    assert not qa.structure_section.is_expanded()
    assert qa.queue_section.is_expanded()


def test_structure_section_contains_production_roi_and_range_controls(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    pane = workbench.path_a_pane

    # Structure section must contain all production ROI & range controls
    assert pane.roi_x_spin.parentWidget() is not None
    assert pane.reset_roi_button.parentWidget() is not None
    assert pane.limit_processing_range_checkbox.parentWidget() is not None
    assert pane.language_selection_panel.parentWidget() is not None
    assert pane.save_roi_button.parentWidget() is not None


def test_cue_queue_section_contains_search_filter_and_queue_list(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    qa = workbench.path_a_pane.qa

    assert qa.search_edit.parentWidget() is not None
    assert qa.filter_combo.parentWidget() is not None
    assert qa.queue.parentWidget() is not None


def test_playback_and_cue_selection_preserve_user_disclosure_state(qapp_guard, tmp_path):
    cue1 = Cue(
        id="c1",
        start_time=1.0,
        end_time=2.0,
        language_layers=[LanguageLayer("ja", "1")],
        review_state=ReviewState.PENDING,
    )
    cue2 = Cue(
        id="c2",
        start_time=2.5,
        end_time=4.0,
        language_layers=[LanguageLayer("ja", "2")],
        review_state=ReviewState.PENDING,
    )
    qa = ReconstructionQaWorkspace(
        cues=[cue1, cue2],
        observations_by_id={},
        priorities_by_cue_id={
            "c1": ReviewPriority(cue_id="c1", score=1.0, level="High", components=()),
            "c2": ReviewPriority(cue_id="c2", score=0.5, level="Medium", components=()),
        },
        center_widget=QWidget(),
    )

    # User collapses structure and queue
    qa.structure_section.set_expanded(False)
    qa.context_section.set_expanded(True)

    # Trigger playback change & cue navigation
    qa.set_playback_active_cue_id("c2")
    qa.go_to_next()

    # Disclosure state must remain strictly preserved
    assert not qa.structure_section.is_expanded()
    assert qa.context_section.is_expanded()
