from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from glyphcue.application.cue_review_actions import (
    approve_cue,
    discard_cue,
    edit_cue_language_text,
    merge_cues,
    nudge_cue_timing,
    split_cue,
)
from glyphcue.application.curated_evidence import select_curated_evidence
from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation
from glyphcue.ui.design_tokens import Color, Spacing
from glyphcue.ui.language_layer_presentation import LanguageLayersPanel, queue_label_for_cue
from glyphcue.ui.main_window import MainWindow

_TIMING_NUDGE_STEP_SECONDS = 0.1
_QUEUE_ITEM_ROLE_CUE_ID = "cue_id"

_APPROVE_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {Color.SUCCESS};
        color: {Color.VOID};
        font-weight: 700;
        padding: 8px 20px;
        border-radius: 6px;
        border: none;
    }}
"""
"""DESIGN.md section 23: Approve is the QA pane's one dominant action --
its own distinct, high-prominence styling, never shared with any
secondary action."""

_SECONDARY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {Color.SURFACE_2};
        color: {Color.TEXT_PRIMARY};
        padding: 6px 14px;
        border-radius: 6px;
        border: 1px solid {Color.BORDER_MEDIUM};
    }}
"""
"""Split/Merge: secondary actions, visually equal to each other and
deliberately less prominent than Approve (DESIGN.md section 23)."""

_DISCARD_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {Color.SURFACE_2};
        color: {Color.DANGER};
        font-weight: 600;
        padding: 6px 14px;
        border-radius: 6px;
        border: 1px solid {Color.DANGER};
    }}
"""
"""Discard: danger-colored so its consequence is legible, but NOT given
Approve's size/weight/fill -- DESIGN.md section 23 requires Discard to
never share visual prominence with Approve."""


def _is_approve_key_event(event: QEvent) -> bool:
    return event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and bool(
        event.modifiers() & Qt.KeyboardModifier.ControlModifier
    )


class _CtrlEnterApproveFilter(QObject):
    """Guarantees Ctrl+Enter still approves while a language-layer
    `QTextEdit` has real keyboard focus (DESIGN.md section 24),
    independent of two separate Qt behaviors that can otherwise swallow
    it:

    1. A focused `QTextEdit` can claim plain Return for itself (newline
       insertion) via Qt's own ShortcutOverride negotiation, which would
       otherwise prevent the window-level Ctrl+Enter `QShortcut` from
       ever firing.
    2. If more than one window in the process happens to have an active
       Ctrl+Return `QShortcut` at once (e.g. a stray window left open by
       an unrelated test), Qt's global shortcut map treats the key as
       AMBIGUOUS and fires neither -- silently, with no exception.

    This filter is installed directly on each editable text edit and
    handles both: it accepts `QEvent.ShortcutOverride` for Ctrl+Enter so
    the key is claimed locally before it can ever reach the (possibly
    ambiguous) global shortcut map, then handles the resulting
    `QEvent.KeyPress` itself -- invoking `callback` (Approve and
    advance) and consuming the event so no newline is inserted."""

    def __init__(self, callback: Callable[[], None], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.ShortcutOverride and _is_approve_key_event(event):
            event.accept()
            return True
        if event.type() == QEvent.Type.KeyPress and _is_approve_key_event(event):
            self._callback()
            return True
        return False


def _priority_label(priority: ReviewPriority) -> str:
    # DESIGN.md section 21's own accepted vocabulary: level word plus
    # the raw heuristic score -- never phrased as a probability/percent.
    return f"Review Priority: {priority.level} ({priority.score:.2f})"


def _diagnostics_text(priority: ReviewPriority) -> str:
    if not priority.components:
        return "No Review Flags"
    return "\n".join(f"- {component.explanation}" for component in priority.components)


class ReconstructionQaWorkspace:
    """The shared production human-in-the-loop review seam (ROADMAP M7):
    one Reconstruction QA right pane plus a priority-ordered left queue,
    reused identically by Path A and Path B so both paths follow the
    same grammar (DESIGN.md section 6's frozen three-pane shell) --
    only the CENTER evidence widget differs per path (video for Path A,
    timed-text evidence for Path B), passed in by the caller.

    Operates on an in-memory `list[Cue]`, mirroring the existing
    `PathBWorkspace` pattern rather than adding new Cue persistence:
    neither path currently round-trips QA edits through `CueRepository`
    (which is insert-only), and ROADMAP M7 explicitly asks to reuse
    existing invariants rather than add speculative schema/migration.
    QA state survives for the review session and flows to Export; it is
    not yet durable across app restarts (a real, documented scope
    boundary, not a silent gap).

    `priorities_by_cue_id` is precomputed by the caller (via
    `review_signals_from_consensus_diagnostics` /
    `review_signals_from_multilingual_diagnostics` +
    `compute_review_priority`, whichever matches the path's own
    reconstruction diagnostics) -- this workspace never computes Review
    Priority itself, keeping it decoupled from M5/M6's diagnostics
    types.
    """

    def __init__(
        self,
        cues: list[Cue],
        observations_by_id: dict[str, Observation],
        priorities_by_cue_id: dict[str, ReviewPriority],
        center_widget: QWidget,
        *,
        play_pause_callback: Callable[[], None] | None = None,
        replay_callback: Callable[[Cue], None] | None = None,
        on_active_cue_changed: Callable[[Cue | None], None] | None = None,
    ) -> None:
        self._cues = list(cues)
        self._observations_by_id = observations_by_id
        self._priorities_by_cue_id = dict(priorities_by_cue_id)
        self._play_pause_callback = play_pause_callback
        self._replay_callback = replay_callback
        self._on_active_cue_changed = on_active_cue_changed
        self._displayed_cue_id: str | None = None
        self._approve_filter = _CtrlEnterApproveFilter(lambda: self.approve_and_advance())

        self.queue = QListWidget()
        self.cue_identity_label = QLabel("")
        self.priority_label = QLabel("")
        self.diagnostics_view = QTextEdit()
        self.diagnostics_view.setReadOnly(True)
        self.language_layers_panel = LanguageLayersPanel(editable=True)

        self.nudge_start_earlier_button = QPushButton("Start −0.1s")
        self.nudge_start_later_button = QPushButton("Start +0.1s")
        self.nudge_end_earlier_button = QPushButton("End −0.1s")
        self.nudge_end_later_button = QPushButton("End +0.1s")

        self.split_time_spin = QDoubleSpinBox()
        self.split_time_spin.setDecimals(3)
        self.split_time_spin.setRange(0.0, 24.0 * 3600.0)
        self.split_button = QPushButton("Split")
        self.merge_next_button = QPushButton("Merge with Next")
        self.discard_button = QPushButton("Discard")
        self.approve_button = QPushButton("Approve")
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.replay_button = QPushButton("Replay")

        # DESIGN.md section 23's minimal QA action hierarchy: Approve is
        # the one dominant action; Split/Merge are secondary and look
        # alike; Discard is danger-colored but never as prominent as
        # Approve.
        self.approve_button.setStyleSheet(_APPROVE_BUTTON_STYLE)
        self.split_button.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        self.merge_next_button.setStyleSheet(_SECONDARY_BUTTON_STYLE)
        self.discard_button.setStyleSheet(_DISCARD_BUTTON_STYLE)

        # A Replay affordance with nothing to replay (no playback
        # controller wired -- e.g. Path B has no video) must be
        # disabled, not a fake control that silently does nothing.
        replay_wired = replay_callback is not None
        self.replay_button.setEnabled(replay_wired)

        self.show_full_evidence_checkbox = QCheckBox("Show full evidence")
        self.evidence_view = QTextEdit()
        self.evidence_view.setReadOnly(True)

        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        left_layout.addWidget(self.queue)

        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        right_layout.addWidget(self.cue_identity_label)
        right_layout.addWidget(self.priority_label)
        right_layout.addWidget(self.diagnostics_view)
        right_layout.addWidget(self.language_layers_panel)
        timing_row = QHBoxLayout()
        for button in (
            self.nudge_start_earlier_button,
            self.nudge_start_later_button,
            self.nudge_end_earlier_button,
            self.nudge_end_later_button,
        ):
            timing_row.addWidget(button)
        right_layout.addLayout(timing_row)
        split_merge_row = QHBoxLayout()
        split_merge_row.addWidget(self.split_time_spin)
        split_merge_row.addWidget(self.split_button)
        split_merge_row.addWidget(self.merge_next_button)
        right_layout.addLayout(split_merge_row)
        action_row = QHBoxLayout()
        action_row.addWidget(self.previous_button)
        action_row.addWidget(self.replay_button)
        action_row.addWidget(self.discard_button)
        action_row.addWidget(self.approve_button)
        action_row.addWidget(self.next_button)
        right_layout.addLayout(action_row)
        right_layout.addWidget(self.show_full_evidence_checkbox)
        right_layout.addWidget(self.evidence_view)
        self._right_layout = right_layout

        self.window = MainWindow(left_pane=left_pane, center_pane=center_widget, right_pane=right_pane)

        self.queue.currentRowChanged.connect(self._on_row_changed)
        self.nudge_start_earlier_button.clicked.connect(
            lambda: self._nudge_active(start_delta=-_TIMING_NUDGE_STEP_SECONDS)
        )
        self.nudge_start_later_button.clicked.connect(
            lambda: self._nudge_active(start_delta=_TIMING_NUDGE_STEP_SECONDS)
        )
        self.nudge_end_earlier_button.clicked.connect(
            lambda: self._nudge_active(end_delta=-_TIMING_NUDGE_STEP_SECONDS)
        )
        self.nudge_end_later_button.clicked.connect(
            lambda: self._nudge_active(end_delta=_TIMING_NUDGE_STEP_SECONDS)
        )
        self.split_button.clicked.connect(self.split_active_cue)
        self.merge_next_button.clicked.connect(self.merge_active_cue_with_next)
        self.discard_button.clicked.connect(self.discard_active_cue)
        self.approve_button.clicked.connect(self.approve_and_advance)
        self.previous_button.clicked.connect(self.go_to_previous)
        self.next_button.clicked.connect(self.go_to_next)
        self.replay_button.clicked.connect(self._on_replay_clicked)
        self.show_full_evidence_checkbox.toggled.connect(lambda _checked: self._refresh_active_pane())

        # DESIGN.md sections 10.2 / 24: Space stays Play/Pause and is
        # never overloaded for approval; Ctrl+Enter is the stable
        # approval shortcut across both paths.
        self.play_pause_shortcut = QShortcut(QKeySequence(" "), self.window)
        self.play_pause_shortcut.activated.connect(self._on_play_pause_shortcut)
        self.approve_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.window)
        self.approve_shortcut.activated.connect(self.approve_and_advance)
        self.replay_shortcut = QShortcut(QKeySequence("R"), self.window)
        self.replay_shortcut.activated.connect(self._on_replay_shortcut)
        self.replay_shortcut.setEnabled(replay_wired)
        self.next_shortcut = QShortcut(QKeySequence("]"), self.window)
        self.next_shortcut.activated.connect(self.go_to_next)
        self.previous_shortcut = QShortcut(QKeySequence("["), self.window)
        self.previous_shortcut.activated.connect(self.go_to_previous)

        # No cue_id to select yet -- defaults to the queue's own top row,
        # i.e. the highest Review Priority, not simply the first Cue in
        # whatever order the caller happened to pass them in.
        self._rebuild_queue(select_cue_id=None)

    @property
    def cues(self) -> list[Cue]:
        return list(self._cues)

    def set_cues_and_priorities(
        self,
        cues: list[Cue],
        observations_by_id: dict[str, Observation],
        priorities_by_cue_id: dict[str, ReviewPriority],
    ) -> None:
        """Replaces the workspace's whole review session -- e.g. once a
        real OCR/reconstruction run finishes and there is something new
        to review. The window itself (and its Path-specific center
        widget) is not rebuilt; only the queue/right-pane content is."""
        self._cues = list(cues)
        self._observations_by_id = observations_by_id
        self._priorities_by_cue_id = dict(priorities_by_cue_id)
        self._rebuild_queue(select_cue_id=None)

    def cue_id_for_row(self, row: int) -> str | None:
        item = self.queue.item(row)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    @property
    def active_cue(self) -> Cue | None:
        cue_id = self.cue_id_for_row(self.queue.currentRow())
        if cue_id is None:
            return None
        return next((cue for cue in self._cues if cue.id == cue_id), None)

    def _priority_for(self, cue_id: str) -> ReviewPriority:
        return self._priorities_by_cue_id.get(
            cue_id, ReviewPriority(cue_id=cue_id, score=0.0, level="None", components=())
        )

    def _rebuild_queue(self, *, select_cue_id: str | None) -> None:
        ordered = sorted(
            self._cues, key=lambda cue: self._priority_for(cue.id).score, reverse=True
        )
        self.queue.blockSignals(True)
        self.queue.clear()
        select_row = 0
        for row, cue in enumerate(ordered):
            priority = self._priority_for(cue.id)
            item = QListWidgetItem(f"[{priority.level}] {queue_label_for_cue(cue)}")
            item.setData(Qt.ItemDataRole.UserRole, cue.id)
            self.queue.addItem(item)
            if cue.id == select_cue_id:
                select_row = row
        self.queue.blockSignals(False)
        if self.queue.count():
            self.queue.setCurrentRow(select_row)
        else:
            self._on_row_changed(-1)

    def _on_row_changed(self, _row: int) -> None:
        # A direct click on a different queue row reaches this signal
        # without going through any of the wrapper methods below (which
        # already commit pending edits themselves before they run) --
        # this call is the safety net for that path. Idempotent: if the
        # edit was already committed by a wrapper method, this is a
        # harmless no-op (the panel's current text already matches the
        # committed Cue text).
        self._commit_displayed_edits()
        self._refresh_active_pane()
        if self._on_active_cue_changed is not None:
            self._on_active_cue_changed(self.active_cue)

    def _commit_displayed_edits(self) -> None:
        """Commits whatever is currently typed into the language-layer
        text edits into `self._cues`, for the Cue that was on screen
        just before this call (`self._displayed_cue_id`) -- NOT
        `self.active_cue`, which may already reflect a row change that
        already happened (e.g. inside `_on_row_changed`, after
        `queue.setCurrentRow` already moved the current row).

        Every action that can switch the active Cue, rebuild the panel,
        or otherwise change a Cue -- Approve, Discard, timing nudge,
        Split, Merge, Previous/Next, and direct queue-row selection --
        calls this first, so a hand-edit is never silently lost by
        anything other than Approve (ROADMAP M7 correctness gate)."""
        if self._displayed_cue_id is None:
            return
        cue = next((c for c in self._cues if c.id == self._displayed_cue_id), None)
        if cue is None:
            return
        for language, text in self.language_layers_panel.current_texts().items():
            existing = next(
                (layer for layer in cue.language_layers if layer.language == language), None
            )
            if existing is not None and existing.text != text:
                self._cues = edit_cue_language_text(self._cues, cue.id, language, text)

    def _refresh_active_pane(self) -> None:
        cue = self.active_cue
        if cue is None:
            self._displayed_cue_id = None
            self.cue_identity_label.setText("")
            self.priority_label.setText("")
            self.diagnostics_view.clear()
            self.language_layers_panel.set_cue(None)
            self.evidence_view.clear()
            return

        priority = self._priority_for(cue.id)
        self.cue_identity_label.setText(f"{cue.id}   {cue.start_time:.3f}s – {cue.end_time:.3f}s")
        self.priority_label.setText(_priority_label(priority))
        self.diagnostics_view.setPlainText(_diagnostics_text(priority))
        self.language_layers_panel.set_cue(cue)
        self._displayed_cue_id = cue.id
        for card in self.language_layers_panel.cards:
            if card.text_edit is not None:
                card.text_edit.installEventFilter(self._approve_filter)
        self.split_time_spin.setRange(cue.start_time, cue.end_time)
        self.split_time_spin.setValue((cue.start_time + cue.end_time) / 2)

        if self.show_full_evidence_checkbox.isChecked():
            observation_ids: list[str] = []
            for layer in cue.language_layers:
                observation_ids.extend(layer.observation_ids)
            shown = [
                self._observations_by_id[observation_id]
                for observation_id in observation_ids
                if observation_id in self._observations_by_id
            ]
        else:
            # Curated evidence is selected PER language layer, against
            # that layer's OWN winning text and OWN observations -- not
            # against the whole Cue's first/primary layer. A fully
            # correct zh layer's observations are never "different from
            # winning_text" here just because zh naturally differs from
            # the Cue's en layer; each layer only ever disagrees with
            # itself.
            shown = []
            seen_ids: set[str] = set()
            for layer in cue.language_layers:
                layer_observations = [
                    self._observations_by_id[observation_id]
                    for observation_id in layer.observation_ids
                    if observation_id in self._observations_by_id
                ]
                for observation in select_curated_evidence(layer_observations, layer.text):
                    if observation.id not in seen_ids:
                        shown.append(observation)
                        seen_ids.add(observation.id)
            shown.sort(key=lambda observation: observation.start_time)

        self.evidence_view.setPlainText(
            "\n".join(f"{observation.start_time:.3f}s  {observation.text}" for observation in shown)
        )

    def approve_and_advance(self) -> None:
        self._commit_displayed_edits()
        cue = self.active_cue
        if cue is None:
            return
        self._cues = approve_cue(self._cues, cue.id)
        self.go_to_next()

    def discard_active_cue(self) -> None:
        self._commit_displayed_edits()
        cue = self.active_cue
        if cue is None:
            return
        self._cues = discard_cue(self._cues, cue.id)
        self._rebuild_queue(select_cue_id=cue.id)

    def _nudge_active(self, *, start_delta: float = 0.0, end_delta: float = 0.0) -> None:
        self._commit_displayed_edits()
        cue = self.active_cue
        if cue is None:
            return
        try:
            self._cues = nudge_cue_timing(self._cues, cue.id, start_delta=start_delta, end_delta=end_delta)
        except ValueError:
            return  # invalid nudge (e.g. would invert the range) -- silently refused, not applied
        self._rebuild_queue(select_cue_id=cue.id)

    def split_active_cue(self) -> None:
        self._commit_displayed_edits()
        cue = self.active_cue
        if cue is None:
            return
        try:
            self._cues = split_cue(self._cues, cue.id, self.split_time_spin.value())
        except ValueError:
            return
        # Neither half has real, re-run reconstruction diagnostics yet
        # -- carry the parent's priority forward for both rather than
        # fabricate a fresh score for evidence that was never re-scored.
        parent_priority = self._priorities_by_cue_id.get(cue.id)
        next_select = None
        for new_cue in self._cues:
            if new_cue.id not in self._priorities_by_cue_id and parent_priority is not None:
                self._priorities_by_cue_id[new_cue.id] = ReviewPriority(
                    cue_id=new_cue.id,
                    score=parent_priority.score,
                    level=parent_priority.level,
                    components=parent_priority.components,
                )
                next_select = next_select or new_cue.id
        self._rebuild_queue(select_cue_id=next_select)

    def _temporal_next_cue(self, cue: Cue) -> Cue | None:
        """The Cue immediately following `cue` in the underlying Cue
        TIMELINE (sorted by start_time) -- deliberately NOT the next row
        in the Review-Priority-ordered queue, which is a completely
        different order once any Cue's priority differs from strict
        chronological order. "Merge with Next" is a timeline operation
        (two temporally adjacent captions), not a queue-navigation one."""
        ordered = sorted(self._cues, key=lambda c: c.start_time)
        for index, candidate in enumerate(ordered):
            if candidate.id == cue.id:
                return ordered[index + 1] if index + 1 < len(ordered) else None
        return None

    def merge_active_cue_with_next(self) -> None:
        self._commit_displayed_edits()
        cue = self.active_cue
        if cue is None:
            return
        next_cue = self._temporal_next_cue(cue)
        if next_cue is None:
            return
        next_cue_id = next_cue.id
        self._cues, merged_id = merge_cues(self._cues, cue.id, next_cue_id)
        first_priority = self._priorities_by_cue_id.get(cue.id)
        second_priority = self._priorities_by_cue_id.get(next_cue_id)
        best = max(
            [priority for priority in (first_priority, second_priority) if priority is not None],
            key=lambda priority: priority.score,
            default=None,
        )
        if best is not None:
            self._priorities_by_cue_id[merged_id] = ReviewPriority(
                cue_id=merged_id, score=best.score, level=best.level, components=best.components
            )
        self._rebuild_queue(select_cue_id=merged_id)

    def go_to_next(self) -> None:
        self._commit_displayed_edits()
        row = self.queue.currentRow()
        if row + 1 < self.queue.count():
            self.queue.setCurrentRow(row + 1)

    def go_to_previous(self) -> None:
        self._commit_displayed_edits()
        row = self.queue.currentRow()
        if row - 1 >= 0:
            self.queue.setCurrentRow(row - 1)

    def _on_play_pause_shortcut(self) -> None:
        if self._play_pause_callback is not None:
            self._play_pause_callback()

    def _on_replay_shortcut(self) -> None:
        self._on_replay_clicked()

    def _on_replay_clicked(self) -> None:
        cue = self.active_cue
        if cue is not None and self._replay_callback is not None:
            self._replay_callback(cue)

    def add_right_pane_widget(self, widget: QWidget) -> None:
        """Appends `widget` to the bottom of the right pane -- the seam
        a caller uses for path-specific extras that don't belong in the
        shared QA controls themselves (e.g. Path B's Export button).
        Never used for QA actions (Approve/Split/Merge/Discard) or
        Review Priority/diagnostics display, which stay identical
        across paths."""
        self._right_layout.addWidget(widget)
