from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from glyphcue.adapters.pysubs2_subtitle_io import ImportWarning, Pysubs2SubtitleFormatAdapter
from glyphcue.adapters.transcript_export import write_ai_ready_transcript, write_readable_transcript
from glyphcue.application.reconstruction import PathBDiagnostics
from glyphcue.application.review_priority import (
    ReviewPriority,
    compute_review_priority,
    review_signals_from_path_b_diagnostics,
)
from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation
from glyphcue.ui.design_tokens import Spacing
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace


def _no_priority_signal(cue_id: str) -> ReviewPriority:
    """Pre-M8 fallback: without real `PathBDiagnostics` for a Cue (e.g.
    a caller that hasn't been updated to pass them), there is no signal
    to rank it by. Every such Cue gets an honest "no signal" priority
    (`level="None"`) rather than a fabricated score."""
    return ReviewPriority(cue_id=cue_id, score=0.0, level="None", components=())


def _priority_for_cue(cue_id: str, diagnostics_by_cue_id: dict[str, PathBDiagnostics]) -> ReviewPriority:
    diagnostics = diagnostics_by_cue_id.get(cue_id)
    if diagnostics is None:
        return _no_priority_signal(cue_id)
    return compute_review_priority(review_signals_from_path_b_diagnostics(diagnostics))


_NORMALIZATION_KIND_LABELS = (
    ("source_order_issue", "Source order issue"),
    ("timing_collision", "Timing collision"),
    ("segmentation_ambiguous", "Segmentation ambiguous"),
    ("rolling_growth", "Rolling growth consolidated"),
    ("sliding_overlap", "Sliding overlap consolidated"),
    ("repetition_collapsed", "Repetition collapsed"),
)


def _normalization_kind_line(diagnostics: PathBDiagnostics | None) -> str | None:
    """A plain-language line naming which M8 normalization phenomena
    this Cue actually went through -- shown regardless of whether any
    of them raised Review Priority. A confidently-resolved rolling/
    sliding/repetition Cue stays "No Review Flags" (M8's whole point:
    content GlyphCue could reliably restore doesn't need a human
    re-check), but the reviewer must still be able to SEE what actually
    happened, not just a blank center pane. Reuses the existing
    consolidation explanation widget -- no second QA UI."""
    if diagnostics is None:
        return None
    kinds = [label for field_name, label in _NORMALIZATION_KIND_LABELS if getattr(diagnostics, field_name)]
    if not kinds:
        return None
    return "Normalization: " + ", ".join(kinds)


def _import_warnings_text(import_warnings: list[ImportWarning]) -> str:
    """A minimal, DESIGN-conformant presentation of M8's per-event
    import warnings (ROADMAP M9): a real recoverable-skipped-event
    count plus each event's own source index/reason, never a log
    console or diagnostic-JSON UI (DESIGN.md section 29). Empty when
    there is nothing to report -- most imports have no warnings."""
    if not import_warnings:
        return ""
    count = len(import_warnings)
    noun = "event" if count == 1 else "events"
    header = f"{count} source {noun} skipped on import (kept the rest):"
    details = [f"  #{warning.source_index}: {warning.reason}" for warning in import_warnings]
    return "\n".join([header, *details])


def _consolidation_explanation(
    cue: Cue | None,
    observations_by_id: dict[str, Observation],
    diagnostics_by_cue_id: dict[str, PathBDiagnostics],
) -> str:
    """DESIGN.md section 14.2's "Consolidation / Reconstruction
    Explanation": which source observations became this reconstructed
    Cue -- descriptive, not falsely authoritative about an algorithm
    that is only known by its behavior. Also names which M8
    normalization phenomena (if any) were involved, independent of
    whether that raised a Review Priority flag."""
    if cue is None:
        return ""
    source_ids = [
        observation_id for layer in cue.language_layers for observation_id in layer.observation_ids
    ]
    if not source_ids:
        base = f"Reconstructed Cue {cue.id} has no recorded source observations."
    else:
        sources = " + ".join(source_ids)
        base = f"Source observations {sources}\n→ Reconstructed Cue {cue.id}"

    kind_line = _normalization_kind_line(diagnostics_by_cue_id.get(cue.id))
    if kind_line is None:
        return base
    return f"{base}\n{kind_line}"


class PathBWorkspace:
    """Wires Path B's timed-caption reconstruction into the shared
    Milestone 7 Reconstruction QA seam (`ReconstructionQaWorkspace`),
    so Path A and Path B follow the same review grammar (DESIGN.md
    section 6's frozen three-pane shell) -- the center pane is the only
    thing that differs per path, per DESIGN.md section 7.2.

    Center pane here is Path B's own "Timed Text Evidence Workspace"
    (DESIGN.md section 14): a consolidation explanation showing which
    source observations became the active reconstructed Cue.
    """

    def __init__(
        self,
        cues: list[Cue],
        observations_by_id: dict[str, Observation],
        source_path: Path,
        export_destination: Path,
        diagnostics_by_cue_id: dict[str, PathBDiagnostics] | None = None,
        import_warnings: list[ImportWarning] | None = None,
    ) -> None:
        self._source_path = source_path
        self._export_destination = export_destination
        self._observations_by_id = observations_by_id
        self._adapter = Pysubs2SubtitleFormatAdapter()
        self._diagnostics_by_cue_id = diagnostics_by_cue_id or {}
        diagnostics_by_cue_id = self._diagnostics_by_cue_id

        self.consolidation_view = QTextEdit()
        self.consolidation_view.setReadOnly(True)
        center_pane = QWidget()
        center_layout = QVBoxLayout(center_pane)
        center_layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        center_layout.addWidget(QLabel("Timed Text Evidence Workspace"))
        center_layout.addWidget(self.consolidation_view)

        priorities = {cue.id: _priority_for_cue(cue.id, diagnostics_by_cue_id) for cue in cues}

        self.qa = ReconstructionQaWorkspace(
            cues,
            observations_by_id,
            priorities,
            center_pane,
            on_active_cue_changed=self._on_active_cue_changed,
        )
        self.window = self.qa.window
        self.queue = self.qa.queue

        self.export_button = QPushButton("Export")
        self.export_readable_transcript_button = QPushButton("Export Readable Transcript")
        self.export_ai_ready_transcript_button = QPushButton("Export AI-ready Transcript")
        self.status_label = QLabel("Source protected — writes normalized output to a new file")
        self.qa.add_right_pane_widget(self.export_button)
        self.qa.add_right_pane_widget(self.export_readable_transcript_button)
        self.qa.add_right_pane_widget(self.export_ai_ready_transcript_button)
        self.qa.add_right_pane_widget(self.status_label)
        self.export_button.clicked.connect(self._on_export_button_clicked)
        self.export_readable_transcript_button.clicked.connect(
            self._on_export_readable_transcript_clicked
        )
        self.export_ai_ready_transcript_button.clicked.connect(
            self._on_export_ai_ready_transcript_clicked
        )

        self.import_warnings_label = QLabel(_import_warnings_text(import_warnings or []))
        self.import_warnings_label.setWordWrap(True)
        self.qa.add_right_pane_widget(self.import_warnings_label)

        self._on_active_cue_changed(self.qa.active_cue)

    @property
    def cues(self) -> list[Cue]:
        return self.qa.cues

    @property
    def active_cue(self) -> Cue | None:
        return self.qa.active_cue

    def _on_active_cue_changed(self, cue: Cue | None) -> None:
        self.consolidation_view.setPlainText(
            _consolidation_explanation(cue, self._observations_by_id, self._diagnostics_by_cue_id)
        )

    def export(self) -> Path:
        """Write the current cues to the export destination.

        Refuses to overwrite the source file, regardless of what
        destination the workspace was constructed with -- this check
        lives here (not only in the orchestration layer that picks the
        default destination) so no caller of this class can accidentally
        bypass it.
        """
        if self._export_destination.resolve() == self._source_path.resolve():
            raise ValueError(
                "Export refused: destination must not overwrite the source file"
            )
        # A live, un-Approved hand-edit sitting in the active language-
        # layer text edit must not be silently lost just because the
        # user exports immediately without Approving or navigating away
        # first -- commit it before reading `self.qa.cues`. This never
        # changes review_state; it is not an implicit Approve.
        self.qa.commit_pending_edits()
        self._adapter.write(self.qa.cues, self._export_destination)
        self.status_label.setText(f"Exported to {self._export_destination}")
        return self._export_destination

    def _on_export_button_clicked(self) -> None:
        try:
            self.export()
        except ValueError as exc:
            self.status_label.setText(str(exc))

    def _transcript_destination(self, suffix: str) -> Path:
        return self._source_path.with_name(f"{self._source_path.stem}{suffix}")

    def _export_transcript(self, destination: Path, writer) -> Path:
        """Shared write path for both transcript presets: same
        non-destructive-source refusal and pending-edit-commit contract
        as `export()`'s SRT/VTT path (DESIGN.md section 16)."""
        if destination.resolve() == self._source_path.resolve():
            raise ValueError(
                "Export refused: destination must not overwrite the source file"
            )
        self.qa.commit_pending_edits()
        writer(self.qa.cues, destination)
        self.status_label.setText(f"Exported to {destination}")
        return destination

    def export_readable_transcript(self) -> Path:
        return self._export_transcript(
            self._transcript_destination(".transcript.txt"), write_readable_transcript
        )

    def export_ai_ready_transcript(self) -> Path:
        return self._export_transcript(
            self._transcript_destination(".transcript.ai.md"), write_ai_ready_transcript
        )

    def _on_export_readable_transcript_clicked(self) -> None:
        try:
            self.export_readable_transcript()
        except ValueError as exc:
            self.status_label.setText(str(exc))

    def _on_export_ai_ready_transcript_clicked(self) -> None:
        try:
            self.export_ai_ready_transcript()
        except ValueError as exc:
            self.status_label.setText(str(exc))
