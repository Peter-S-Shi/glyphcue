from __future__ import annotations

from pathlib import Path

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
from glyphcue.adapters.pyav_media_source import probe_media
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.jobs.job import Job
from glyphcue.persistence.observation_repository import ObservationRepository
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.design_tokens import Spacing
from glyphcue.ui.main_window import MainWindow
from glyphcue.ui.ocr_evidence_pane import OcrEvidencePane
from glyphcue.ui.playback_controller import PlaybackController

_DEFAULT_TRACK_GROUP_ID = "default"
_DEFAULT_LANGUAGE = "und"


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
    `ocr_engine`/`observation_repository` are optional so this pane
    still constructs (with OCR controls disabled) without them --
    `create_path_a_app` wires real ones in for the production
    entrypoint. Final QA/review workspace is a later milestone (M5+).
    """

    def __init__(
        self,
        track_group_repository: TrackGroupRepository,
        track_group_id: str = _DEFAULT_TRACK_GROUP_ID,
        ocr_engine: OcrEngine | None = None,
        observation_repository: ObservationRepository | None = None,
    ) -> None:
        self._repository = track_group_repository
        self._track_group_id = track_group_id
        self._ocr_engine = ocr_engine
        self._observation_repository = observation_repository
        self._video_path: Path | None = None
        self.current_ocr_job: Job | None = None
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
        self.save_roi_button = QPushButton("Save ROI")

        self.run_ocr_button = QPushButton("Run OCR Evidence")
        self.cancel_ocr_button = QPushButton("Cancel")
        self.ocr_status_label = QLabel("OCR evidence not run yet")
        self.evidence_pane = OcrEvidencePane([])
        self._update_ocr_button_enabled()

        self.open_button.clicked.connect(self._on_open_clicked)
        self.play_button.clicked.connect(self.controller.play)
        self.pause_button.clicked.connect(self.controller.pause)
        self.save_roi_button.clicked.connect(self._on_save_roi_clicked)
        self.run_ocr_button.clicked.connect(self._on_run_ocr_clicked)
        self.cancel_ocr_button.clicked.connect(self._on_cancel_ocr_clicked)

        self._restore_roi()

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
        layout.addWidget(self.save_roi_button)

        ocr_controls = QHBoxLayout()
        ocr_controls.addWidget(self.run_ocr_button)
        ocr_controls.addWidget(self.cancel_ocr_button)
        layout.addLayout(ocr_controls)
        layout.addWidget(self.ocr_status_label)
        layout.addWidget(self.evidence_pane)

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

    def _on_save_roi_clicked(self) -> None:
        existing = self._repository.get(self._track_group_id)
        languages = existing.languages if existing is not None else (_DEFAULT_LANGUAGE,)
        track_group = TrackGroup(
            id=self._track_group_id, roi=self.current_roi(), languages=languages
        )
        self._repository.save(track_group)

    def _on_open_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(
            None, "Open Video", "", "Video files (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if path_str:
            self.open_video(Path(path_str))

    def _update_ocr_button_enabled(self) -> None:
        wired = self._ocr_engine is not None and self._observation_repository is not None
        self.run_ocr_button.setEnabled(wired)
        self.cancel_ocr_button.setEnabled(False)

    def _on_run_ocr_clicked(self) -> None:
        if (
            self._video_path is None
            or self._ocr_engine is None
            or self._observation_repository is None
        ):
            return
        self.ocr_metrics = PipelineMetrics()
        self.current_ocr_job = build_ocr_evidence_job(
            self._video_path,
            ProcessingRange(),
            self.current_roi(),
            self._ocr_engine,
            self._observation_repository,
            self.ocr_metrics,
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
        if self._observation_repository is not None:
            self.evidence_pane.set_observations(self._observation_repository.list_all())
        self.ocr_status_label.setText(
            f"Done: {self.ocr_metrics.frames_analyzed} frames analyzed, "
            f"{self.ocr_metrics.ocr_calls} OCR calls, "
            f"{self.ocr_metrics.observations_created} observations"
        )
