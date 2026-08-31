from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.paddleocr_engine import CANONICAL_LANGUAGES
from glyphcue.adapters.pyav_media_source import probe_media
from glyphcue.application.multilingual_ocr_evidence_job import build_multilingual_ocr_evidence_job
from glyphcue.application.multilingual_reconstruction import (
    reconstruct_multilingual_cues_for_track_group,
)
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.cue import Cue
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.jobs.job import Job, JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.design_tokens import Spacing
from glyphcue.ui.language_layer_presentation import LanguageLayersPanel
from glyphcue.ui.language_selection_panel import LanguageSelectionPanel
from glyphcue.ui.main_window import MainWindow
from glyphcue.ui.ocr_evidence_pane import OcrEvidencePane
from glyphcue.ui.playback_controller import PlaybackController

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
    `language -> OcrEngine` constructor: when the current Track Group
    has more than one configured language, this pane actually builds
    one engine per language and runs the real
    `build_multilingual_ocr_evidence_job`, then reconstructs and
    displays every language layer via `language_layers_panel` -- it
    does not silently fall back to a single engine. A single-language
    Track Group keeps using the plain `ocr_engine` (if given) or
    `ocr_engine_factory(language)`, and `build_ocr_evidence_job`
    exactly as before M6 -- unchanged M4/M5 behavior, not a
    reimplementation of it.

    `language_selection_panel` (Milestone 6) is the real, user-reachable
    1..N language configuration surface (DESIGN.md section 11): a
    generic add/remove/select list, never hard-coded to "Language A" /
    "Language B", constrained to `available_languages` (defaults to
    `PaddleOcrEngine.CANONICAL_LANGUAGES` -- the only languages the
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
    ) -> None:
        self._repository = track_group_repository
        self._track_group_id = track_group_id
        self._ocr_engine = ocr_engine
        self._ocr_engine_factory = ocr_engine_factory
        self._db_path = db_path
        self._current_track_group: TrackGroup | None = None
        self._processing_range = ProcessingRange()
        self.last_reconstructed_cues: list[Cue] | None = None
        # A connection of its own on the UI thread, separate from
        # whatever connection the OCR job opens on its own worker
        # thread (build_ocr_evidence_job owns that one) -- never shared
        # across the thread boundary.
        self._observation_repository = (
            ObservationRepository(connect(db_path)) if db_path is not None else None
        )
        self._video_path: Path | None = None
        self.current_ocr_job: Job | None = None
        self.current_evidence_run_id: str | None = None
        self.ocr_metrics = PipelineMetrics()

        self.controller = PlaybackController()
        self.video_widget = QVideoWidget()
        self.controller.set_video_output(self.video_widget)

        self.open_button = QPushButton("Open Video…")
        self.metadata_label = QLabel("No video loaded")
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")

        self.roi_x_spin = _roi_spin_box()
        self.roi_y_spin = _roi_spin_box()
        self.roi_width_spin = _roi_spin_box()
        self.roi_height_spin = _roi_spin_box()
        self.language_selection_panel = LanguageSelectionPanel(available_languages)
        self.save_roi_button = QPushButton("Save Track Group")

        self.run_ocr_button = QPushButton("Run OCR Evidence")
        self.cancel_ocr_button = QPushButton("Cancel")
        self.ocr_status_label = QLabel("OCR evidence not run yet")
        self.evidence_pane = OcrEvidencePane([])
        self.language_layers_panel = LanguageLayersPanel()
        self._update_ocr_button_enabled()

        self.open_button.clicked.connect(self._on_open_clicked)
        self.play_button.clicked.connect(self.controller.play)
        self.pause_button.clicked.connect(self.controller.pause)
        self.save_roi_button.clicked.connect(self._on_save_roi_clicked)
        self.run_ocr_button.clicked.connect(self._on_run_ocr_clicked)
        self.cancel_ocr_button.clicked.connect(self._on_cancel_ocr_clicked)

        self._restore_roi()
        self._restore_languages()

        center_pane = QWidget()
        layout = QVBoxLayout(center_pane)
        layout.setContentsMargins(
            Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR, Spacing.PANEL_MAJOR
        )
        layout.addWidget(self.open_button)
        layout.addWidget(self.metadata_label)
        layout.addWidget(self.video_widget)

        playback_controls = QHBoxLayout()
        playback_controls.addWidget(self.play_button)
        playback_controls.addWidget(self.pause_button)
        layout.addLayout(playback_controls)

        roi_form = QFormLayout()
        roi_form.addRow("ROI x", self.roi_x_spin)
        roi_form.addRow("ROI y", self.roi_y_spin)
        roi_form.addRow("ROI width", self.roi_width_spin)
        roi_form.addRow("ROI height", self.roi_height_spin)
        layout.addLayout(roi_form)
        layout.addWidget(self.language_selection_panel)
        layout.addWidget(self.save_roi_button)

        ocr_controls = QHBoxLayout()
        ocr_controls.addWidget(self.run_ocr_button)
        ocr_controls.addWidget(self.cancel_ocr_button)
        layout.addLayout(ocr_controls)
        layout.addWidget(self.ocr_status_label)
        layout.addWidget(self.evidence_pane)
        layout.addWidget(self.language_layers_panel)

        self.window = MainWindow(center_pane=center_pane)

    def open_video(self, path: Path) -> None:
        self._video_path = path
        self.controller.load(path)
        metadata = probe_media(path)
        self.metadata_label.setText(
            f"{metadata.width}x{metadata.height} · "
            f"{metadata.duration_seconds:.2f}s · {metadata.codec_name}"
        )

    def current_roi(self) -> ROI:
        return ROI(
            x=self.roi_x_spin.value(),
            y=self.roi_y_spin.value(),
            width=self.roi_width_spin.value(),
            height=self.roi_height_spin.value(),
        )

    def _restore_roi(self) -> None:
        track_group = self._repository.get(self._track_group_id)
        roi = track_group.roi if track_group is not None else ROI(0.0, 0.0, 1.0, 1.0)
        self.roi_x_spin.setValue(roi.x)
        self.roi_y_spin.setValue(roi.y)
        self.roi_width_spin.setValue(roi.width)
        self.roi_height_spin.setValue(roi.height)

    def _restore_languages(self) -> None:
        track_group = self._repository.get(self._track_group_id)
        if track_group is not None:
            self.language_selection_panel.set_languages(track_group.languages)

    def _on_save_roi_clicked(self) -> None:
        track_group = TrackGroup(
            id=self._track_group_id,
            roi=self.current_roi(),
            languages=self.language_selection_panel.selected_languages(),
        )
        self._repository.save(track_group)

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

        self.ocr_metrics = PipelineMetrics()
        self.current_evidence_run_id = str(uuid.uuid4())

        # Real, resolved processing-end evidence -- the SAME
        # ProcessingRange the job itself is about to run with -- so the
        # final reconstructed Cue can use it instead of an ~1ms
        # OCR-instant-marker fallback (ROADMAP M5's frozen final-
        # boundary contract; see reconstruct_multilingual_cues_for_track_group).
        media_duration = probe_media(self._video_path).duration_seconds
        _range_start, self._current_processing_end_time = self._processing_range.resolve(
            media_duration
        )

        if len(languages) == 1:
            # Unchanged M4/M5 single-engine path: a plain `ocr_engine`
            # takes precedence when given (existing callers/tests), the
            # factory is only used when that's all that's wired.
            engine = self._ocr_engine if self._ocr_engine is not None else self._ocr_engine_factory(
                languages[0]
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
        self.run_ocr_button.setEnabled(False)
        self.cancel_ocr_button.setEnabled(True)
        self.ocr_status_label.setText("Running OCR evidence extraction…")
        self.current_ocr_job.start()

    def _on_cancel_ocr_clicked(self) -> None:
        if self.current_ocr_job is not None:
            self.current_ocr_job.request_cancel()

    def _on_ocr_progress(self, phase: str, processed_seconds: float, total_seconds: float) -> None:
        self.ocr_status_label.setText(
            f"{phase}: {processed_seconds:.1f}s / {total_seconds:.1f}s · "
            f"{self.ocr_metrics.ocr_calls} OCR calls"
        )

    def _on_ocr_finished(self) -> None:
        self.run_ocr_button.setEnabled(True)
        self.cancel_ocr_button.setEnabled(False)

        state = self.current_ocr_job.state if self.current_ocr_job is not None else None
        observations_for_run: list = []
        if self._observation_repository is not None and self.current_evidence_run_id is not None:
            # Only this run's own evidence -- never database history
            # from a different video or an earlier re-run.
            observations_for_run = self._observation_repository.list_for_run(
                self.current_evidence_run_id
            )
            self.evidence_pane.set_observations(observations_for_run)

        # Milestone 6: for a multilingual Track Group, reconstruct and
        # show every language layer on this Path A surface -- the
        # thinnest wiring that makes "configure N languages, see N
        # layers" actually reachable, not a full QA workspace (M7).
        self.language_layers_panel.set_cue(None)
        self.last_reconstructed_cues = None
        if (
            state is JobState.SUCCEEDED
            and self._current_track_group is not None
            and len(self._current_track_group.languages) > 1
            and observations_for_run
        ):
            cues, _diagnostics = reconstruct_multilingual_cues_for_track_group(
                observations_for_run,
                self._current_track_group,
                processing_end_time=self._current_processing_end_time,
            )
            self.last_reconstructed_cues = cues
            if cues:
                self.language_layers_panel.set_cue(cues[0])

        frames = self.ocr_metrics.frames_analyzed
        calls = self.ocr_metrics.ocr_calls
        observations = self.ocr_metrics.observations_created
        if state is JobState.SUCCEEDED:
            self.ocr_status_label.setText(
                f"Done: {frames} frames analyzed, {calls} OCR calls, {observations} observations"
            )
        elif state is JobState.CANCELLED:
            self.ocr_status_label.setText(
                f"Cancelled: kept {observations} observations from {frames} frames analyzed "
                f"before cancellation, {calls} OCR calls (partial)"
            )
        elif state is JobState.FAILED:
            self.ocr_status_label.setText(
                f"Failed: OCR evidence job failed after {frames} frames analyzed, "
                f"{calls} OCR calls, {observations} observations kept (partial)"
            )
        else:  # pragma: no cover - defensive, Job always reaches a terminal state
            self.ocr_status_label.setText("OCR evidence job ended in an unexpected state")
