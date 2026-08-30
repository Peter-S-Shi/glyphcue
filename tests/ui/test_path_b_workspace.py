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
    workspace = PathBWorkspace(cues, {}, tmp_path / "out.srt")

    assert workspace.queue.count() == 2


def test_selecting_a_queue_row_sets_the_active_cue(qapp_guard, tmp_path):
    cues = [_cue("c1", "first"), _cue("c2", "second")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "out.srt")

    workspace.queue.setCurrentRow(1)

    assert workspace.active_cue.id == "c2"
    assert workspace.text_edit.toPlainText() == "second"


def test_selecting_a_queue_row_shows_source_observations_as_evidence(qapp_guard, tmp_path):
    observations = {"o1": _observation("o1", "raw ocr text one")}
    cues = [_cue("c1", "reconstructed", observation_ids=("o1",))]
    workspace = PathBWorkspace(cues, observations, tmp_path / "out.srt")

    workspace.queue.setCurrentRow(0)

    assert "raw ocr text one" in workspace.evidence_view.toPlainText()


def test_approve_updates_review_state_and_commits_edited_text(qapp_guard, tmp_path):
    cues = [_cue("c1", "original")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "out.srt")
    workspace.queue.setCurrentRow(0)

    workspace.text_edit.setPlainText("corrected")
    workspace.approve_button.click()

    approved = workspace.cues[0]
    assert approved.review_state is ReviewState.APPROVED
    assert approved.language_layers[0].text == "corrected"


def test_export_writes_a_new_file_and_preserves_no_source_reference(qapp_guard, tmp_path):
    cues = [_cue("c1", "final text")]
    destination = tmp_path / "out.srt"
    workspace = PathBWorkspace(cues, {}, destination)
    workspace.queue.setCurrentRow(0)

    workspace.export_button.click()

    assert destination.exists()
    assert "final text" in destination.read_text(encoding="utf-8")
