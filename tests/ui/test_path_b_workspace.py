import pytest

from glyphcue.adapters.pysubs2_subtitle_io import ImportWarning
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.path_b_workspace import PathBWorkspace


def _observation(id_: str, text: str, start: float = 0.0, end: float = 1.0) -> Observation:
    return Observation(
        id=id_,
        text=text,
        start_time=start,
        end_time=end,
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
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")

    assert workspace.queue.count() == 2


def test_selecting_a_queue_row_sets_the_active_cue(qapp_guard, tmp_path):
    cues = [_cue("c1", "first"), _cue("c2", "second")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")

    workspace.queue.setCurrentRow(1)

    assert workspace.active_cue.id == "c2"
    assert workspace.qa.language_layers_panel.cards[0].current_text() == "second"


def test_selecting_a_queue_row_shows_a_consolidation_explanation(qapp_guard, tmp_path):
    observations = {"o1": _observation("o1", "raw ocr text one")}
    cues = [_cue("c1", "reconstructed", observation_ids=("o1",))]
    workspace = PathBWorkspace(cues, observations, tmp_path / "input.srt")

    workspace.queue.setCurrentRow(0)

    assert "o1" in workspace.consolidation_view.toPlainText()
    assert "c1" in workspace.consolidation_view.toPlainText()


def test_selecting_a_queue_row_shows_the_raw_timed_caption_stream(qapp_guard, tmp_path):
    # DESIGN.md section 14.1: source observation id/timing/text must be
    # directly visible, not only summarized in the consolidation text.
    observations = {"o1": _observation("o1", "raw ocr text one", start=1.5, end=3.0)}
    cues = [_cue("c1", "reconstructed", observation_ids=("o1",))]
    workspace = PathBWorkspace(cues, observations, tmp_path / "input.srt")

    workspace.queue.setCurrentRow(0)

    raw_text = workspace.raw_stream_view.toPlainText()
    assert "o1" in raw_text
    assert "1.500" in raw_text
    assert "raw ocr text one" in raw_text


def test_selecting_a_queue_row_shows_the_timing_collision_track(qapp_guard, tmp_path):
    # DESIGN.md section 14.3: source spans and the reconstructed span
    # must both be inspectable, and a real timing collision must be
    # visibly flagged, not only present in the raw diagnostics object.
    from glyphcue.application.reconstruction import PathBDiagnostics

    observations = {"o1": _observation("o1", "first", start=0.0, end=2.0)}
    cues = [_cue("c1", "first", observation_ids=("o1",))]
    diagnostics_by_cue_id = {
        "c1": PathBDiagnostics(
            cue_id="c1", source_order_issue=False, rolling_growth=False,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=True, segmentation_ambiguous=False,
        ),
    }
    workspace = PathBWorkspace(
        cues, observations, tmp_path / "input.srt", diagnostics_by_cue_id=diagnostics_by_cue_id
    )

    workspace.queue.setCurrentRow(0)

    timing_text = workspace.timing_view.toPlainText().lower()
    assert "o1" in timing_text
    assert "collision" in timing_text


def test_clean_pass_through_cue_shows_preserved_1_to_1_state(qapp_guard, tmp_path):
    # DESIGN.md section 17: a structurally normal caption GlyphCue did
    # not need to touch must say so explicitly, not show a blank
    # explanation indistinguishable from "no diagnostics available".
    from glyphcue.application.reconstruction import PathBDiagnostics

    cues = [_cue("c1", "clean line", observation_ids=("o1",))]
    diagnostics_by_cue_id = {
        "c1": PathBDiagnostics(
            cue_id="c1", source_order_issue=False, rolling_growth=False,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=False, segmentation_ambiguous=False,
        ),
    }
    workspace = PathBWorkspace(
        cues, {}, tmp_path / "input.srt", diagnostics_by_cue_id=diagnostics_by_cue_id
    )

    workspace.queue.setCurrentRow(0)

    text = workspace.consolidation_view.toPlainText().lower()
    assert "preserved 1:1" in text


def test_selecting_a_queue_row_populates_the_timeline_with_source_and_reconstructed_spans(
    qapp_guard, tmp_path
):
    # DESIGN.md section 49: Path B's compact timeline must show source
    # overlap/timing density and the reconstructed Cue span -- not just
    # prose (that is `timing_view`'s job).
    observations = {"o1": _observation("o1", "raw", start=0.0, end=2.0)}
    cues = [_cue("c1", "reconstructed", observation_ids=("o1",))]
    workspace = PathBWorkspace(cues, observations, tmp_path / "input.srt")

    workspace.queue.setCurrentRow(0)

    roles = {span[2] for span in workspace.timeline.spans}
    assert "source" in roles
    assert "reconstructed" in roles


def test_timeline_marks_a_timing_collision_span(qapp_guard, tmp_path):
    from glyphcue.application.reconstruction import PathBDiagnostics

    observations = {"o1": _observation("o1", "raw", start=0.0, end=2.0)}
    cues = [_cue("c1", "reconstructed", observation_ids=("o1",))]
    diagnostics_by_cue_id = {
        "c1": PathBDiagnostics(
            cue_id="c1", source_order_issue=False, rolling_growth=False,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=True, segmentation_ambiguous=False,
        ),
    }
    workspace = PathBWorkspace(
        cues, observations, tmp_path / "input.srt", diagnostics_by_cue_id=diagnostics_by_cue_id
    )

    workspace.queue.setCurrentRow(0)

    roles = {span[2] for span in workspace.timeline.spans}
    assert "collision" in roles


def test_left_pane_shows_the_ingestion_profile(qapp_guard, tmp_path):
    observations = {"o1": _observation("o1", "a"), "o2": _observation("o2", "b")}
    cues = [_cue("c1", "merged", observation_ids=("o1", "o2"))]
    workspace = PathBWorkspace(cues, observations, tmp_path / "input.srt")

    profile_text = workspace.ingestion_profile_label.text()
    assert "input.srt" in profile_text
    assert "SRT" in profile_text
    assert "2" in profile_text  # source cue count
    assert "1" in profile_text  # output cue count
    assert "protected" in profile_text.lower()


def test_ingestion_profile_source_cue_count_includes_recoverable_skipped_events(
    qapp_guard, tmp_path
):
    # A "Source cues" count that only reflects successfully-parsed
    # Observations understates the real number of structurally-read
    # source events whenever one was skipped as a recoverable import
    # warning -- it must not silently pass off "Observations we kept"
    # as "source cues".
    observations = {"o1": _observation("o1", "a"), "o2": _observation("o2", "b")}
    cues = [_cue("c1", "merged", observation_ids=("o1", "o2"))]
    warnings = [ImportWarning(source_index=2, reason="Observation.end_time must be after start_time")]
    workspace = PathBWorkspace(
        cues, observations, tmp_path / "input.srt", import_warnings=warnings
    )

    profile_text = workspace.ingestion_profile_label.text()
    assert "3" in profile_text  # 2 kept observations + 1 skipped event = 3 real source events


def test_path_b_uses_its_own_frozen_filter_baseline(qapp_guard, tmp_path):
    cues = [_cue("c1", "clean import")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")

    labels = [workspace.qa.filter_combo.itemText(i) for i in range(workspace.qa.filter_combo.count())]

    assert labels == ["All Reconstructed", "Review Needed", "Preserved"]


def test_preserved_filter_excludes_a_confidently_resolved_rolling_cue(qapp_guard, tmp_path):
    # A confidently-resolved rolling_growth Cue has NO Review Priority
    # flag (M8's whole point), so it must never leak into "Preserved"
    # just because priority.level == "None" -- Preserved is judged from
    # real PathBDiagnostics, not inferred from the review-priority score.
    from glyphcue.application.reconstruction import PathBDiagnostics

    cues = [_cue("c1", "rolling"), _cue("c2", "clean")]
    diagnostics_by_cue_id = {
        "c1": PathBDiagnostics(
            cue_id="c1", source_order_issue=False, rolling_growth=True,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=False, segmentation_ambiguous=False,
        ),
        "c2": PathBDiagnostics(
            cue_id="c2", source_order_issue=False, rolling_growth=False,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=False, segmentation_ambiguous=False,
        ),
    }
    workspace = PathBWorkspace(
        cues, {}, tmp_path / "input.srt", diagnostics_by_cue_id=diagnostics_by_cue_id
    )

    workspace.qa.filter_combo.setCurrentText("Preserved")

    shown_ids = {workspace.qa.cue_id_for_row(row) for row in range(workspace.qa.queue.count())}
    assert shown_ids == {"c2"}


def test_preserved_filter_includes_a_real_clean_cue_with_all_false_diagnostics(qapp_guard, tmp_path):
    from glyphcue.application.reconstruction import PathBDiagnostics

    cues = [_cue("c1", "clean")]
    diagnostics_by_cue_id = {
        "c1": PathBDiagnostics(
            cue_id="c1", source_order_issue=False, rolling_growth=False,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=False, segmentation_ambiguous=False,
        ),
    }
    workspace = PathBWorkspace(
        cues, {}, tmp_path / "input.srt", diagnostics_by_cue_id=diagnostics_by_cue_id
    )

    workspace.qa.filter_combo.setCurrentText("Preserved")

    shown_ids = {workspace.qa.cue_id_for_row(row) for row in range(workspace.qa.queue.count())}
    assert shown_ids == {"c1"}


def test_preserved_filter_excludes_a_cue_with_no_diagnostics_at_all(qapp_guard, tmp_path):
    # A Split/Merge-produced Cue (or any Cue with no diagnostics record)
    # must not pass as Preserved merely for lacking a Review Priority
    # signal -- Preserved requires a real diagnostics record confirming
    # nothing needed fixing, not the absence of a flag.
    cues = [_cue("c1", "no diagnostics recorded")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")

    workspace.qa.filter_combo.setCurrentText("Preserved")

    assert workspace.qa.queue.count() == 0


def test_approve_updates_review_state_and_commits_edited_text(qapp_guard, tmp_path):
    cues = [_cue("c1", "original")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")
    workspace.queue.setCurrentRow(0)

    workspace.qa.language_layers_panel.cards[0].text_edit.setPlainText("corrected")
    workspace.qa.approve_button.click()

    approved = workspace.cues[0]
    assert approved.review_state is ReviewState.APPROVED
    assert approved.language_layers[0].text == "corrected"


def test_export_button_click_writes_a_new_file_and_preserves_no_source_reference(qapp_guard, tmp_path):
    cues = [_cue("c1", "final text")]
    source = tmp_path / "input.srt"
    workspace = PathBWorkspace(cues, {}, source)
    workspace.queue.setCurrentRow(0)

    workspace.export_controls.export_button.click()

    destination = tmp_path / "input.reconstructed.srt"
    assert destination.exists()
    assert "final text" in destination.read_text(encoding="utf-8")


def test_the_same_srt_source_can_also_export_vtt_via_the_format_picker(qapp_guard, tmp_path):
    # Closes the M9 correctness gap: production Path B's export must
    # not merely reuse the input suffix -- the same .srt source must be
    # able to produce a .vtt output, and vice versa.
    cues = [_cue("c1", "final text")]
    source = tmp_path / "input.srt"
    workspace = PathBWorkspace(cues, {}, source)
    workspace.queue.setCurrentRow(0)

    workspace.export_controls.format_combo.setCurrentText("VTT")
    workspace.export_controls.export_button.click()

    destination = tmp_path / "input.reconstructed.vtt"
    assert destination.exists()
    assert "final text" in destination.read_text(encoding="utf-8")


def test_a_vtt_source_can_export_srt_via_the_format_picker(qapp_guard, tmp_path):
    cues = [_cue("c1", "final text")]
    source = tmp_path / "input.vtt"
    workspace = PathBWorkspace(cues, {}, source)
    workspace.queue.setCurrentRow(0)

    workspace.export_controls.format_combo.setCurrentText("SRT")
    workspace.export_controls.export_button.click()

    destination = tmp_path / "input.reconstructed.srt"
    assert destination.exists()
    assert "final text" in destination.read_text(encoding="utf-8")


def test_editing_text_then_exporting_immediately_without_approving_exports_the_edit(
    qapp_guard, tmp_path
):
    # A hand-edit sitting in the live QTextEdit must not be lost just
    # because the user exports immediately, without Approving or
    # navigating away first -- export must see the CURRENT editor
    # content, not whatever was last committed.
    cues = [_cue("c1", "Helo")]
    source = tmp_path / "input.srt"
    workspace = PathBWorkspace(cues, {}, source)
    workspace.queue.setCurrentRow(0)

    workspace.qa.language_layers_panel.cards[0].text_edit.setPlainText("Hello")
    workspace.export_controls.export_button.click()

    destination = tmp_path / "input.reconstructed.srt"
    exported = destination.read_text(encoding="utf-8")
    assert "Hello" in exported
    assert "Helo" not in exported
    # Export must not implicitly approve -- committing an edit for
    # export is not a review decision, but transitions to NEEDS_REVIEW to preserve the hand-edit.
    assert workspace.cues[0].review_state == ReviewState.NEEDS_REVIEW


def test_confidently_resolved_rolling_cue_shows_normalization_kind_but_no_review_flags(
    qapp_guard, tmp_path
):
    # A confidently-resolved rolling-growth Cue must still show "No
    # Review Flags" (M8's whole point: content GlyphCue could reliably
    # restore does not need a human to re-check it) -- but the reviewer
    # must still be able to SEE, in the existing shared shell, that it
    # actually went through rolling-growth consolidation, not just a
    # blank "nothing to report." No second QA UI is built for this --
    # it reuses the existing center-pane consolidation explanation.
    from glyphcue.application.reconstruction import PathBDiagnostics

    cues = [_cue("c1", "Hello world, how are you", observation_ids=("o1", "o2"))]
    diagnostics_by_cue_id = {
        "c1": PathBDiagnostics(
            cue_id="c1", source_order_issue=False, rolling_growth=True,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=False, segmentation_ambiguous=False,
        ),
    }
    workspace = PathBWorkspace(
        cues, {}, tmp_path / "input.srt",
        diagnostics_by_cue_id=diagnostics_by_cue_id,
    )

    workspace.queue.setCurrentRow(0)

    assert "None" in workspace.qa.priority_label.text()
    consolidation_text = workspace.consolidation_view.toPlainText().lower()
    assert "rolling growth" in consolidation_text


def test_discarding_a_cue_then_exporting_excludes_it_from_the_output_file(qapp_guard, tmp_path):
    cues = [_cue("c1", "keep this line"), _cue("c2", "discard this garbage reading")]
    source = tmp_path / "input.srt"
    workspace = PathBWorkspace(cues, {}, source)
    workspace.queue.setCurrentRow(1)
    assert workspace.active_cue.id == "c2"

    workspace.qa.discard_button.click()
    workspace.export_controls.export_button.click()

    destination = tmp_path / "input.reconstructed.srt"
    exported = destination.read_text(encoding="utf-8")
    assert "keep this line" in exported
    assert "discard this garbage reading" not in exported


def test_path_b_cues_show_no_review_flags_not_a_fabricated_priority(qapp_guard, tmp_path):
    # Path B's reconstruction has no OCR-confidence/disagreement
    # diagnostics to score with -- this must show up honestly as "no
    # signal", never a made-up score. (No diagnostics_by_cue_id passed
    # at all -- the pre-M8 backward-compatible default.)
    cues = [_cue("c1", "clean import")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")

    workspace.queue.setCurrentRow(0)

    assert "None" in workspace.qa.priority_label.text()


def test_path_b_real_m8_diagnostics_drive_a_real_review_priority(qapp_guard, tmp_path):
    from glyphcue.application.reconstruction import PathBDiagnostics

    confidently_resolved = _cue("c1", "rolling caption, confidently merged")
    ambiguous = _cue("c2", "kept separate, uncertain")
    diagnostics_by_cue_id = {
        "c1": PathBDiagnostics(
            cue_id="c1", source_order_issue=False, rolling_growth=True,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=False, segmentation_ambiguous=False,
        ),
        "c2": PathBDiagnostics(
            cue_id="c2", source_order_issue=False, rolling_growth=False,
            sliding_overlap=False, repetition_collapsed=False,
            timing_collision=False, segmentation_ambiguous=True,
        ),
    }
    workspace = PathBWorkspace(
        [confidently_resolved, ambiguous], {}, tmp_path / "input.srt",
        diagnostics_by_cue_id=diagnostics_by_cue_id,
    )

    row_of_c1 = next(row for row in range(workspace.queue.count()) if workspace.qa.cue_id_for_row(row) == "c1")
    workspace.queue.setCurrentRow(row_of_c1)
    assert "None" in workspace.qa.priority_label.text()

    row_of_c2 = next(row for row in range(workspace.queue.count()) if workspace.qa.cue_id_for_row(row) == "c2")
    workspace.queue.setCurrentRow(row_of_c2)
    assert "None" not in workspace.qa.priority_label.text()
    assert "segmentation" in workspace.qa.diagnostics_view.toPlainText().lower()


def test_export_readable_transcript_via_format_picker(qapp_guard, tmp_path):
    cues = [_cue("c1", "final text")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")
    workspace.queue.setCurrentRow(0)

    workspace.export_controls.format_combo.setCurrentText("Readable Transcript")
    workspace.export_controls.export_button.click()

    destination = tmp_path / "input.transcript.txt"
    assert destination.exists()
    assert "final text" in destination.read_text(encoding="utf-8")


def test_export_ai_ready_transcript_via_format_picker(qapp_guard, tmp_path):
    cues = [_cue("c1", "final text")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")
    workspace.queue.setCurrentRow(0)

    workspace.export_controls.format_combo.setCurrentText("AI-ready Transcript")
    workspace.export_controls.export_button.click()

    destination = tmp_path / "input.transcript.ai.md"
    assert destination.exists()
    assert "final text" in destination.read_text(encoding="utf-8")


def test_workspace_with_no_import_warnings_shows_no_warning_notice(qapp_guard, tmp_path):
    cues = [_cue("c1", "clean import")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")

    assert workspace.import_warnings_label.text() == ""


def test_workspace_surfaces_import_warnings_from_a_recoverable_skipped_event(qapp_guard, tmp_path):
    cues = [_cue("c1", "clean import")]
    warnings = [ImportWarning(source_index=3, reason="Observation.end_time must be after start_time")]
    workspace = PathBWorkspace(
        cues, {}, tmp_path / "input.srt", import_warnings=warnings
    )

    text = workspace.import_warnings_label.text()
    assert "1" in text
    assert "3" in text
    assert "end_time" in text


def test_open_video_button_is_disabled_without_a_switch_callback(qapp_guard, tmp_path):
    cues = [_cue("c1", "clean import")]
    workspace = PathBWorkspace(cues, {}, tmp_path / "input.srt")

    assert workspace.open_video_button.isEnabled() is False


def test_switch_to_video_invokes_the_injected_callback_directly(qapp_guard, tmp_path):
    # Path switching from an already-open Path B workbench must reach
    # Path A directly, not require the app to be restarted -- verified
    # here at the seam PathBWorkspace actually calls, without needing a
    # real QFileDialog.
    called_with: list = []
    cues = [_cue("c1", "clean import")]
    workspace = PathBWorkspace(
        cues, {}, tmp_path / "input.srt", on_open_video=called_with.append
    )

    assert workspace.open_video_button.isEnabled() is True
    workspace.switch_to_video(tmp_path / "clip.mp4")

    assert called_with == [tmp_path / "clip.mp4"]
