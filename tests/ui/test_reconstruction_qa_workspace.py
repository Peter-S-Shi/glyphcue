from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from glyphcue.application.review_priority import ReviewPriority, ReviewPriorityComponent
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace

_PROVENANCE = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="x")


def _cue(id_, start, end, texts=None, obs_ids=()):
    texts = texts or {"en": "Hello"}
    layers = tuple(
        LanguageLayer(language=language, text=text, observation_ids=obs_ids)
        for language, text in texts.items()
    )
    return Cue(id=id_, start_time=start, end_time=end, language_layers=layers)


def _obs(id_, text, start):
    return Observation(id=id_, text=text, start_time=start, end_time=start + 0.001, provenance=_PROVENANCE)


def _priority(cue_id, score, level="Low"):
    return ReviewPriority(
        cue_id=cue_id,
        score=score,
        level=level,
        components=(ReviewPriorityComponent(name="x", contribution=score, explanation="because x"),),
    )


def _none_priority(cue_id):
    return ReviewPriority(cue_id=cue_id, score=0.0, level="None", components=())


def test_queue_is_ordered_by_review_priority_descending(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0), _cue("c3", 2.0, 3.0)]
    priorities = {"c1": _none_priority("c1"), "c2": _priority("c2", 0.9, "High"), "c3": _priority("c3", 0.4, "Medium")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    ordered_ids = [workspace.cue_id_for_row(row) for row in range(workspace.queue.count())]

    assert ordered_ids == ["c2", "c3", "c1"]


def test_search_filters_the_queue_by_active_language_layer_text(qapp_guard):
    cues = [
        _cue("c1", 0.0, 1.0, texts={"en": "the quick fox"}),
        _cue("c2", 1.0, 2.0, texts={"en": "a lazy dog"}),
    ]
    priorities = {"c1": _none_priority("c1"), "c2": _none_priority("c2")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.search_edit.setText("lazy")

    assert workspace.queue.count() == 1
    assert workspace.cue_id_for_row(0) == "c2"


def test_clearing_the_search_restores_the_full_queue(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "fox"}), _cue("c2", 1.0, 2.0, texts={"en": "dog"})]
    priorities = {"c1": _none_priority("c1"), "c2": _none_priority("c2")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.search_edit.setText("fox")

    workspace.search_edit.setText("")

    assert workspace.queue.count() == 2


def test_default_filter_labels_are_the_path_a_frozen_baseline(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    labels = [workspace.filter_combo.itemText(i) for i in range(workspace.filter_combo.count())]

    assert labels == ["All", "Review Needed", "Clean / Approved"]


def test_filter_labels_are_customizable_for_path_b(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(
        cues, {}, priorities, QWidget(),
        filter_labels=("All Reconstructed", "Review Needed", "Preserved"),
    )

    labels = [workspace.filter_combo.itemText(i) for i in range(workspace.filter_combo.count())]

    assert labels == ["All Reconstructed", "Review Needed", "Preserved"]


def test_review_needed_filter_shows_only_cues_with_a_real_review_flag(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _none_priority("c1"), "c2": _priority("c2", 0.9, "High")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.filter_combo.setCurrentText("Review Needed")

    assert workspace.queue.count() == 1
    assert workspace.cue_id_for_row(0) == "c2"


def test_clean_or_approved_filter_shows_cues_with_no_flag_or_that_are_approved(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0), _cue("c3", 2.0, 3.0)]
    priorities = {
        "c1": _none_priority("c1"),  # clean, no flag
        "c2": _priority("c2", 0.9, "High"),  # flagged, not approved
        "c3": _priority("c3", 0.9, "High"),  # flagged BUT approved
    }
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.queue.setCurrentRow(next(
        row for row in range(workspace.queue.count()) if workspace.cue_id_for_row(row) == "c3"
    ))
    workspace.approve_and_advance()

    workspace.filter_combo.setCurrentText("Clean / Approved")

    shown_ids = {workspace.cue_id_for_row(row) for row in range(workspace.queue.count())}
    assert shown_ids == {"c1", "c3"}


def test_approved_flagged_cue_leaves_review_needed(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _none_priority("c1"), "c2": _priority("c2", 0.9, "High")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.queue.setCurrentRow(next(
        row for row in range(workspace.queue.count()) if workspace.cue_id_for_row(row) == "c2"
    ))
    workspace.approve_and_advance()

    workspace.filter_combo.setCurrentText("Review Needed")

    assert workspace.queue.count() == 0


def test_needs_review_state_from_split_appears_in_review_needed_even_with_no_priority_signal(
    qapp_guard,
):
    # A clean parent Cue with NO Review Priority flag is Split. Both
    # halves inherit the parent's priority ("None" here) but
    # cue_review_actions.split_cue always marks them NEEDS_REVIEW -- a
    # machine split is never itself a correct reconstruction, so the
    # human review-state signal (not the heuristic priority score) must
    # be what puts them in Review Needed.
    cues = [_cue("c1", 0.0, 2.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.split_time_spin.setValue(1.0)
    workspace.split_active_cue()

    workspace.filter_combo.setCurrentText("Review Needed")

    assert workspace.queue.count() == 2


def test_rejected_cue_with_no_priority_signal_is_not_clean_or_approved(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _none_priority("c1"), "c2": _none_priority("c2")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.queue.setCurrentRow(next(
        row for row in range(workspace.queue.count()) if workspace.cue_id_for_row(row) == "c2"
    ))
    workspace.discard_active_cue()

    workspace.filter_combo.setCurrentText("Clean / Approved")

    shown_ids = {workspace.cue_id_for_row(row) for row in range(workspace.queue.count())}
    assert shown_ids == {"c1"}


def test_third_filter_predicate_overrides_the_default_clean_or_approved_semantics(qapp_guard):
    # A path-specific caller (Path B) can override the third filter
    # bucket's meaning entirely -- e.g. "Preserved" must be judged from
    # real PathBDiagnostics, never inferred from Review Priority.
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _none_priority("c1"), "c2": _none_priority("c2")}
    workspace = ReconstructionQaWorkspace(
        cues, {}, priorities, QWidget(),
        filter_labels=("All Reconstructed", "Review Needed", "Preserved"),
        third_filter_predicate=lambda cue: cue.id == "c2",
    )

    workspace.filter_combo.setCurrentText("Preserved")

    shown_ids = {workspace.cue_id_for_row(row) for row in range(workspace.queue.count())}
    assert shown_ids == {"c2"}


def test_active_cue_starts_as_the_top_of_the_queue(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _none_priority("c1"), "c2": _priority("c2", 0.9, "High")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    assert workspace.active_cue.id == "c2"


def test_approve_and_advance_marks_approved_and_moves_to_the_next_queue_row(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _priority("c1", 0.9, "High"), "c2": _priority("c2", 0.5, "Medium")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.approve_and_advance()

    approved = next(cue for cue in workspace.cues if cue.id == "c1")
    assert approved.review_state == ReviewState.APPROVED
    assert workspace.active_cue.id == "c2"


def test_ctrl_enter_shortcut_triggers_approve_and_advance(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _priority("c1", 0.9), "c2": _priority("c2", 0.5)}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.approve_shortcut.activated.emit()

    approved = next(cue for cue in workspace.cues if cue.id == "c1")
    assert approved.review_state == ReviewState.APPROVED


def test_discard_marks_rejected(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.discard_active_cue()

    assert workspace.cues[0].review_state == ReviewState.REJECTED


def test_editing_language_layer_text_and_approving_applies_the_correction(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Helo"})]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Hello")
    workspace.approve_and_advance()

    assert workspace.cues[0].language_layers[0].text == "Hello"
    assert workspace.cues[0].review_state == ReviewState.APPROVED


def test_timing_nudge_buttons_adjust_the_active_cue(qapp_guard):
    cues = [_cue("c1", 1.0, 2.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.nudge_start_earlier_button.click()

    assert workspace.cues[0].start_time < 1.0


def test_split_creates_two_cues_and_advances_past_the_original(qapp_guard):
    cues = [_cue("c1", 0.0, 4.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.split_time_spin.setValue(2.0)

    workspace.split_active_cue()

    assert len(workspace.cues) == 2
    assert workspace.cues[0].review_state == ReviewState.NEEDS_REVIEW


def test_merge_with_next_merges_the_temporally_next_cue_even_when_priority_order_differs(qapp_guard):
    # 3 Cues on the timeline as c1 (0-2s) -> c2 (2-4s) -> c3 (4-6s), but
    # priority order is deliberately c1 > c3 > c2, so c1's QUEUE-next
    # row is c3 (NOT its real temporal next, c2). The OLD implementation
    # used "next row in the priority-sorted queue" for Merge with Next,
    # which would wrongly merge c1 with c3 here. Merge with Next must
    # always merge c1 with c2 (the real next Cue on the timeline),
    # regardless of priority order.
    cues = [
        _cue("c1", 0.0, 2.0, texts={"en": "Hello"}),
        _cue("c2", 2.0, 4.0, texts={"en": "world"}),
        _cue("c3", 4.0, 6.0, texts={"en": "unrelated"}),
    ]
    priorities = {
        "c1": _priority("c1", 0.9, "High"),
        "c3": _priority("c3", 0.5, "Medium"),
        "c2": _none_priority("c2"),
    }
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    # Queue order is priority-descending: c1, c3, c2.
    row_of_c1 = next(row for row in range(workspace.queue.count()) if workspace.cue_id_for_row(row) == "c1")
    workspace.queue.setCurrentRow(row_of_c1)
    assert workspace.active_cue.id == "c1"

    workspace.merge_active_cue_with_next()

    ids = {cue.id for cue in workspace.cues}
    assert "c3" in ids  # c3 (unrelated) untouched
    merged = next(cue for cue in workspace.cues if cue.id not in {"c1", "c2", "c3"})
    assert "Hello" in merged.language_layers[0].text
    assert "world" in merged.language_layers[0].text
    assert "unrelated" not in merged.language_layers[0].text


def test_merge_with_next_combines_active_cue_with_the_following_queue_entry(qapp_guard):
    cues = [_cue("c1", 0.0, 2.0, texts={"en": "Hello"}), _cue("c2", 2.0, 4.0, texts={"en": "world"})]
    priorities = {"c1": _priority("c1", 0.9, "High"), "c2": _none_priority("c2")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.merge_active_cue_with_next()

    assert len(workspace.cues) == 1
    assert "Hello" in workspace.cues[0].language_layers[0].text
    assert "world" in workspace.cues[0].language_layers[0].text


def test_previous_next_navigation_moves_the_active_row(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _priority("c1", 0.9), "c2": _priority("c2", 0.5)}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    assert workspace.active_cue.id == "c1"

    workspace.go_to_next()
    assert workspace.active_cue.id == "c2"

    workspace.go_to_previous()
    assert workspace.active_cue.id == "c1"


def test_replay_callback_receives_the_active_cue(qapp_guard):
    received = []
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(
        cues, {}, priorities, QWidget(), replay_callback=received.append
    )

    workspace.replay_shortcut.activated.emit()

    assert received == [workspace.active_cue]


def test_play_pause_callback_is_invoked_by_the_space_shortcut(qapp_guard):
    calls = []
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(
        cues, {}, priorities, QWidget(), play_pause_callback=lambda: calls.append(True)
    )

    workspace.play_pause_shortcut.activated.emit()

    assert calls == [True]


def test_evidence_view_defaults_to_curated_and_can_expand_to_full(qapp_guard):
    observations_by_id = {
        "o1": _obs("o1", "Hello", 0.0),
        "o2": _obs("o2", "Hallo", 0.5),
        "o3": _obs("o3", "Hello", 1.0),
        "o4": _obs("o4", "Hello", 1.5),
        "o5": _obs("o5", "Hello", 2.0),
    }
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Hello"}, obs_ids=tuple(observations_by_id))]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, observations_by_id, priorities, QWidget())

    curated_text = workspace.evidence_view.toPlainText()
    assert "Hallo" in curated_text  # disagreement always shown

    workspace.show_full_evidence_checkbox.setChecked(True)
    full_text = workspace.evidence_view.toPlainText()

    assert len(full_text) >= len(curated_text)
    for observation_id in observations_by_id:
        assert observations_by_id[observation_id].text in full_text


def test_editing_text_then_nudging_timing_retains_the_edit(qapp_guard):
    cues = [_cue("c1", 1.0, 2.0, texts={"en": "Helo"})]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Hello")
    workspace.nudge_start_earlier_button.click()

    assert workspace.cues[0].language_layers[0].text == "Hello"
    assert workspace.cues[0].start_time < 1.0


def test_editing_text_then_navigating_away_and_back_retains_the_edit(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Helo"}), _cue("c2", 1.0, 2.0, texts={"en": "world"})]
    priorities = {"c1": _priority("c1", 0.9), "c2": _priority("c2", 0.5)}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Hello")
    workspace.go_to_next()
    workspace.go_to_previous()

    assert workspace.cues[0].language_layers[0].text == "Hello"
    assert workspace.language_layers_panel.cards[0].current_text() == "Hello"


def test_editing_text_then_clicking_a_different_queue_row_retains_the_edit(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Helo"}), _cue("c2", 1.0, 2.0, texts={"en": "world"})]
    priorities = {"c1": _priority("c1", 0.9), "c2": _priority("c2", 0.5)}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Hello")
    workspace.queue.setCurrentRow(1)  # direct row click, not go_to_next/previous

    assert workspace.cues[0].language_layers[0].text == "Hello"


def test_editing_text_then_splitting_retains_the_edit_on_both_halves(qapp_guard):
    cues = [_cue("c1", 0.0, 4.0, texts={"en": "Helo world"})]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.split_time_spin.setValue(2.0)

    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Hello world")
    workspace.split_active_cue()

    assert len(workspace.cues) == 2
    assert workspace.cues[0].language_layers[0].text == "Hello world"
    assert workspace.cues[1].language_layers[0].text == "Hello world"


def test_editing_text_then_merging_with_next_retains_the_edit(qapp_guard):
    cues = [_cue("c1", 0.0, 2.0, texts={"en": "Helo"}), _cue("c2", 2.0, 4.0, texts={"en": "world"})]
    priorities = {"c1": _priority("c1", 0.9, "High"), "c2": _none_priority("c2")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Hello")
    workspace.merge_active_cue_with_next()

    assert "Hello" in workspace.cues[0].language_layers[0].text
    assert "Helo" not in workspace.cues[0].language_layers[0].text


def test_editing_text_then_discarding_retains_the_edit(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Helo"})]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Hello")
    workspace.discard_active_cue()

    assert workspace.cues[0].language_layers[0].text == "Hello"
    assert workspace.cues[0].review_state == ReviewState.REJECTED


def test_space_shortcut_does_not_fire_while_the_text_edit_has_real_keyboard_focus(qapp_guard):
    calls = []
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Hello"})]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(
        cues, {}, priorities, QWidget(), play_pause_callback=lambda: calls.append(True)
    )
    workspace.window.show()
    text_edit = workspace.language_layers_panel.cards[0].text_edit
    text_edit.setFocus()
    text_edit.selectAll()

    QTest.keyClick(text_edit, Qt.Key.Key_Space)

    assert calls == []
    assert " " in text_edit.toPlainText()
    workspace.window.hide()


def test_bracket_shortcuts_do_not_fire_while_the_text_edit_has_real_keyboard_focus(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _priority("c1", 0.9), "c2": _priority("c2", 0.5)}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.window.show()
    text_edit = workspace.language_layers_panel.cards[0].text_edit
    text_edit.setFocus()

    QTest.keyClick(text_edit, Qt.Key.Key_BracketRight)

    assert workspace.active_cue.id == "c1"  # navigation did not fire
    assert "]" in text_edit.toPlainText()
    workspace.window.hide()


def test_replay_shortcut_does_not_fire_while_the_text_edit_has_real_keyboard_focus(qapp_guard):
    received = []
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Hello"})]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(
        cues, {}, priorities, QWidget(), replay_callback=received.append
    )
    workspace.window.show()
    text_edit = workspace.language_layers_panel.cards[0].text_edit
    text_edit.setFocus()

    QTest.keyClick(text_edit, Qt.Key.Key_R)

    assert received == []
    assert "r" in text_edit.toPlainText().lower()
    workspace.window.hide()


def test_ctrl_enter_still_approves_while_the_text_edit_has_real_keyboard_focus(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Helo"}), _cue("c2", 1.0, 2.0)]
    priorities = {"c1": _priority("c1", 0.9), "c2": _priority("c2", 0.5)}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())
    workspace.window.show()
    text_edit = workspace.language_layers_panel.cards[0].text_edit
    text_edit.setFocus()
    text_edit.selectAll()
    text_edit.insertPlainText("Hello")

    QTest.keyClick(text_edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    approved = next(cue for cue in workspace.cues if cue.id == "c1")
    assert approved.review_state == ReviewState.APPROVED
    assert approved.language_layers[0].text == "Hello"
    workspace.window.hide()


def test_replay_capability_is_disabled_when_no_replay_callback_is_wired(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    assert workspace.replay_button.isEnabled() is False
    assert workspace.replay_shortcut.isEnabled() is False


def test_replay_capability_is_enabled_when_a_replay_callback_is_wired(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(
        cues, {}, priorities, QWidget(), replay_callback=lambda cue: None
    )

    assert workspace.replay_button.isEnabled() is True
    assert workspace.replay_shortcut.isEnabled() is True


def test_action_hierarchy_gives_approve_dominant_styling_and_discard_danger_styling(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    approve_style = workspace.approve_button.styleSheet()
    discard_style = workspace.discard_button.styleSheet()
    split_style = workspace.split_button.styleSheet()
    merge_style = workspace.merge_next_button.styleSheet()

    # Approve is the one dominant action (DESIGN.md section 23): its
    # own distinct styling, not shared with any secondary action.
    assert approve_style
    assert approve_style != discard_style
    assert approve_style != split_style
    assert approve_style != merge_style
    # Discard is danger-colored but must not share Approve's prominence.
    assert discard_style != approve_style
    # Split/Merge are secondary actions and look alike, not like Approve.
    assert split_style == merge_style
    assert split_style != approve_style


def test_multilingual_curated_evidence_never_flags_a_correct_layer_as_disagreeing_with_another_language(
    qapp_guard,
):
    # Regression: curated evidence must compare each language layer
    # against its OWN winning text, not the Cue's primary/first layer's
    # text -- a fully-correct zh layer naturally differs from the en
    # layer's text, and that is not evidence of disagreement.
    observations_by_id = {
        "en1": _obs("en1", "Hello", 0.0),
        "en2": _obs("en2", "Hallo", 0.3),  # a real en disagreement
        "en3": _obs("en3", "Hello", 0.6),
        "zh1": _obs("zh1", "你好", 0.0),
        "zh2": _obs("zh2", "你好", 0.2),
        "zh3": _obs("zh3", "你好", 0.4),
        "zh4": _obs("zh4", "你好", 0.6),
        "zh5": _obs("zh5", "你好", 0.8),
    }
    cue = Cue(
        id="c1",
        start_time=0.0,
        end_time=1.0,
        language_layers=(
            LanguageLayer(language="en", text="Hello", observation_ids=("en1", "en2", "en3")),
            LanguageLayer(
                language="zh", text="你好", observation_ids=("zh1", "zh2", "zh3", "zh4", "zh5")
            ),
        ),
    )
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace([cue], observations_by_id, priorities, QWidget())

    curated_text = workspace.evidence_view.toPlainText()

    assert "Hallo" in curated_text  # the real en disagreement is still shown
    # All 5 zh observations are textually identical to zh's own winning
    # text -- if curated selection wrongly compared them against the
    # Cue's primary (en) text instead of zh's own, every one of the 5
    # would look like a "disagreement" and get shown. Comparing each
    # layer against its own text means only in-point/representative/
    # out-point (3, per `select_curated_evidence`) are shown here.
    zh_line_count = sum(1 for line in curated_text.splitlines() if "你好" in line)
    assert zh_line_count == 3


def test_set_cues_and_priorities_populates_an_initially_empty_workspace(qapp_guard):
    # Path A starts a review session with nothing to review yet (no OCR
    # run has completed) and populates the SAME workspace once one
    # finishes -- the window is not rebuilt from scratch.
    workspace = ReconstructionQaWorkspace([], {}, {}, QWidget())
    assert workspace.active_cue is None

    cues = [_cue("c1", 0.0, 1.0)]
    observations_by_id = {"o1": _obs("o1", "Hello", 0.0)}
    priorities = {"c1": _priority("c1", 0.7, "Medium")}

    workspace.set_cues_and_priorities(cues, observations_by_id, priorities)

    assert workspace.active_cue is not None
    assert workspace.active_cue.id == "c1"
    assert workspace.queue.count() == 1


def test_queue_items_show_review_state_badges_and_review_priority(qapp_guard):
    cues = [
        _cue("c1", 0.0, 1.0, texts={"en": "First line"}),
        _cue("c2", 1.0, 2.0, texts={"en": "Second line"}),
        _cue("c3", 2.0, 3.0, texts={"en": "Third line"}),
    ]
    priorities = {
        "c1": _priority("c1", 0.9, "High"),
        "c2": _priority("c2", 0.5, "Medium"),
        "c3": _none_priority("c3"),
    }
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    # Initial pending state
    assert "[High]" in workspace.queue.item(0).text()
    assert "[○ Pending]" in workspace.queue.item(0).text()
    assert "First line" in workspace.queue.item(0).text()

    # Approve c1
    workspace.approve_and_advance()
    assert "[High]" in workspace.queue.item(0).text()
    assert "[✓ Approved]" in workspace.queue.item(0).text()

    # Discard c2
    workspace.discard_active_cue()
    assert "[Medium]" in workspace.queue.item(1).text()
    assert "[✕ Discarded]" in workspace.queue.item(1).text()


def test_review_state_and_review_priority_are_distinct_labels_in_right_pane(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0, texts={"en": "Hello"})]
    priorities = {"c1": _priority("c1", 0.85, "High")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    assert workspace.review_state_label.text() == "Review State: ○ Pending"
    assert workspace.priority_label.text() == "Review Priority: High (0.85)"

    workspace.approve_and_advance()
    assert workspace.review_state_label.text() == "Review State: ✓ Approved"


def test_editing_text_and_approving_immediately_refreshes_queue_label_and_state(qapp_guard):
    cues = [
        _cue("c1", 0.0, 1.0, texts={"en": "Original Text"}),
        _cue("c2", 1.0, 2.0, texts={"en": "Second Cue"}),
    ]
    priorities = {"c1": _priority("c1", 0.9, "High"), "c2": _none_priority("c2")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    # Edit text in right pane
    workspace.language_layers_panel.cards[0].text_edit.setPlainText("Corrected Hand-Edited Text")
    workspace.approve_and_advance()

    # The first item in queue must immediately reflect new text and Approved state
    c1_item_text = workspace.queue.item(0).text()
    assert "[✓ Approved]" in c1_item_text
    assert "Corrected Hand-Edited Text" in c1_item_text


def test_raw_ocr_evidence_header_and_explanatory_note_are_present(qapp_guard):
    cues = [_cue("c1", 0.0, 1.0)]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    assert "Raw OCR Evidence" in workspace.evidence_header_label.text()
    assert "Machine Observations" in workspace.evidence_header_label.text()
    assert len(workspace.evidence_note_label.text()) > 0


def test_timing_nudge_exact_point_one_second_steps_and_refreshes_ui(qapp_guard):
    cues = [_cue("c1", 1.0, 2.0, texts={"en": "Test Cue"})]
    priorities = {"c1": _none_priority("c1")}
    workspace = ReconstructionQaWorkspace(cues, {}, priorities, QWidget())

    # 1. Start earlier by 0.1s -> 0.9s
    workspace.nudge_start_earlier_button.click()
    assert workspace.cues[0].start_time == 0.9
    assert workspace.cues[0].end_time == 2.0
    assert "0.900s" in workspace.cue_identity_label.text()
    assert "⚠ Needs Review" in workspace.review_state_label.text()
    assert "[⚠ Needs Review]" in workspace.queue.item(0).text()

    # 2. Start later by 0.1s -> 1.0s
    workspace.nudge_start_later_button.click()
    assert workspace.cues[0].start_time == 1.0
    assert "1.000s" in workspace.cue_identity_label.text()

    # 3. End later by 0.1s -> 2.1s
    workspace.nudge_end_later_button.click()
    assert workspace.cues[0].end_time == 2.1
    assert "2.100s" in workspace.cue_identity_label.text()

    # 4. End earlier by 0.1s -> 2.0s
    workspace.nudge_end_earlier_button.click()
    assert workspace.cues[0].end_time == 2.0
    assert "2.000s" in workspace.cue_identity_label.text()

