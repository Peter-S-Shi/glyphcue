from __future__ import annotations

import time
import uuid
from pathlib import Path

from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.ocr_invocation_policy import (
    ChangeTriggeredOcrPolicy,
    OcrInvocationPolicy,
)
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.jobs.job import Job, JobContext
from glyphcue.persistence.observation_repository import ObservationRepository

_INSTANT_SPAN_SECONDS = 0.001
"""An OCR observation is a point-in-time sample, not a duration claim --
Observation requires end_time > start_time, so this is a small fixed
span marking "this is an instant," not a measured/estimated duration.
Real duration/spanning across neighboring observations is Milestone 5's
job (multi-frame consensus / Cue reconstruction), not this one's."""


def build_ocr_evidence_job(
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    ocr_engine: OcrEngine,
    observation_repository: ObservationRepository,
    metrics: PipelineMetrics,
    *,
    policy: OcrInvocationPolicy | None = None,
) -> Job:
    """Cancelable background job implementing ROADMAP Milestone 4's
    target flow:

        ROI frame stream -> cheap change analysis -> candidate states
        -> selective OCR -> Observation

    Reuses the Milestone 2 media/job foundation exactly like
    `build_media_analysis_job`: owns the PyAvMediaFrameSource lifecycle
    inside `work`, polls cancellation each iteration, reports progress.
    Persists each Observation as soon as it is produced, so a
    cancel/failure partway through the run still keeps whatever evidence
    was already found (ROADMAP M4: "partial working state where
    appropriate"). `metrics` is filled in as the job actually runs (the
    same passed-in-mutable-object pattern `JobContext` uses for
    cancellation) so its counts are read from the real execution path,
    never estimated.

    `policy` defaults to `ChangeTriggeredOcrPolicy()` -- the selective,
    production behavior. Passing `NaiveDenseOcrPolicy()` is supported
    only to produce a dense-OCR comparison baseline (ROADMAP M4
    acceptance gate 3), never as a production default.
    """
    active_policy = policy if policy is not None else ChangeTriggeredOcrPolicy()

    def work(context: JobContext) -> None:
        wall_start = time.monotonic()
        metadata = probe_media(path)
        start, end = processing_range.resolve(metadata.duration_seconds)

        ocr_engine.initialize()
        source = PyAvMediaFrameSource()
        source.open(path)
        try:
            for timestamp, frame in source.frames(start, end):
                if context.is_cancel_requested():
                    return
                metrics.frames_analyzed += 1
                roi_frame = crop_to_roi(frame, roi)

                if active_policy.should_ocr(roi_frame, timestamp):
                    metrics.ocr_calls += 1
                    regions = ocr_engine.recognize(roi_frame)
                    runtime_info = ocr_engine.runtime_info()
                    for region in regions:
                        if not region.text:
                            continue
                        observation = Observation(
                            id=str(uuid.uuid4()),
                            text=region.text,
                            start_time=timestamp,
                            end_time=timestamp + _INSTANT_SPAN_SECONDS,
                            provenance=Provenance(
                                kind=ProvenanceKind.OCR_ENGINE,
                                source=runtime_info.engine_name,
                                detail={
                                    "engine_version": runtime_info.version,
                                    "backend": runtime_info.backend,
                                    "backend_version": runtime_info.backend_version or "",
                                },
                            ),
                            language=region.language,
                            confidence=region.confidence,
                            roi=roi,
                            geometry=region.geometry,
                            frame_reference=f"{path}@{timestamp:.6f}s",
                        )
                        observation_repository.add(observation)
                        metrics.observations_created += 1

                metrics.media_seconds_processed = timestamp
                metrics.elapsed_seconds = time.monotonic() - wall_start
                context.report_progress("ocr_evidence", timestamp, metadata.duration_seconds)
        finally:
            source.close()
            ocr_engine.shutdown()
            metrics.elapsed_seconds = time.monotonic() - wall_start

    return Job(work=work)
