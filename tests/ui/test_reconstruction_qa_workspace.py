from PySide6.QtCore import Qt
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
