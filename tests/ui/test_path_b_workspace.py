import pytest

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.path_b_workspace import PathBWorkspace


def _observation(id_: str, text: str) -> Observation:
    return Observation(
        id=id_,
        text=text,
        start_time=0.0,
        end_time=1.0,
        provenance=Provenance(kind=ProvenanceKind.SUBTITLE_IMPORT, source="input.srt"),
    )


def _cue(id_: str, text: str, observation_ids=()) -> Cue:
    return Cue(
        id=id_,
        start_time=0.0,
        end_time=1.0,
        language_layers=(
            LanguageLayer(language="en", text=text, observation_ids=observation_ids),
        ),
    )


def test_workspace_lists_every_cue_in_the_queue(qapp_guard, tmp_path):
    cues = [_cue("c1", "first"), _cue("c2", "second")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt", tmp_path / "out.srt")

    assert workspace.queue.count() == 2


def test_selecting_a_queue_row_sets_the_active_cue(qapp_guard, tmp_path):
    cues = [_cue("c1", "first"), _cue("c2", "second")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt", tmp_path / "out.srt")

    workspace.queue.setCurrentRow(1)

    assert workspace.active_cue.id == "c2"
    assert workspace.qa.language_layers_panel.cards[0].current_text() == "second"


def test_selecting_a_queue_row_shows_a_consolidation_explanation(qapp_guard, tmp_path):
    observations = {"o1": _observation("o1", "raw ocr text one")}
    cues = [_cue("c1", "reconstructed", observation_ids=("o1",))]
    workspace = PathBWorkspace(cues, observations, tmp_path / "input.srt", tmp_path / "out.srt")

    workspace.queue.setCurrentRow(0)

    assert "o1" in workspace.consolidation_view.toPlainText()
    assert "c1" in workspace.consolidation_view.toPlainText()


def test_approve_updates_review_state_and_commits_edited_text(qapp_guard, tmp_path):
    cues = [_cue("c1", "original")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt", tmp_path / "out.srt")
    workspace.queue.setCurrentRow(0)

    workspace.qa.language_layers_panel.cards[0].text_edit.setPlainText("corrected")
    workspace.qa.approve_button.click()

    approved = workspace.cues[0]
    assert approved.review_state is ReviewState.APPROVED
    assert approved.language_layers[0].text == "corrected"


def test_export_writes_a_new_file_and_preserves_no_source_reference(qapp_guard, tmp_path):
    cues = [_cue("c1", "final text")]
    destination = tmp_path / "out.srt"
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt", destination)
    workspace.queue.setCurrentRow(0)

    workspace.export_button.click()

    assert destination.exists()
    assert "final text" in destination.read_text(encoding="utf-8")


def test_export_refuses_to_overwrite_the_source_path(qapp_guard, tmp_path):
    source = tmp_path / "input.srt"
    source.write_text("original source content", encoding="utf-8")
    cues = [_cue("c1", "final text")]
    # Constructed with export_destination == source_path: the workspace
    # itself must refuse this, not rely on the caller having picked a
    # different path.
    workspace = PathBWorkspace(cues, {}, source, source)
    workspace.queue.setCurrentRow(0)

    with pytest.raises(ValueError):
        workspace.export()

    assert source.read_text(encoding="utf-8") == "original source content"


def test_export_button_click_refuses_to_overwrite_source_without_crashing(qapp_guard, tmp_path):
    source = tmp_path / "input.srt"
    source.write_text("original source content", encoding="utf-8")
    cues = [_cue("c1", "final text")]
    workspace = PathBWorkspace(cues, {}, source, source)
    workspace.queue.setCurrentRow(0)

    workspace.export_button.click()

    assert source.read_text(encoding="utf-8") == "original source content"
    assert "refus" in workspace.status_label.text().lower()


def test_path_b_cues_show_no_review_flags_not_a_fabricated_priority(qapp_guard, tmp_path):
    # Path B's reconstruction has no OCR-confidence/disagreement
    # diagnostics to score with -- this must show up honestly as "no
    # signal", never a made-up score.
    cues = [_cue("c1", "clean import")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt", tmp_path / "out.srt")

    workspace.queue.setCurrentRow(0)

    assert "None" in workspace.qa.priority_label.text()
