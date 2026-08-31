from glyphcue.application.thin_path_b import parse_and_reconstruct
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.path_b_workspace import PathBWorkspace

_ROLLING_SRT = """1
00:00:00,000 --> 00:00:02,000
Hello

2
00:00:01,000 --> 00:00:04,000
Hello world

3
00:00:03,000 --> 00:00:06,000
Hello world, how are you
"""


def test_full_vertical_slice_import_review_approve_export(qapp_guard, tmp_path):
    source = tmp_path / "input.srt"
    source.write_text(_ROLLING_SRT, encoding="utf-8")
    destination = tmp_path / "input.reconstructed.srt"

    cues, observations_by_id, diagnostics_by_cue_id, _import_warnings = parse_and_reconstruct(source)
    workspace = PathBWorkspace(
        cues, observations_by_id, source, destination, diagnostics_by_cue_id=diagnostics_by_cue_id
    )

    # Queue selection + active Cue + source observations
    workspace.queue.setCurrentRow(0)
    assert workspace.active_cue is not None
    assert "Hello" in workspace.qa.language_layers_panel.cards[0].current_text()

    # Editable text + Approve
    workspace.qa.language_layers_panel.cards[0].text_edit.setPlainText(
        "Hello world, how are you doing"
    )
    workspace.qa.approve_button.click()
    assert workspace.cues[0].review_state is ReviewState.APPROVED
    assert workspace.cues[0].language_layers[0].text == "Hello world, how are you doing"

    # Export (non-destructive)
    workspace.export_button.click()

    assert source.read_text(encoding="utf-8") == _ROLLING_SRT
    assert destination.exists()
    assert destination != source
    exported_text = destination.read_text(encoding="utf-8")
    assert "Hello world, how are you doing" in exported_text
