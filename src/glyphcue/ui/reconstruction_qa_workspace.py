from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
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
from glyphcue.domain.review_state import ReviewState
from glyphcue.ui.design_tokens import Color, Spacing
from glyphcue.ui.language_layer_presentation import LanguageLayersPanel, queue_label_for_cue
from glyphcue.ui.main_window import MainWindow

_TIMING_NUDGE_STEP_SECONDS = 0.05
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

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ShortcutOverride and _is_approve_key_event(event):
            event.accept()
            return True
        if event.type() == QEvent.Type.KeyPress and _is_approve_key_event(event):
            self._callback()
            event.accept()
            return True
        return super().eventFilter(watched, event)


class _CloseEventFilter(QObject):
    def __init__(self, on_close: Callable[[], None], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._on_close = on_close

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Close:
            self._on_close()
        return super().eventFilter(watched, event)


def review_state_badge(state: ReviewState) -> str:
    """Clear text + graphic status marker for ReviewState (not color-only)."""
    if state is ReviewState.APPROVED:
        return "✓ Approved"
    elif state == ReviewState.REJECTED:
        return "✕ Discarded"
    elif state == ReviewState.NEEDS_REVIEW:
        return "⚠ Needs Review"
    else:  # PENDING
        return "○ Pending"


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

    Operates on an in-memory `list[Cue]` and remains persistence-agnostic:
    notifies callers of any Cue modifications via `on_cues_changed`,
    allowing host panes to persist changes according to their lifecycle
    contracts. Path A connects this to atomic source-bound SQLite
    persistence supporting full restart resume, while Path B maintains its
    in-memory session/export lifecycle.

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
        on_cues_changed: Callable[[list[Cue]], None] | None = None,
        filter_labels: tuple[str, str, str] = ("All", "Review Needed", "Clean / Approved"),
        third_filter_predicate: Callable[[Cue], bool] | None = None,
    ) -> None:
        self._cues = list(cues)
        self._observations_by_id = observations_by_id
        self._priorities_by_cue_id = dict(priorities_by_cue_id)
        self._play_pause_callback = play_pause_callback
        self._replay_callback = replay_callback
        self._on_active_cue_changed = on_active_cue_changed
        self._on_cues_changed = on_cues_changed
        self._filter_labels = filter_labels
        self._third_filter_predicate = third_filter_predicate
        self._displayed_cue_id: str | None = None
        self._playback_active_cue_id: str | None = None
        self._approve_filter = _CtrlEnterApproveFilter(lambda: self.approve_and_advance())

        # DESIGN.md section 7.1 / section 53: the left pane must offer
        # search + review filters alongside the queue, with a small,
        # task-oriented frozen baseline -- not a project-manager-style
        # filter taxonomy. Labels are caller-supplied (Path A vs Path B
        # baseline wording) but the underlying semantics are identical:
        # "Review Needed" = a real Review Priority signal exists;
        # the third option = no signal OR already Approved.
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search current text…")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(list(filter_labels))

        self.queue = QListWidget()
        self.queue.setObjectName("cueList")
        self.cue_identity_label = QLabel("")
        self.cue_identity_label.setObjectName("cueIdentityLabel")
        self.cue_identity_label.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {Color.TEXT_PRIMARY};")
        self.review_state_label = QLabel("")
        self.review_state_label.setObjectName("reviewStateLabel")
        self.review_state_label.setStyleSheet(f"font-weight: 600; color: {Color.TEXT_PRIMARY};")
        self.priority_label = QLabel("")
        self.priority_label.setObjectName("reviewPriorityLabel")
        self.priority_label.setStyleSheet(f"color: {Color.TEXT_SECONDARY};")
        self.diagnostics_view = QTextEdit()
        self.diagnostics_view.setObjectName("diagnosticsCard")
        self.diagnostics_view.setReadOnly(True)
        self.language_layers_panel = LanguageLayersPanel(editable=True)

        self.nudge_start_earlier_button = QPushButton("Start −0.05s")
        self.nudge_start_later_button = QPushButton("Start +0.05s")
        self.nudge_end_earlier_button = QPushButton("End −0.05s")
        self.nudge_end_later_button = QPushButton("End +0.05s")

        self.split_time_spin = QDoubleSpinBox()
        self.split_time_spin.setDecimals(3)
        self.split_time_spin.setRange(0.0, 24.0 * 3600.0)
        self.split_button = QPushButton("Split")
        self.split_button.setObjectName("secondaryBtn")
        self.merge_next_button = QPushButton("Merge with Next")
        self.merge_next_button.setObjectName("secondaryBtn")
        self.discard_button = QPushButton("Discard")
        self.discard_button.setObjectName("discardButton")
        self.approve_button = QPushButton("Approve [Ctrl+Enter]")
        self.approve_button.setObjectName("approveButton")
        self.previous_button = QPushButton("Previous [")
        self.previous_button.setObjectName("secondaryBtn")
        self.next_button = QPushButton("Next ]")
        self.next_button.setObjectName("secondaryBtn")
        self.replay_button = QPushButton("Replay [R]")
        self.replay_button.setObjectName("secondaryBtn")

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

        self.evidence_header_label = QLabel("Raw OCR Evidence / Original Machine Observations")
        self.evidence_header_label.setObjectName("evidenceHeaderLabel")
        self.evidence_header_label.setStyleSheet(f"font-weight: 600; color: {Color.TEXT_SECONDARY};")
        self.evidence_note_label = QLabel(
            "Original machine OCR observations are preserved for reference and audit, and remain unchanged when cue text is edited."
        )
        self.evidence_note_label.setObjectName("evidenceNoteLabel")
        self.evidence_note_label.setStyleSheet(f"color: {Color.TEXT_MUTED}; font-size: 11px;")
        self.evidence_note_label.setWordWrap(True)
        self.show_full_evidence_checkbox = QCheckBox("Show full evidence")
        self.evidence_view = QTextEdit()
        self.evidence_view.setReadOnly(True)

        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(
            Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD
        )
        left_layout.setSpacing(Spacing.COMPACT)

        # Dedicated scrollable container for injected structure/metadata widgets
        self._left_structure_container = QWidget()
        self._left_structure_layout = QVBoxLayout(self._left_structure_container)
        self._left_structure_layout.setContentsMargins(0, 0, 0, 0)
        self._left_structure_layout.setSpacing(Spacing.COMPACT)

        self._left_structure_scroll = QScrollArea()
        self._left_structure_scroll.setObjectName("leftPaneStructureScroll")
        self._left_structure_scroll.setWidgetResizable(True)
        self._left_structure_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._left_structure_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._left_structure_scroll.setWidget(self._left_structure_container)
        self._left_structure_scroll.setMaximumHeight(340)

        left_layout.addWidget(self._left_structure_scroll)
        left_layout.addWidget(self.search_edit)
        left_layout.addWidget(self.filter_combo)
        left_layout.addWidget(self.queue, stretch=1)
        self._left_layout = left_layout

        right_pane = QWidget()
        right_scroll = QScrollArea(right_pane)
        right_scroll.setObjectName("rightPaneScrollArea")
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        right_content = QWidget()
        right_content.setObjectName("rightPaneContent")
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(
            Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD
        )
        right_layout.setSpacing(Spacing.STANDARD)

        # 1. Header Card (Cue ID, State badge, Priority badge)
        header_card = QWidget()
        header_card.setObjectName("qaHeaderCard")
        header_card_layout = QVBoxLayout(header_card)
        header_card_layout.setContentsMargins(
            Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD
        )
        header_card_layout.addWidget(self.cue_identity_label)
        badges_row = QHBoxLayout()
        badges_row.addWidget(self.review_state_label)
        badges_row.addWidget(self.priority_label)
        badges_row.addStretch(1)
        header_card_layout.addLayout(badges_row)
        right_layout.addWidget(header_card)

        # 2. Diagnostics
        right_layout.addWidget(self.diagnostics_view)

        # 3. Language Layers Editor
        right_layout.addWidget(self.language_layers_panel)

        # 4. 50ms Precision Timing Card (Reflowed 2x2 grid for responsive width)
        timing_card = QWidget()
        timing_card.setObjectName("timingCard")
        timing_card_layout = QVBoxLayout(timing_card)
        timing_card_layout.setContentsMargins(
            Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD
        )
        timing_title = QLabel("TIMING PRECISION (50ms)")
        timing_title.setObjectName("sectionHeaderLabel")
        timing_card_layout.addWidget(timing_title)

        timing_grid = QGridLayout()
        self.nudge_start_earlier_button.setObjectName("secondaryBtn")
        self.nudge_start_later_button.setObjectName("secondaryBtn")
        self.nudge_end_earlier_button.setObjectName("secondaryBtn")
        self.nudge_end_later_button.setObjectName("secondaryBtn")
        timing_grid.addWidget(self.nudge_start_earlier_button, 0, 0)
        timing_grid.addWidget(self.nudge_start_later_button, 0, 1)
        timing_grid.addWidget(self.nudge_end_earlier_button, 1, 0)
        timing_grid.addWidget(self.nudge_end_later_button, 1, 1)
        timing_card_layout.addLayout(timing_grid)
        right_layout.addWidget(timing_card)

        # 5. Split & Merge Tools
        split_merge_row = QHBoxLayout()
        split_merge_row.addWidget(self.split_time_spin)
        split_merge_row.addWidget(self.split_button)
        split_merge_row.addWidget(self.merge_next_button)
        right_layout.addLayout(split_merge_row)

        # 6. Primary QA Action Bar (Dominant full row Approve + sub-actions)
        action_box = QVBoxLayout()
        action_box.addWidget(self.approve_button)
        sub_actions_row = QHBoxLayout()
        sub_actions_row.addWidget(self.previous_button)
        sub_actions_row.addWidget(self.replay_button)
        sub_actions_row.addWidget(self.discard_button)
        sub_actions_row.addWidget(self.next_button)
        action_box.addLayout(sub_actions_row)
        right_layout.addLayout(action_box)

        # 7. Raw Observations Evidence Card
        evidence_card = QWidget()
        evidence_card.setObjectName("evidenceCard")
        evidence_layout = QVBoxLayout(evidence_card)
        evidence_layout.setContentsMargins(
            Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD
        )
        evidence_layout.addWidget(self.evidence_header_label)
        evidence_layout.addWidget(self.evidence_note_label)
        evidence_layout.addWidget(self.show_full_evidence_checkbox)
        evidence_layout.addWidget(self.evidence_view)
        right_layout.addWidget(evidence_card)

        right_scroll.setWidget(right_content)
        right_outer_layout = QVBoxLayout(right_pane)
        right_outer_layout.setContentsMargins(0, 0, 0, 0)
        right_outer_layout.addWidget(right_scroll)
        self._right_layout = right_layout

        self.window = MainWindow(left_pane=left_pane, center_pane=center_widget, right_pane=right_pane)

        self.queue.currentRowChanged.connect(self._on_row_changed)
        self.search_edit.textChanged.connect(lambda _text: self._on_search_or_filter_changed())
        self.filter_combo.currentTextChanged.connect(lambda _text: self._on_search_or_filter_changed())
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

        self._close_filter = _CloseEventFilter(self.commit_pending_edits)
        self.window.installEventFilter(self._close_filter)

    @property
    def central_widget(self) -> QWidget:
        """Returns the embeddable 3-pane central widget (splitter)."""
        return self.window.centralWidget()

    def bind_to_host(self, host: QWidget) -> None:
        """Binds QA keyboard shortcuts to a host window (e.g. GlyphCueWorkbench)
        when hosted inside a persistent product shell."""
        self.play_pause_shortcut.setParent(host)
        self.approve_shortcut.setParent(host)
        self.replay_shortcut.setParent(host)
        self.next_shortcut.setParent(host)
        self.previous_shortcut.setParent(host)

    @property
    def cues(self) -> list[Cue]:
        return list(self._cues)

    def commit_pending_edits(self) -> None:
        """Commits whatever is currently typed into the displayed
        Cue's language-layer text edits into the in-memory Cue list --
        the minimal public persistence seam a caller (e.g. Path A/B
        lifecycle hooks or Export) uses to make sure a live, un-committed
        hand-edit is not silently lost. Never automatically Approves, but
        real text modifications transition the Cue to `ReviewState.NEEDS_REVIEW`
        and trigger `on_cues_changed` for persistence. Safe to call at any
        time, including when nothing is displayed (a no-op)."""
        self._commit_displayed_edits()

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

    def priority_for_cue_id(self, cue_id: str) -> ReviewPriority:
        """Public read of a Cue's current Review Priority -- the seam a
        path-specific caller (e.g. a compact temporal strip needing to
        color a Cue span as flagged/clean) uses instead of reaching
        into the private `_priorities_by_cue_id` mapping."""
        return self._priority_for(cue_id)

    def _matches_search(self, cue: Cue) -> bool:
        query = self.search_edit.text().strip().lower()
        if not query:
            return True
        return any(query in layer.text.lower() for layer in cue.language_layers)

    def _matches_filter(self, cue: Cue) -> bool:
        selection = self.filter_combo.currentText()
        all_label, review_needed_label, _third_label = self._filter_labels
        if selection == all_label:
            return True
        if selection == review_needed_label:
            return self._is_review_needed(cue)
        # Third option (label differs by path, e.g. "Clean / Approved"
        # vs "Preserved"). A caller-supplied predicate (Path B's real
        # PathBDiagnostics check) takes over the bucket's meaning
        # entirely when given -- it is never inferred from Review
        # Priority for a path where that inference would be wrong.
        if self._third_filter_predicate is not None:
            return self._third_filter_predicate(cue)
        return self._is_clean_or_approved(cue)

    def _is_review_needed(self, cue: Cue) -> bool:
        # Real human-review state wins first: an Approved/Rejected Cue
        # is a settled decision and never stays in Review Needed no
        # matter what its (possibly stale) Review Priority score says.
        # A NEEDS_REVIEW Cue (e.g. fresh out of Split/Merge) belongs
        # here even with priority.level == "None" -- a machine split/
        # merge is never itself a correct reconstruction, independent
        # of whether any heuristic flagged it.
        if cue.review_state in (ReviewState.APPROVED, ReviewState.REJECTED):
            return False
        if cue.review_state == ReviewState.NEEDS_REVIEW:
            return True
        return self._priority_for(cue.id).level != "None"

    def _is_clean_or_approved(self, cue: Cue) -> bool:
        # Path A's default third bucket: a genuinely clean Cue (no
        # Review Priority flag, and not Rejected/NEEDS_REVIEW), or a
        # Cue the user has already Approved. A Rejected Cue never
        # counts as clean just because it happens to carry no priority
        # flag -- Discard is itself a review decision, not silence.
        if cue.review_state == ReviewState.APPROVED:
            return True
        if cue.review_state in (ReviewState.REJECTED, ReviewState.NEEDS_REVIEW):
            return False
        return self._priority_for(cue.id).level == "None"

    def _on_search_or_filter_changed(self) -> None:
        # A live text-edit search/filter change is not itself a Cue
        # navigation action, but it can change which row is current --
        # commit first, same discipline as every other queue-mutating
        # action.
        self._commit_displayed_edits()
        self._rebuild_queue(select_cue_id=self._displayed_cue_id)

    @property
    def playback_active_cue_id(self) -> str | None:
        return self._playback_active_cue_id

    def set_playback_active_cue_id(self, cue_id: str | None) -> None:
        """DOG-007: Updates the playback-active Cue indicator in the queue
        without altering the user's active editing selection (active_cue /
        _displayed_cue_id)."""
        if self._playback_active_cue_id == cue_id:
            return
        self._playback_active_cue_id = cue_id
        self._refresh_queue_labels()
        if cue_id is not None:
            for row in range(self.queue.count()):
                item = self.queue.item(row)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == cue_id:
                    self.queue.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)
                    break

    def _queue_item_label(self, cue: Cue) -> str:
        priority = self._priority_for(cue.id)
        prefix = "▶ " if cue.id == self._playback_active_cue_id else ""
        return f"{prefix}[{priority.level}] [{review_state_badge(cue.review_state)}] {queue_label_for_cue(cue)}"

    def _refresh_queue_labels(self) -> None:
        for row in range(self.queue.count()):
            item = self.queue.item(row)
            if item is None:
                continue
            cue_id = item.data(Qt.ItemDataRole.UserRole)
            cue = next((c for c in self._cues if c.id == cue_id), None)
            if cue is not None:
                item.setText(self._queue_item_label(cue))

    def _rebuild_queue(self, *, select_cue_id: str | None) -> None:
        ordered = sorted(
            self._cues, key=lambda cue: self._priority_for(cue.id).score, reverse=True
        )
        ordered = [cue for cue in ordered if self._matches_filter(cue) and self._matches_search(cue)]
        self.queue.blockSignals(True)
        self.queue.clear()
        select_row = 0
        for row, cue in enumerate(ordered):
            item = QListWidgetItem(self._queue_item_label(cue))
            item.setData(Qt.ItemDataRole.UserRole, cue.id)
            self.queue.addItem(item)
            if cue.id == select_cue_id:
                select_row = row
        self.queue.blockSignals(False)
        if self.queue.count():
            self.queue.setCurrentRow(select_row)
            self._refresh_active_pane()
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

    def _notify_cues_changed(self) -> None:
        if self._on_cues_changed is not None:
            self._on_cues_changed(self.cues)

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
        modified = False
        for language, text in self.language_layers_panel.current_texts().items():
            existing = next(
                (layer for layer in cue.language_layers if layer.language == language), None
            )
            if existing is not None and existing.text != text:
                self._cues = edit_cue_language_text(self._cues, cue.id, language, text)
                modified = True
        if modified:
            self._refresh_queue_labels()
            self._notify_cues_changed()

    def _refresh_active_pane(self) -> None:
        cue = self.active_cue
        if cue is None:
            self._displayed_cue_id = None
            self.cue_identity_label.setText("")
            self.review_state_label.setText("")
            self.priority_label.setText("")
            self.diagnostics_view.clear()
            self.language_layers_panel.set_cue(None)
            self.evidence_view.clear()
            return

        priority = self._priority_for(cue.id)
        cue_idx = next((i + 1 for i, c in enumerate(self._cues) if c.id == cue.id), 1)
        duration = cue.end_time - cue.start_time
        self.cue_identity_label.setText(
            f"Cue #{cue_idx} · {cue.start_time:.3f}s – {cue.end_time:.3f}s ({duration:.2f}s)"
        )
        self.cue_identity_label.setToolTip(f"Cue ID: {cue.id}")
        self.review_state_label.setText(f"Review State: {review_state_badge(cue.review_state)}")
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
        self._refresh_queue_labels()
        self._notify_cues_changed()
        if self.queue.currentRow() + 1 < self.queue.count():
            self.go_to_next()
        else:
            self._refresh_active_pane()

    def discard_active_cue(self) -> None:
        self._commit_displayed_edits()
        cue = self.active_cue
        if cue is None:
            return
        self._cues = discard_cue(self._cues, cue.id)
        self._refresh_queue_labels()
        self._notify_cues_changed()
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
        self._refresh_queue_labels()
        self._notify_cues_changed()
        self._refresh_active_pane()
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
        self._notify_cues_changed()
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
        self._notify_cues_changed()
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

    def add_left_pane_widget(self, widget: QWidget) -> None:
        """Appends `widget` into the scrollable structure/context region
        above search and review queue in the left pane."""
        self._left_structure_layout.addWidget(widget)

    def insert_left_pane_widget(self, index: int, widget: QWidget) -> None:
        """Inserts `widget` at `index` in the scrollable structure/context region
        above search and review queue in the left pane."""
        self._left_structure_layout.insertWidget(index, widget)
