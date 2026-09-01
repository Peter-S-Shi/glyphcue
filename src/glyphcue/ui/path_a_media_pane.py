from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.paddleocr_engine import CANONICAL_LANGUAGES
from glyphcue.adapters.pyav_media_source import probe_media
from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.cue_merge import merge_incremental_cues
from glyphcue.application.multilingual_ocr_evidence_job import build_multilingual_ocr_evidence_job
from glyphcue.application.multilingual_reconstruction import (
    reconstruct_multilingual_cues_for_track_group,
)
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.review_priority import (
    ReviewPriority,
    review_signals_from_consensus_diagnostics,
    review_signals_from_multilingual_diagnostics,
    compute_review_priority,
)
from glyphcue.application.source_identity import normalize_source_id
from glyphcue.domain.review_state import ReviewState
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.jobs.job import Job, JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository
from glyphcue.persistence.repository import CueRepository
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.compact_timeline import CompactTimeline
from glyphcue.ui.design_tokens import Spacing
from glyphcue.ui.export_controls import ExportControls
from glyphcue.ui.language_selection_panel import LanguageSelectionPanel
from glyphcue.ui.ocr_evidence_pane import OcrEvidencePane
from glyphcue.ui.playback_controller import PlaybackController
from glyphcue.ui.reconstruction_qa_workspace import ReconstructionQaWorkspace
from glyphcue.ui.roi_visualization import RoiVisualization
from glyphcue.ui.video_roi_overlay import VideoRoiOverlay, VideoRoiView

_DEFAULT_TRACK_GROUP_ID = "default"


def _roi_spin_box(maximum: float = 1.0) -> QDoubleSpinBox:
    spin_box = QDoubleSpinBox()
    spin_box.setRange(0.0, maximum)
    spin_box.setSingleStep(0.01)
    spin_box.setDecimals(3)
    return spin_box


class PathAMediaPane:
    """Path A workflow inside the frozen shell.

    Local video selection, basic media metadata display, human playback
    (Play/Pause), production ROI selection/persistence via a
    TrackGroup, and (Milestone 4) selective OCR evidence extraction:
    Run OCR Evidence builds and starts a `build_ocr_evidence_job` over
    the current video/ROI, with cancellation and an embedded
    `OcrEvidencePane` for inspecting the resulting Observations.
    `ocr_engine`/`db_path` are optional so this pane still constructs
    (with OCR controls disabled) without them -- `create_path_a_app`
    wires real ones in for the production entrypoint. `db_path` (not a
    ready-made repository) lets the pane open its own connection for
    UI-thread reads, kept separate from the connection
    `build_ocr_evidence_job` opens on its own worker thread when a run
    starts. Final QA/review workspace is a later milestone (M7+).

    `ocr_engine_factory` (Milestone 6) is an optional
    `language -> OcrEngine` constructor: when present, the current
    Track Group's live language selection always constructs the real
    engine set from it. Multilingual groups run the real
    `build_multilingual_ocr_evidence_job`, then reconstructs and
    displays every language layer via `language_layers_panel` -- it
    does not silently fall back to a single engine. A single-language
    Track Group keeps using `build_ocr_evidence_job`; a plain
    `ocr_engine` remains a compatibility fallback only when no factory
    is wired.

    `language_selection_panel` (Milestone 6) is the real, user-reachable
    1..N language configuration surface (DESIGN.md section 11): a
    generic add/remove/select list, never hard-coded to "Language A" /
    "Language B", constrained to `available_languages` (defaults to
    the module-level `CANONICAL_LANGUAGES` -- the only languages the
    real production OCR runtime can actually be constructed for; never
    the old "und" placeholder, which it cannot). Saving persists both
    ROI and the selected languages together into one `TrackGroup`;
    reconstructing this pane over the same repository restores both.
    """

    def __init__(
        self,
        track_group_repository: TrackGroupRepository,
        track_group_id: str = _DEFAULT_TRACK_GROUP_ID,
        ocr_engine: OcrEngine | None = None,
        ocr_engine_factory: Callable[[str], OcrEngine] | None = None,
        db_path: Path | None = None,
        available_languages: tuple[str, ...] = CANONICAL_LANGUAGES,
        on_open_caption_file: Callable[[Path], None] | None = None,
    ) -> None:
        self._repository = track_group_repository
        self._track_group_id = track_group_id
        self._ocr_engine = ocr_engine
        self._ocr_engine_factory = ocr_engine_factory
        self._db_path = db_path
        self._on_open_caption_file = on_open_caption_file
        self._current_track_group: TrackGroup | None = None
        self._processing_range = ProcessingRange()
        self._source_id: str | None = None
        # A connection of its own on the UI thread, separate from
        # whatever connection the OCR job opens on its own worker
        # thread (build_ocr_evidence_job owns that one) -- never shared
        # across the thread boundary.
        self._db_conn = connect(db_path) if db_path is not None else None
        self._observation_repository = (
            ObservationRepository(self._db_conn) if self._db_conn is not None else None
        )
        self._cue_repository = (
            CueRepository(self._db_conn) if self._db_conn is not None else None
        )
        self._video_path: Path | None = None
        self._video_duration_seconds: float = 0.0
        self.current_ocr_job: Job | None = None
        self.current_evidence_run_id: str | None = None
        self.ocr_metrics = PipelineMetrics()

        self.controller = PlaybackController()
        self.video_widget = VideoRoiView()
        self.video_widget.setMinimumHeight(240)
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.controller.set_video_output(self.video_widget.video_item)

        self.video_overlay = self.video_widget
        self.video_widget.roiChanged.connect(self.set_roi)

        self.open_button = QPushButton("Open Video…")
        self.metadata_label = QLabel("No video loaded")
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")

        # DESIGN.md section 10 / 10.1: active ROI must be visually
        # distinguishable, not only four spin-box numbers.
        self.roi_visualization = RoiVisualization()

        # DESIGN.md section 10: PTS-aware time context + frame/time
        # navigation + current-Cue relationship. A standard QSlider is
        # the navigation control (drag or programmatic setValue both
        # seek); `current_time_label` / `current_cue_relationship_label`
        # supply the read-only context.
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.current_time_label = QLabel("0.00s")
        self.current_cue_relationship_label = QLabel("")
        self.controller.player.positionChanged.connect(self._on_playback_position_changed)
        self.position_slider.valueChanged.connect(
            lambda position_ms: self.controller.seek(position_ms / 1000.0)
        )

        # DESIGN.md section 49: a compact, read-only temporal strip --
        # Cue spans + playhead, not an NLE timeline.
        self.timeline = CompactTimeline()

        self.roi_x_spin = _roi_spin_box()
        self.roi_y_spin = _roi_spin_box()
        self.roi_width_spin = _roi_spin_box()
        self.roi_height_spin = _roi_spin_box()
        self.reset_roi_button = QPushButton("Reset to Full Frame")
        self.language_selection_panel = LanguageSelectionPanel(available_languages)
        self.save_roi_button = QPushButton("Save Track Group")

        # DESIGN.md section 84: partial-video processing is a first-
        # class Path A concept and the selected range must be visible,
        # not just implemented internally. Unchecked (the default)
        # means whole-media, matching ProcessingRange()'s own default.
        self.limit_processing_range_checkbox = QCheckBox("Limit processing range")
        self.processing_range_start_spin = _roi_spin_box(maximum=1_000_000.0)
        self.processing_range_end_spin = _roi_spin_box(maximum=1_000_000.0)
        self.processing_range_start_spin.setEnabled(False)
        self.processing_range_end_spin.setEnabled(False)
        self.limit_processing_range_checkbox.toggled.connect(
            self.processing_range_start_spin.setEnabled
        )
        self.limit_processing_range_checkbox.toggled.connect(
            self.processing_range_end_spin.setEnabled
        )

        self.run_ocr_button = QPushButton("Run OCR Evidence")
        self.cancel_ocr_button = QPushButton("Cancel")
        self.discard_latest_run_button = QPushButton("Discard Latest OCR Run")
        self.discard_latest_run_button.setEnabled(False)
        self.ocr_progress_bar = QProgressBar()
        self.ocr_progress_bar.setRange(0, 100)
        self.ocr_progress_bar.setValue(0)
        self.ocr_progress_bar.setTextVisible(True)
        self.ocr_progress_bar.setVisible(False)
        self.ocr_status_label = QLabel("OCR evidence not run yet")
        self.evidence_pane = OcrEvidencePane([])
        self._last_pre_run_cues: list[Cue] | None = None
        self._ocr_start_time: float = 0.0
        self._video_duration_seconds: float = 0.0
        self._update_ocr_button_enabled()

        self.open_button.clicked.connect(self._on_open_clicked)
        self.play_button.clicked.connect(self.controller.play)
        self.pause_button.clicked.connect(self.controller.pause)
        self.reset_roi_button.clicked.connect(self.reset_roi)
        self.save_roi_button.clicked.connect(self._on_save_roi_clicked)
        self.run_ocr_button.clicked.connect(self._on_run_ocr_clicked)
        self.cancel_ocr_button.clicked.connect(self._on_cancel_ocr_clicked)
        self.discard_latest_run_button.clicked.connect(self._on_discard_latest_run_clicked)

        self.context_label = QLabel()
        self.context_label.setWordWrap(True)

        self._restore_roi()
        self._restore_languages()

        # Structure / ROI & Track Group setup container in Left Pane
        structure_container = QWidget()
        structure_container.setObjectName("structureCard")
        structure_layout = QVBoxLayout(structure_container)
        structure_layout.setContentsMargins(
            Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD
        )

        structure_header = QLabel("STRUCTURE & REGION")
        structure_header.setObjectName("sectionHeaderLabel")
        structure_layout.addWidget(structure_header)

        roi_form = QFormLayout()
        roi_form.addRow("ROI x", self.roi_x_spin)
        roi_form.addRow("ROI y", self.roi_y_spin)
        roi_form.addRow("ROI width", self.roi_width_spin)
        roi_form.addRow("ROI height", self.roi_height_spin)
        structure_layout.addLayout(roi_form)
        structure_layout.addWidget(self.reset_roi_button)

        processing_range_form = QFormLayout()
        processing_range_form.addRow(self.limit_processing_range_checkbox)
        processing_range_form.addRow("Range start (s)", self.processing_range_start_spin)
        processing_range_form.addRow("Range end (s)", self.processing_range_end_spin)
        structure_layout.addLayout(processing_range_form)

        structure_layout.addWidget(self.language_selection_panel)
        structure_layout.addWidget(self.save_roi_button)

        # Center Pane: Primary Media & Evidence Workspace
        center_pane = QWidget()
        center_layout = QVBoxLayout(center_pane)
        center_layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        center_layout.addWidget(self.open_button)
        center_layout.addWidget(self.metadata_label)
        self.video_widget.setObjectName("videoViewport")
        center_layout.addWidget(self.video_widget, stretch=1)

        playback_controls = QHBoxLayout()
        playback_controls.addWidget(self.play_button)
        playback_controls.addWidget(self.pause_button)
        center_layout.addLayout(playback_controls)

        center_layout.addWidget(self.position_slider)
        center_layout.addWidget(self.current_time_label)
        center_layout.addWidget(self.current_cue_relationship_label)
        center_layout.addWidget(self.timeline)

        # OCR Action Pipeline Section in Center Pane (DOG-002 action hierarchy)
        ocr_container = QWidget()
        ocr_container.setObjectName("ocrActionBox")
        ocr_box_layout = QVBoxLayout(ocr_container)
        ocr_box_layout.setContentsMargins(
            Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD, Spacing.STANDARD
        )

        ocr_header = QLabel("OCR EVIDENCE PIPELINE")
        ocr_header.setObjectName("sectionHeaderLabel")
        ocr_box_layout.addWidget(ocr_header)

        ocr_controls = QHBoxLayout()
        self.run_ocr_button.setObjectName("runOcrBtn")
        self.cancel_ocr_button.setObjectName("secondaryBtn")
        self.discard_latest_run_button.setObjectName("subtleDangerBtn")
        ocr_controls.addWidget(self.run_ocr_button)
        ocr_controls.addWidget(self.cancel_ocr_button)
        ocr_controls.addWidget(self.discard_latest_run_button)
        ocr_box_layout.addLayout(ocr_controls)
        ocr_box_layout.addWidget(self.ocr_progress_bar)
        ocr_box_layout.addWidget(self.ocr_status_label)

        center_layout.addWidget(ocr_container)

        # Milestone 7: Path A follows the same shared Reconstruction QA
        # seam Path B does (DESIGN.md section 6's frozen three-pane
        # shell) -- video/ROI/config stays this pane's own CENTER
        # content, the only thing that legitimately differs per path
        # (DESIGN.md section 7.2); the queue and QA right pane are
        # identical to Path B's.
        self.qa = ReconstructionQaWorkspace(
            [],
            {},
            {},
            center_pane,
            play_pause_callback=self.controller.toggle_play_pause,
            replay_callback=self._on_replay,
            on_active_cue_changed=self._on_qa_active_cue_changed,
            on_cues_changed=self._on_qa_cues_changed,
        )
        self.window = self.qa.window

        for spin in (
            self.roi_x_spin, self.roi_y_spin, self.roi_width_spin, self.roi_height_spin,
        ):
            spin.valueChanged.connect(lambda _value: self._on_spin_roi_changed())
        self.roi_visualization.set_roi(self.current_roi())
        self._refresh_current_cue_relationship(0.0)

        # Left Pane: Top Structure Card + Queue
        self.qa.insert_left_pane_widget(0, structure_container)
        self.qa.add_left_pane_widget(self.context_label)
        self._refresh_context_label()
        for spin in (
            self.processing_range_start_spin, self.processing_range_end_spin,
        ):
            spin.valueChanged.connect(lambda _value: self._refresh_context_label())
        self.limit_processing_range_checkbox.toggled.connect(
            lambda _checked: self._refresh_context_label()
        )
        self.language_selection_panel.languagesChanged.connect(self._refresh_context_label)

        # Right Pane: Supporting Raw Evidence + Export Controls
        self.qa.add_right_pane_widget(self.evidence_pane)

        self.export_controls = ExportControls(
            get_cues=lambda: self.qa.cues,
            commit_pending_edits=self.qa.commit_pending_edits,
        )
        self.qa.add_right_pane_widget(self.export_controls.widget)

        self.open_caption_file_button = QPushButton("Open Caption File (Path B)…")
        self.open_caption_file_button.setEnabled(on_open_caption_file is not None)
        self.open_caption_file_button.clicked.connect(self._on_open_caption_file_clicked)
        self.qa.add_right_pane_widget(self.open_caption_file_button)

    def _on_replay(self, cue) -> None:
        self.controller.play_span(cue.start_time, cue.end_time)

    def commit_pending_edits(self) -> None:
        self.qa.commit_pending_edits()

    def switch_to_caption_file(self, path: Path) -> None:
        """Reaches Path B directly from an already-open Path A
        workbench (DESIGN.md section 9): switching paths is changing
        evidence-source mode inside one product, not restarting the
        app. Delegates to the shared entry (`GlyphCueEntry`) via the
        injected callback so the same window-transition logic used at
        first launch is reused, not duplicated."""
        self.commit_pending_edits()
        if self._on_open_caption_file is not None:
            self._on_open_caption_file(path)

    def _on_open_caption_file_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            None, "Open Caption File", "", "Subtitle files (*.srt *.vtt)"
        )
        if path_str:
            self.switch_to_caption_file(Path(path_str))

    def _on_qa_cues_changed(self, cues: list[Cue]) -> None:
        if self._source_id and self._cue_repository is not None:
            self._cue_repository.save_cues_for_source(self._source_id, cues)
        self._last_pre_run_cues = None
        self.discard_latest_run_button.setEnabled(False)
        self._refresh_timeline()
        self._refresh_current_cue_relationship(self.controller.player.position() / 1000.0)

    @property
    def last_reconstructed_cues(self) -> list | None:
        """The most recently reconstructed Cues, or `None` if no
        successful OCR/reconstruction run has completed yet -- kept as
        a thin compatibility view onto the shared QA workspace's own
        `cues` (`self.qa.cues`), which is the real source of truth."""
        return self.qa.cues or None

    def open_video(self, path: Path) -> None:
        self.commit_pending_edits()
        switching = self._video_path is not None and self._video_path != path
        self._video_path = path
        self._source_id = normalize_source_id(path)
        self._track_group_id = f"tg:{self._source_id}"
        self._video_duration_seconds = 0.0
        self.controller.load(path)
        metadata = probe_media(path)
        self.metadata_label.setText(
            f"{metadata.width}x{metadata.height} · "
            f"{metadata.duration_seconds:.2f}s · {metadata.codec_name}"
        )
        self.video_overlay.set_video_size(metadata.width, metadata.height)
        self.export_controls.set_source_path(path)
        # DESIGN.md section 84: the range controls must offer a
        # reasonable bound from the real, just-opened media -- not an
        # arbitrary large ceiling the user could set past the video's
        # own end.
        self.processing_range_start_spin.setRange(0.0, metadata.duration_seconds)
        self.processing_range_end_spin.setRange(0.0, metadata.duration_seconds)
        self.processing_range_end_spin.setValue(metadata.duration_seconds)

        self._restore_roi()
        self._restore_languages()
        self._last_pre_run_cues = None
        self.discard_latest_run_button.setEnabled(False)
        self.ocr_progress_bar.setVisible(False)
        self.ocr_progress_bar.setValue(0)

        if self._cue_repository is not None and self._source_id:
            persisted_cues = self._cue_repository.list_for_source(self._source_id)
            if persisted_cues:
                obs_ids: list[str] = []
                for c in persisted_cues:
                    for layer in c.language_layers:
                        obs_ids.extend(layer.observation_ids)
                obs_map = (
                    self._observation_repository.get_by_ids(obs_ids)
                    if self._observation_repository is not None
                    else {}
                )
                priorities = {
                    c.id: ReviewPriority(cue_id=c.id, score=0.0, level="None", components=())
                    for c in persisted_cues
                }
                self.qa.set_cues_and_priorities(persisted_cues, obs_map, priorities)
            else:
                self.qa.set_cues_and_priorities([], {}, {})

        self._refresh_context_label()

        # DESIGN.md section 10: PTS-aware time context/navigation and
        # the compact timeline both need a real duration to scale
        # against -- the probed value, not whatever QMediaPlayer has
        # loaded so far (which can lag behind `load()` returning).
        self._video_duration_seconds = metadata.duration_seconds
        self.position_slider.setRange(0, round(metadata.duration_seconds * 1000))
        self._refresh_timeline()
        self._refresh_current_cue_relationship(0.0)

    def current_roi(self) -> ROI:
        x = min(1.0, max(0.0, self.roi_x_spin.value()))
        y = min(1.0, max(0.0, self.roi_y_spin.value()))
        width = min(1.0 - x, max(0.001, self.roi_width_spin.value()))
        height = min(1.0 - y, max(0.001, self.roi_height_spin.value()))
        return ROI(
            x=round(x, 4),
            y=round(y, 4),
            width=round(width, 4),
            height=round(height, 4),
        )

    def set_roi(self, roi: ROI) -> None:
        """Sets the active ROI across all inputs: spinboxes, video overlay, and diagram."""
        for spin in (self.roi_x_spin, self.roi_y_spin, self.roi_width_spin, self.roi_height_spin):
            spin.blockSignals(True)
        self.roi_x_spin.setValue(roi.x)
        self.roi_y_spin.setValue(roi.y)
        self.roi_width_spin.setValue(roi.width)
        self.roi_height_spin.setValue(roi.height)
        for spin in (self.roi_x_spin, self.roi_y_spin, self.roi_width_spin, self.roi_height_spin):
            spin.blockSignals(False)
        self.video_overlay.set_roi(roi)
        self.roi_visualization.set_roi(roi)
        self._refresh_context_label()

    def reset_roi(self) -> None:
        """Resets the active ROI back to the full frame (0, 0, 1, 1)."""
        self.set_roi(ROI(0.0, 0.0, 1.0, 1.0))

    def _on_spin_roi_changed(self) -> None:
        roi = self.current_roi()
        self.video_overlay.set_roi(roi)
        self.roi_visualization.set_roi(roi)
        self._refresh_context_label()

    def _on_playback_position_changed(self, position_ms: int) -> None:
        position_seconds = position_ms / 1000.0
        self.current_time_label.setText(f"{position_seconds:.2f}s")
        # Programmatic (playback-driven) updates must not re-trigger a
        # seek through the slider's own valueChanged -> controller.seek
        # wiring -- that wiring exists for user-driven navigation.
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position_ms)
        self.position_slider.blockSignals(False)
        self.timeline.playhead_seconds = position_seconds
        self.timeline.update()
        self._refresh_current_cue_relationship(position_seconds)

    def _on_qa_active_cue_changed(self, _cue) -> None:
        # The shared QA workspace's active-Cue-changed callback also
        # fires while `ReconstructionQaWorkspace.__init__` itself is
        # still running (its own initial `_rebuild_queue` call) --
        # before `self.qa` has been assigned here. Nothing to refresh
        # yet in that case (cues start empty regardless).
        if not hasattr(self, "qa"):
            return
        # Also fires right after a fresh reconstruction result is
        # loaded (`set_cues_and_priorities` selects a first row) --
        # reused here as the trigger to refresh the WHOLE timeline
        # (every Cue's span), not just the active one.
        self._refresh_timeline()

    def _refresh_timeline(self) -> None:
        spans = []
        for cue in self.qa.cues:
            priority = self.qa.priority_for_cue_id(cue.id)
            role = "flagged" if priority.level != "None" else "clean"
            spans.append((cue.start_time, cue.end_time, role))
        self.timeline.set_data(
            self._video_duration_seconds, spans, playhead_seconds=self.controller.position_seconds
        )

    def _refresh_current_cue_relationship(self, position_seconds: float | None = None) -> None:
        if position_seconds is None:
            position_seconds = self.controller.position_seconds
        matching = next(
            (cue for cue in self.qa.cues if cue.start_time <= position_seconds <= cue.end_time),
            None,
        )
        self.qa.set_playback_active_cue_id(matching.id if matching is not None else None)
        if matching is None:
            self.current_cue_relationship_label.setText(
                f"{position_seconds:.2f}s — No Cue at current time"
            )
        else:
            priority = self.qa.priority_for_cue_id(matching.id)
            self.current_cue_relationship_label.setText(
                f"{position_seconds:.2f}s — Cue {matching.id} (Review Priority: {priority.level})"
            )

    def _refresh_context_label(self) -> None:
        video = self._video_path.name if self._video_path is not None else "No video loaded"
        roi = self.current_roi()
        languages = self.language_selection_panel.selected_languages()
        if self.limit_processing_range_checkbox.isChecked():
            range_text = (
                f"{self.processing_range_start_spin.value():.2f}s"
                f" – {self.processing_range_end_spin.value():.2f}s"
            )
        else:
            range_text = "Whole media"
        self.context_label.setText(
            f"{video}\n"
            f"ROI: x={roi.x:.2f} y={roi.y:.2f} w={roi.width:.2f} h={roi.height:.2f}\n"
            f"Languages: {', '.join(languages) if languages else '—'}\n"
            f"Processing range: {range_text}"
        )

    def current_processing_range(self) -> ProcessingRange:
        """The live processing-range selection -- "what you see is what
        runs", the same contract `current_roi()` already has. Unchecked
        means whole-media, never a stale value left over from a
        previous video."""
        if not self.limit_processing_range_checkbox.isChecked():
            return ProcessingRange()
        return ProcessingRange(
            start_time=self.processing_range_start_spin.value(),
            end_time=self.processing_range_end_spin.value(),
        )

    def _restore_roi(self) -> None:
        track_group = self._repository.get(self._track_group_id)
        if track_group is not None:
            self.set_roi(track_group.roi)
        else:
            self.reset_roi()

    def _restore_languages(self) -> None:
        track_group = self._repository.get(self._track_group_id)
        if track_group is not None:
            clean_languages = tuple(lang for lang in track_group.languages if lang != "und")
            self.language_selection_panel.set_languages(clean_languages or ("en",))
        else:
            self.language_selection_panel.set_languages(("en",))

    def _on_save_roi_clicked(self) -> None:
        track_group = TrackGroup(
            id=self._track_group_id,
            roi=self.current_roi(),
            languages=self.language_selection_panel.selected_languages(),
        )
        self._repository.save(track_group)
        self._refresh_context_label()

    def _on_open_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            None, "Open Video", "", "Video files (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if path_str:
            self.open_video(Path(path_str))

    def _update_ocr_button_enabled(self) -> None:
        wired = (
            self._ocr_engine is not None or self._ocr_engine_factory is not None
        ) and self._db_path is not None
        self.run_ocr_button.setEnabled(wired)
        self.cancel_ocr_button.setEnabled(False)

    def _on_run_ocr_clicked(self) -> None:
        if self._video_path is None or self._db_path is None:
            return
        if self._ocr_engine is None and self._ocr_engine_factory is None:
            return

        # The live language selection is what actually runs -- the same
        # "what you see is what runs" contract `current_roi()` already
        # has, rather than requiring an explicit prior Save first.
        languages = self.language_selection_panel.selected_languages()
        track_group = TrackGroup(id=self._track_group_id, roi=self.current_roi(), languages=languages)
        self._current_track_group = track_group

        self._processing_range = self.current_processing_range()

        # Real, resolved processing-end evidence -- the SAME
        # ProcessingRange the job itself is about to run with -- so the
        # final reconstructed Cue can use it instead of an ~1ms
        # OCR-instant-marker fallback (ROADMAP M5's frozen final-
        # boundary contract; see reconstruct_multilingual_cues_for_track_group).
        #
        # Resolved and validated BEFORE any job/run-state is touched
        # (ROADMAP M9): a reversed/zero/out-of-media range must never
        # start a job or overwrite the previous run's status with a
        # fake "running" state -- it is refused up front, with the
        # current OCR status left exactly as it was.
        media_duration = probe_media(self._video_path).duration_seconds
        try:
            _range_start, processing_end_time = self._processing_range.resolve(media_duration)
        except ValueError as exc:
            self.ocr_status_label.setText(f"Invalid processing range: {exc}")
            return
        self._current_processing_end_time = processing_end_time

        self.ocr_metrics = PipelineMetrics()
        self.current_evidence_run_id = str(uuid.uuid4())

        if len(languages) == 1:
            # The live language selection must choose the real runtime
            # whenever a factory is available. A plain engine remains
            # only as the M4/M5 injection compatibility fallback.
            engine = (
                self._ocr_engine_factory(languages[0])
                if self._ocr_engine_factory is not None
                else self._ocr_engine
            )
            self.current_ocr_job = build_ocr_evidence_job(
                self._video_path,
                self._processing_range,
                track_group.roi,
                engine,
                self._db_path,
                self.ocr_metrics,
                self.current_evidence_run_id,
            )
        else:
            # Milestone 6: the Track Group's own configured languages
            # decide the real engine set -- one per language, never a
            # single engine reinterpreted after the fact.
            if self._ocr_engine_factory is None:
                self.ocr_status_label.setText(
                    "Multilingual Track Group needs an OCR engine per language "
                    "(no ocr_engine_factory wired)"
                )
                return
            engines = {language: self._ocr_engine_factory(language) for language in languages}
            self.current_ocr_job = build_multilingual_ocr_evidence_job(
                self._video_path,
                self._processing_range,
                track_group,
                engines,
                self._db_path,
                self.ocr_metrics,
                self.current_evidence_run_id,
            )

        self.current_ocr_job.progress.connect(self._on_ocr_progress)
        self.current_ocr_job.finished.connect(self._on_ocr_finished)
        if self._source_id and self._cue_repository is not None:
            self._last_pre_run_cues = list(self._cue_repository.list_for_source(self._source_id))
        else:
            self._last_pre_run_cues = list(self.qa.cues)
        self._ocr_start_time = time.monotonic()
        self.ocr_progress_bar.setVisible(True)
        self.ocr_progress_bar.setValue(0)
        self.discard_latest_run_button.setEnabled(False)
        self.run_ocr_button.setEnabled(False)
        self.cancel_ocr_button.setEnabled(True)
        self.ocr_status_label.setText("Running OCR evidence extraction…")
        self.current_ocr_job.start()

    def _on_cancel_ocr_clicked(self) -> None:
        if self.current_ocr_job is not None:
            self.current_ocr_job.request_cancel()

    def _on_ocr_progress(self, phase: str, processed_seconds: float, total_seconds: float) -> None:
        elapsed = time.monotonic() - self._ocr_start_time
        pct = int(processed_seconds / total_seconds * 100) if total_seconds > 0 else 0
        self.ocr_progress_bar.setValue(min(100, max(0, pct)))
        self.ocr_status_label.setText(
            f"Running OCR ({phase}): {processed_seconds:.1f}s / {total_seconds:.1f}s · "
            f"{self.ocr_metrics.ocr_calls} OCR calls · Elapsed: {elapsed:.1f}s"
        )

    def _on_ocr_finished(self) -> None:
        self.run_ocr_button.setEnabled(True)
        self.cancel_ocr_button.setEnabled(False)

        state = self.current_ocr_job.state if self.current_ocr_job is not None else None
        elapsed = max(0.001, time.monotonic() - self._ocr_start_time)
        observations_for_run: list = []
        if self._observation_repository is not None and self.current_evidence_run_id is not None:
            # Only this run's own evidence -- never database history
            # from a different video or an earlier re-run.
            observations_for_run = self._observation_repository.list_for_run(
                self.current_evidence_run_id
            )
            self.evidence_pane.set_observations(observations_for_run)

        # Milestone 7: reconstruct real Cues from this run's evidence
        # (single- or multi-language, using M5's/M6's own reconstruction
        # seams unchanged) and hand them to the shared QA workspace with
        # a real, explainable Review Priority per Cue -- not just a
        # language-layer preview (that was M6's thinner wiring).
        new_cues_count = 0
        if state is JobState.SUCCEEDED and self._current_track_group is not None:
            observations_by_id = {observation.id: observation for observation in observations_for_run}
            new_cues: list[Cue] = []
            priorities: dict[str, ReviewPriority] = {}
            if observations_for_run:
                if len(self._current_track_group.languages) > 1:
                    new_cues, diagnostics_list = reconstruct_multilingual_cues_for_track_group(
                        observations_for_run,
                        self._current_track_group,
                        processing_end_time=self._current_processing_end_time,
                    )
                    signal_builder = review_signals_from_multilingual_diagnostics
                else:
                    new_cues, diagnostics_list = reconstruct_cues_with_consensus(
                        observations_for_run,
                        processing_end_time=self._current_processing_end_time,
                    )
                    signal_builder = review_signals_from_consensus_diagnostics

                for cue, diagnostics in zip(new_cues, diagnostics_list):
                    cue_observations = [
                        observations_by_id[observation_id]
                        for layer in cue.language_layers
                        for observation_id in layer.observation_ids
                        if observation_id in observations_by_id
                    ]
                    priorities[cue.id] = compute_review_priority(
                        signal_builder(diagnostics, cue_observations)
                    )
            new_cues_count = len(new_cues)

            if self._source_id and self._cue_repository is not None:
                existing_cues = self._cue_repository.list_for_source(self._source_id)
                range_start = self._processing_range.start_time or 0.0
                range_end = self._current_processing_end_time or (
                    self._processing_range.end_time or 999999.0
                )
                merged_cues = merge_incremental_cues(existing_cues, new_cues, range_start, range_end)
                self._cue_repository.save_cues_for_source(self._source_id, merged_cues)
                cues = merged_cues
            else:
                cues = new_cues

            if self._source_id and self._repository is not None:
                self._repository.save(
                    TrackGroup(
                        id=self._track_group_id,
                        roi=self.current_roi(),
                        languages=self.language_selection_panel.selected_languages(),
                    )
                )

            if self._observation_repository is not None:
                all_obs_ids = [
                    obs_id
                    for c in cues
                    for layer in c.language_layers
                    for obs_id in layer.observation_ids
                ]
                all_obs = self._observation_repository.get_by_ids(all_obs_ids)
                observations_by_id.update(all_obs)

            for c in cues:
                if c.id not in priorities:
                    priorities[c.id] = ReviewPriority(cue_id=c.id, score=0.0, level="None", components=())

            self.qa.set_cues_and_priorities(cues, observations_by_id, priorities)
            self._refresh_timeline()
            self.discard_latest_run_button.setEnabled(self._last_pre_run_cues is not None)

        frames = self.ocr_metrics.frames_analyzed
        calls = self.ocr_metrics.ocr_calls
        observations = self.ocr_metrics.observations_created
        if state is JobState.SUCCEEDED:
            self.ocr_progress_bar.setValue(100)
            range_start = self._processing_range.start_time or 0.0
            range_end = self._current_processing_end_time or (
                self._processing_range.end_time or self._video_duration_seconds or 0.0
            )
            media_duration = max(0.0, range_end - range_start)
            if media_duration == 0.0 and self._video_duration_seconds:
                media_duration = self._video_duration_seconds
            speed_ratio = media_duration / elapsed if elapsed > 0 else 0.0
            self.ocr_status_label.setText(
                f"Done: {media_duration:.2f}s media in {elapsed:.2f}s ({speed_ratio:.2f}x realtime) · "
                f"{frames} frames analyzed · {calls} OCR calls · {observations} observations · "
                f"{new_cues_count} new cues"
            )
        elif state is JobState.CANCELLED:
            self.discard_latest_run_button.setEnabled(False)
            self.ocr_status_label.setText(
                f"Cancelled: kept {observations} observations from {frames} frames analyzed "
                f"before cancellation ({calls} OCR calls) in {elapsed:.2f}s"
            )
        elif state is JobState.FAILED:
            self.discard_latest_run_button.setEnabled(False)
            self.ocr_status_label.setText(
                f"Failed: OCR evidence job failed after {elapsed:.2f}s ({frames} frames analyzed, "
                f"{calls} OCR calls, {observations} observations kept)"
            )
        else:  # pragma: no cover - defensive, Job always reaches a terminal state
            self.discard_latest_run_button.setEnabled(False)
            self.ocr_status_label.setText("OCR evidence job ended in an unexpected state")

    def _on_discard_latest_run_clicked(self) -> None:
        if self._last_pre_run_cues is None or not self._source_id:
            return
        restored_cues = list(self._last_pre_run_cues)
        if self._cue_repository is not None:
            self._cue_repository.save_cues_for_source(self._source_id, restored_cues)

        obs_ids = [
            obs_id
            for c in restored_cues
            for layer in c.language_layers
            for obs_id in layer.observation_ids
        ]
        obs_map = (
            self._observation_repository.get_by_ids(obs_ids)
            if self._observation_repository is not None
            else {}
        )
        priorities = {
            c.id: ReviewPriority(cue_id=c.id, score=0.0, level="None", components=())
            for c in restored_cues
        }
        self.qa.set_cues_and_priorities(restored_cues, obs_map, priorities)
        self.evidence_pane.set_observations([])
        self._refresh_timeline()
        self._last_pre_run_cues = None
        self.discard_latest_run_button.setEnabled(False)
        self.ocr_status_label.setText("Latest OCR run discarded; workspace restored.")
