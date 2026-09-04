from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSplitter,
    QWidget,
)

from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.app import GlyphCueWorkbench, create_app
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace


def test_top_app_chrome_visual_hierarchy_and_object_names(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    header = workbench.findChild(QWidget, "appHeader")
    assert header is not None

    brand_logo = workbench.findChild(QLabel, "brandLogoBox")
    assert brand_logo is not None
    assert brand_logo.text() == "GC"

    brand_label = workbench.findChild(QLabel, "brandLabel")
    assert brand_label is not None
    assert brand_label.text() == "GlyphCue"

    app_badge = workbench.findChild(QLabel, "appBadge")
    assert app_badge is not None

    mode_nav = workbench.findChild(QWidget, "modeNavContainer")
    assert mode_nav is not None
    assert workbench.path_a_mode_button.objectName() == "modeBtn"
    assert workbench.path_b_mode_button.objectName() == "modeBtn"

    assert workbench.asset_status_label.objectName() == "assetStatusPill"


def test_left_pane_structure_card_and_cue_queue(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    structure_card = workbench.findChild(QWidget, "structureCard")
    assert structure_card is not None

    cue_list = workbench.findChild(QListWidget, "cueList")
    assert cue_list is not None


def test_center_pane_video_viewport_and_ocr_action_box(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    video_viewport = workbench.findChild(QWidget, "videoViewport")
    assert video_viewport is not None

    ocr_box = workbench.findChild(QWidget, "ocrActionBox")
    assert ocr_box is not None

    pane = workbench.path_a_pane
    assert pane.run_ocr_button.objectName() == "runOcrBtn"
    assert pane.cancel_ocr_button.objectName() == "secondaryBtn"
    assert pane.discard_latest_run_button.objectName() == "subtleDangerBtn"


def test_right_pane_qa_cards_and_action_button_hierarchy(qapp_guard, tmp_path):
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

    header_card = qa.window.findChild(QWidget, "qaHeaderCard")
    assert header_card is not None

    timing_card = qa.window.findChild(QWidget, "timingCard")
    assert timing_card is not None

    evidence_card = qa.window.findChild(QWidget, "evidenceCard")
    assert evidence_card is not None

    assert qa.approve_button.objectName() == "approveButton"
    assert qa.discard_button.objectName() == "discardButton"
    assert qa.split_button.objectName() == "secondaryBtn"
    assert qa.merge_next_button.objectName() == "secondaryBtn"
