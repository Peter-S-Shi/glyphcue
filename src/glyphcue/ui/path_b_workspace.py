from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from glyphcue.adapters.pysubs2_subtitle_io import Pysubs2SubtitleFormatAdapter
from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation
from glyphcue.ui.design_tokens import Spacing
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace

_NO_PRIORITY_SIGNAL_EXPLANATION = (
    "Path B (subtitle-file import) reconstruction does not currently produce "
    "OCR-confidence/disagreement diagnostics the way Path A's OCR pipeline "
    "does -- Review Priority has no signal to rank this Cue by yet, so it "
    "shows 'No Review Flags' rather than a fabricated score."
)


def _no_priority_signal(cue_id: str) -> ReviewPriority:
    """Path B's `reconstruct_cues` (application/reconstruction.py) does
    not emit per-Cue reconstruction diagnostics the way M5/M6's Path A
    pipeline does -- there is no real cross-frame disagreement or OCR
    confidence signal to build a `ReviewSignals` from. Every Path B Cue
    therefore gets an honest "no signal" priority (`level="None"`)
    rather than a fabricated score; this is a documented scope
    boundary, not a silent gap (see docs/qa/reconstruction_qa_review_priority.md)."""
    return ReviewPriority(cue_id=cue_id, score=0.0, level="None", components=())


def _consolidation_explanation(cue: Cue | None, observations_by_id: dict[str, Observation]) -> str:
    """DESIGN.md section 14.2's "Consolidation / Reconstruction
    Explanation": which source observations became this reconstructed
    Cue -- descriptive, not falsely authoritative about an algorithm
    that is only known by its behavior."""
    if cue is None:
        return ""
    source_ids = [
        observation_id for layer in cue.language_layers for observation_id in layer.observation_ids
    ]
    if not source_ids:
        return f"Reconstructed Cue {cue.id} has no recorded source observations."
    sources = " + ".join(source_ids)
    return f"Source observations {sources}\n→ Reconstructed Cue {cue.id}"


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
    ) -> None:
        self._source_path = source_path
        self._export_destination = export_destination
        self._observations_by_id = observations_by_id
        self._adapter = Pysubs2SubtitleFormatAdapter()

        self.consolidation_view = QTextEdit()
        self.consolidation_view.setReadOnly(True)
        center_pane = QWidget()
        center_layout = QVBoxLayout(center_pane)
        center_layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        center_layout.addWidget(QLabel("Timed Text Evidence Workspace"))
        center_layout.addWidget(self.consolidation_view)

        priorities = {cue.id: _no_priority_signal(cue.id) for cue in cues}

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
        self.status_label = QLabel("Source protected — writes normalized output to a new file")
        self.qa.add_right_pane_widget(self.export_button)
        self.qa.add_right_pane_widget(self.status_label)
        self.export_button.clicked.connect(self._on_export_button_clicked)

        self._on_active_cue_changed(self.qa.active_cue)

    @property
    def cues(self) -> list[Cue]:
        return self.qa.cues

    @property
    def active_cue(self) -> Cue | None:
        return self.qa.active_cue

    def _on_active_cue_changed(self, cue: Cue | None) -> None:
        self.consolidation_view.setPlainText(
            _consolidation_explanation(cue, self._observations_by_id)
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
        self._adapter.write(self.qa.cues, self._export_destination)
        self.status_label.setText(f"Exported to {self._export_destination}")
        return self._export_destination

    def _on_export_button_clicked(self) -> None:
        try:
            self.export()
        except ValueError as exc:
            self.status_label.setText(str(exc))
