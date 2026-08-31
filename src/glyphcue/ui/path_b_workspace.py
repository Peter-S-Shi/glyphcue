from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from glyphcue.adapters.pysubs2_subtitle_io import ImportWarning
from glyphcue.application.reconstruction import PathBDiagnostics
from glyphcue.application.review_priority import (
    ReviewPriority,
    compute_review_priority,
    review_signals_from_path_b_diagnostics,
)
from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation
from glyphcue.ui.compact_timeline import CompactTimeline
from glyphcue.ui.design_tokens import Spacing
from glyphcue.ui.export_controls import ExportControls
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
    consolidation explanation widget -- no second QA UI.

    DESIGN.md section 17 (Preserved / No-Change State): when real
    diagnostics exist and NONE of them fired, that is itself a real,
    positive fact -- a structurally normal caption GlyphCue did not
    need to touch -- and must say so explicitly rather than showing
    nothing, which would be indistinguishable from "no diagnostics were
    ever computed" (the `diagnostics is None` case below)."""
    if diagnostics is None:
        return None
    kinds = [label for field_name, label in _NORMALIZATION_KIND_LABELS if getattr(diagnostics, field_name)]
    if not kinds:
        return "Preserved 1:1 — no reconstruction required"
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


def _cue_source_observations(
    cue: Cue | None, observations_by_id: dict[str, Observation]
) -> list[Observation]:
    if cue is None:
        return []
    source_ids = [
        observation_id for layer in cue.language_layers for observation_id in layer.observation_ids
    ]
    observations = [
        observations_by_id[observation_id]
        for observation_id in source_ids
        if observation_id in observations_by_id
    ]
    observations.sort(key=lambda observation: observation.start_time)
    return observations


def _raw_timed_caption_stream_text(
    cue: Cue | None, observations_by_id: dict[str, Observation]
) -> str:
    """DESIGN.md section 14.1's Raw Timed Caption Stream: every source
    observation's own id/timing/text that fed the active reconstructed
    Cue, in source-time order -- the raw evidence, not the curated/
    consolidated view (that is `_consolidation_explanation`)."""
    if cue is None:
        return ""
    observations = _cue_source_observations(cue, observations_by_id)
    if not observations:
        return "No source observations recorded for this Cue."
    return "\n".join(
        f"{observation.id}  {observation.start_time:.3f}s–{observation.end_time:.3f}s  {observation.text}"
        for observation in observations
    )


def _timing_collision_track_text(
    cue: Cue | None,
    observations_by_id: dict[str, Observation],
    diagnostics_by_cue_id: dict[str, PathBDiagnostics],
) -> str:
    """DESIGN.md section 14.3's Timing / Collision Track: source
    observation spans, the reconstructed Cue's own span, and an
    explicit collision/review-boundary marker when M8's diagnostics
    flagged one -- makes temporal normalization inspectable rather than
    only described in prose."""
    if cue is None:
        return ""
    lines = [
        f"Source {observation.id}: {observation.start_time:.3f}s – {observation.end_time:.3f}s"
        for observation in _cue_source_observations(cue, observations_by_id)
    ]
    lines.append(f"Reconstructed {cue.id}: {cue.start_time:.3f}s – {cue.end_time:.3f}s")
    diagnostics = diagnostics_by_cue_id.get(cue.id)
    if diagnostics is not None and diagnostics.timing_collision:
        lines.append("⚠ Timing collision — flagged for review")
    return "\n".join(lines)


def _timeline_data(
    cue: Cue | None,
    observations_by_id: dict[str, Observation],
    diagnostics_by_cue_id: dict[str, PathBDiagnostics],
) -> tuple[float, list[tuple[float, float, str]]]:
    """DESIGN.md section 49's Path B compact timeline: source-
    observation spans, the reconstructed Cue's own span (or a
    "collision" role when `PathBDiagnostics.timing_collision` fired),
    scaled to the local evidence window for the active Cue -- not the
    whole file, matching `timing_view`'s own per-Cue scope."""
    if cue is None:
        return 0.0, []
    observations = _cue_source_observations(cue, observations_by_id)
    window_start = min([cue.start_time, *(o.start_time for o in observations)], default=cue.start_time)
    window_end = max([cue.end_time, *(o.end_time for o in observations)], default=cue.end_time)
    duration = window_end - window_start

    spans = [
        (observation.start_time - window_start, observation.end_time - window_start, "source")
        for observation in observations
    ]
    diagnostics = diagnostics_by_cue_id.get(cue.id)
    reconstructed_role = "collision" if diagnostics is not None and diagnostics.timing_collision else "reconstructed"
    spans.append((cue.start_time - window_start, cue.end_time - window_start, reconstructed_role))
    return duration, spans


def _ingestion_profile_text(
    source_path: Path,
    observations_by_id: dict[str, Observation],
    cues: list[Cue],
    import_warnings: list[ImportWarning],
) -> str:
    """DESIGN.md section 15's Path B left-pane ingestion/normalization
    profile: source filename, format, source/output cue counts, and
    the non-destructive-source status, always visible (not only on the
    active Cue) since it describes the whole import, not one Cue.

    "Source cues" is the real count of structurally-read source
    events -- kept Observations PLUS any recoverable-skipped events
    (M8's `ImportWarning`s) -- never just `len(observations_by_id)`,
    which would understate the real source-event count and silently
    pass off "events we kept" as "source cues" whenever the adapter
    had to skip one."""
    format_name = source_path.suffix.lstrip(".").upper() or "?"
    source_event_count = len(observations_by_id) + len(import_warnings)
    return (
        f"{source_path.name}  ({format_name})\n"
        f"Source cues: {source_event_count}  →  Output cues: {len(cues)}\n"
        "Source protected — original file is never modified"
    )


class PathBWorkspace:
    """Wires Path B's timed-caption reconstruction into the shared
    Milestone 7 Reconstruction QA seam (`ReconstructionQaWorkspace`),
    so Path A and Path B follow the same review grammar (DESIGN.md
    section 6's frozen three-pane shell) -- the center pane is the only
    thing that differs per path, per DESIGN.md section 7.2.

    Center pane here is Path B's own "Timed Text Evidence Workspace"
    (DESIGN.md section 14): the Raw Timed Caption Stream (14.1), the
    Consolidation / Reconstruction Explanation (14.2), and the Timing /
    Collision Track (14.3), plus a left-pane ingestion profile (section
    15) and Preserved 1:1 state for structurally clean input (section
    17).
    """

    def __init__(
        self,
        cues: list[Cue],
        observations_by_id: dict[str, Observation],
        source_path: Path,
        diagnostics_by_cue_id: dict[str, PathBDiagnostics] | None = None,
        import_warnings: list[ImportWarning] | None = None,
        on_open_video: Callable[[Path], None] | None = None,
    ) -> None:
        self._source_path = source_path
        self._observations_by_id = observations_by_id
        self._diagnostics_by_cue_id = diagnostics_by_cue_id or {}
        self._on_open_video = on_open_video
        diagnostics_by_cue_id = self._diagnostics_by_cue_id

        self.raw_stream_view = QTextEdit()
        self.raw_stream_view.setReadOnly(True)
        self.consolidation_view = QTextEdit()
        self.consolidation_view.setReadOnly(True)
        self.timing_view = QTextEdit()
        self.timing_view.setReadOnly(True)
        self.timeline = CompactTimeline()
        center_pane = QWidget()
        center_layout = QVBoxLayout(center_pane)
        center_layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        center_layout.addWidget(QLabel("Timed Text Evidence Workspace"))
        center_layout.addWidget(QLabel("Raw Timed Caption Stream"))
        center_layout.addWidget(self.raw_stream_view)
        center_layout.addWidget(QLabel("Consolidation / Reconstruction Explanation"))
        center_layout.addWidget(self.consolidation_view)
        center_layout.addWidget(QLabel("Timing / Collision Track"))
        center_layout.addWidget(self.timing_view)
        center_layout.addWidget(self.timeline)

        priorities = {cue.id: _priority_for_cue(cue.id, diagnostics_by_cue_id) for cue in cues}

        self.qa = ReconstructionQaWorkspace(
            cues,
            observations_by_id,
            priorities,
            center_pane,
            on_active_cue_changed=self._on_active_cue_changed,
            filter_labels=("All Reconstructed", "Review Needed", "Preserved"),
        )
        self.window = self.qa.window
        self.queue = self.qa.queue

        self.ingestion_profile_label = QLabel(
            _ingestion_profile_text(source_path, observations_by_id, cues, import_warnings or [])
        )
        self.ingestion_profile_label.setWordWrap(True)
        self.qa.add_left_pane_widget(self.ingestion_profile_label)

        self.export_controls = ExportControls(
            get_cues=lambda: self.qa.cues,
            commit_pending_edits=self.qa.commit_pending_edits,
            source_path=source_path,
        )
        self.qa.add_right_pane_widget(self.export_controls.widget)

        self.import_warnings_label = QLabel(_import_warnings_text(import_warnings or []))
        self.import_warnings_label.setWordWrap(True)
        self.qa.add_right_pane_widget(self.import_warnings_label)

        self.open_video_button = QPushButton("Open Video (Path A)…")
        self.open_video_button.setEnabled(on_open_video is not None)
        self.open_video_button.clicked.connect(self._on_open_video_clicked)
        self.qa.add_right_pane_widget(self.open_video_button)

        self._on_active_cue_changed(self.qa.active_cue)

    @property
    def cues(self) -> list[Cue]:
        return self.qa.cues

    @property
    def active_cue(self) -> Cue | None:
        return self.qa.active_cue

    def _on_active_cue_changed(self, cue: Cue | None) -> None:
        self.raw_stream_view.setPlainText(
            _raw_timed_caption_stream_text(cue, self._observations_by_id)
        )
        self.consolidation_view.setPlainText(
            _consolidation_explanation(cue, self._observations_by_id, self._diagnostics_by_cue_id)
        )
        self.timing_view.setPlainText(
            _timing_collision_track_text(cue, self._observations_by_id, self._diagnostics_by_cue_id)
        )
        duration, spans = _timeline_data(cue, self._observations_by_id, self._diagnostics_by_cue_id)
        self.timeline.set_data(duration, spans)

    def export(self) -> Path:
        return self.export_controls.export()

    def switch_to_video(self, path: Path) -> None:
        """Reaches Path A directly from an already-open Path B
        workbench (DESIGN.md section 9): switching paths is changing
        evidence-source mode inside one product, not restarting the
        app. Delegates to the shared entry (`GlyphCueEntry`) via the
        injected callback so the same window-transition logic used at
        first launch is reused, not duplicated."""
        if self._on_open_video is not None:
            self._on_open_video(path)

    def _on_open_video_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            None, "Open Video", "", "Video files (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if path_str:
            self.switch_to_video(Path(path_str))
