from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.persistence.database import connect
from glyphcue.persistence.repository import CueRepository
from glyphcue.ui.app import create_app


def test_discard_latest_run_cancel_preserves_workspace_and_button_state(qapp_guard, tmp_path):
    db_path = tmp_path / "glyphcue.sqlite3"
    app, workbench = create_app(db_path=db_path)
    pane = workbench.path_a_pane
    pane._source_id = "test_source"

    pre_cue = Cue(
        id="c_pre",
        start_time=0.0,
        end_time=1.0,
        language_layers=[LanguageLayer("ja", "初期")],
        review_state=ReviewState.APPROVED,
    )
    new_cue = Cue(
        id="c_new",
        start_time=1.0,
        end_time=2.0,
        language_layers=[LanguageLayer("ja", "新規")],
        review_state=ReviewState.PENDING,
    )

    repo = CueRepository(connect(db_path))
    repo.save_cues_for_source("test_source", [pre_cue, new_cue])
    pane._cue_repository = repo
    pane._last_pre_run_cues = [pre_cue]
    pane.qa.set_cues_and_priorities([pre_cue, new_cue], {}, {})
    pane.discard_latest_run_button.setEnabled(True)

    # When user cancels the modal confirmation dialog
    with patch.object(QMessageBox, "exec", return_value=None):
        with patch.object(QMessageBox, "clickedButton", return_value=None):
            pane.discard_latest_run_button.click()

    # Workspace and cues must remain unchanged
    assert len(pane.qa.cues) == 2
    assert pane._last_pre_run_cues == [pre_cue]
    assert pane.discard_latest_run_button.isEnabled()


def test_discard_latest_run_confirm_executes_rollback(qapp_guard, tmp_path):
    db_path = tmp_path / "glyphcue.sqlite3"
    app, workbench = create_app(db_path=db_path)
    pane = workbench.path_a_pane
    pane._source_id = "test_source"

    pre_cue = Cue(
        id="c_pre",
        start_time=0.0,
        end_time=1.0,
        language_layers=[LanguageLayer("ja", "初期")],
        review_state=ReviewState.APPROVED,
    )
    new_cue = Cue(
        id="c_new",
        start_time=1.0,
        end_time=2.0,
        language_layers=[LanguageLayer("ja", "新規")],
        review_state=ReviewState.PENDING,
    )

    repo = CueRepository(connect(db_path))
    repo.save_cues_for_source("test_source", [pre_cue, new_cue])
    pane._cue_repository = repo
    pane._last_pre_run_cues = [pre_cue]
    pane.qa.set_cues_and_priorities([pre_cue, new_cue], {}, {})
    pane.discard_latest_run_button.setEnabled(True)

    # When user confirms discard in modal dialog
    with patch.object(QMessageBox, "exec", return_value=None):
        with patch.object(
            QMessageBox,
            "clickedButton",
            lambda self: next((b for b in self.buttons() if "Discard" in b.text()), None),
        ):
            pane.discard_latest_run_button.click()

    # Workspace should be rolled back to pre-run cues
    assert len(pane.qa.cues) == 1
    assert pane.qa.cues[0].id == "c_pre"
    assert pane._last_pre_run_cues is None
    assert not pane.discard_latest_run_button.isEnabled()
    assert "discarded" in pane.ocr_status_label.text()


def test_per_cue_discard_has_no_confirmation_dialog(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    qa = workbench.path_a_pane.qa

    cue = Cue(
        id="c1",
        start_time=0.0,
        end_time=1.0,
        language_layers=[LanguageLayer("ja", "テスト")],
        review_state=ReviewState.PENDING,
    )
    qa.set_cues_and_priorities([cue], {}, {})
    assert len(qa.cues) == 1

    with patch.object(QMessageBox, "exec") as mock_exec:
        qa.discard_button.click()
        # Routine per-cue discard must never show modal confirmation dialog
        mock_exec.assert_not_called()

    assert len(qa.cues) == 1
    assert qa.cues[0].review_state == ReviewState.REJECTED
