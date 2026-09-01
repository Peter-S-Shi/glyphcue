from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QLabel,
    QWidget,
)

from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.app import create_app
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace


def test_split_point_has_explicit_split_at_label(qapp_guard, tmp_path):
    cue = Cue(
        id="c1",
        start_time=1.0,
        end_time=3.0,
        language_layers=[LanguageLayer("ja", "テスト")],
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

    split_label = qa.window.findChild(QLabel, "splitTimeLabel")
    assert split_label is not None
    assert "Split at" in split_label.text()


def test_ocr_action_box_has_always_visible_live_range_summary(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    pane = workbench.path_a_pane
    assert pane is not None

    summary_label = pane.qa.window.findChild(QLabel, "ocrRangeSummaryLabel") or workbench.findChild(
        QLabel, "ocrRangeSummaryLabel"
    )
    assert summary_label is not None

    # Initial state without limit
    assert not pane.limit_processing_range_checkbox.isChecked()
    assert "Range: Whole media" in summary_label.text()

    # Turn on range limits
    pane.limit_processing_range_checkbox.setChecked(True)
    pane.processing_range_start_spin.setValue(1.50)
    pane.processing_range_end_spin.setValue(6.80)

    # Must update live without launching OCR
    assert "Range: 1.50s–6.80s · 5.30s selected" in summary_label.text()

    # Turn off range limits
    pane.limit_processing_range_checkbox.setChecked(False)
    assert "Range: Whole media" in summary_label.text()
