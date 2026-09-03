from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable

import numpy as np

from glyphcue.adapters.ocr_engine import OcrEngine, RegionOcrEngine
from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.ocr_evidence_job import STATE_TRIGGER_DETAIL_KEY, INSTANT_SPAN_SECONDS
from glyphcue.application.ocr_invocation_policy import (
    ChangeTriggeredOcrPolicy,
    OcrInvocationPolicy,
)
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.application.source_identity import normalize_source_id
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.track_group import TrackGroup
from glyphcue.jobs.job import Job, JobContext
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository


TextDetector = Callable[[np.ndarray], Any]


def build_multilingual_ocr_evidence_job(
    path: Path,
    processing_range: ProcessingRange,
    track_group: TrackGroup,
    ocr_engine: OcrEngine,
    db_path: Path,
    metrics: PipelineMetrics,
    evidence_run_id: str,
    *,
    detect: TextDetector,
    policy: OcrInvocationPolicy | None = None,
) -> Job:
    """Milestone 11 Architecture B: the M4 job architecture
    (`ocr_evidence_job.build_ocr_evidence_job`) extended for genuinely
    multilingual evidence via ONE shared detector plus ONE universal
    recognizer per triggered frame -- not, as Milestone 6's original
    design had it, one full detect+recognize call per Track Group
    language.

    Milestone 6's own real multi-engine verification
    (`benchmarks/multilingual_reconstruction/`, see
    docs/multilingual/track_group_reconstruction.md's "Evidence
    hygiene") found that every `PaddleOcrEngine` instance already
    detects and transcribes EVERY text region in the frame regardless of
    which language it was constructed for -- the "engine per language"
    design was paying for N full detection+recognition passes over
    IDENTICAL frame content to get N engines' opinions on the same
    regions, when only the RECOGNITION step's underlying model varies at
    all by configured language (and P2/P3's own `RegionOcrEngine` work
    showed even that isn't true: `PaddleOcrEngine`/`DirectMlOcrEngine`'s
    recognizer is the same multi-script-capable model regardless of the
    `language=` an instance happens to be labeled with).

    `detect` runs ONCE per triggered frame, producing this frame's
    ordered polygons; `ocr_engine` (typically constructed via
    `glyphcue.adapters.ocr_engine_selection.create_ocr_engine` --
    Windows DirectML opt-in with the same real preflight/fallback to
    PaddleOcrEngine as the Hybrid P2/P3 path, never a silent behavior
    change to the default) then runs its `recognize_regions` (or plain
    `recognize`, for a caller-supplied `OcrEngine` that doesn't implement
    `RegionOcrEngine`) exactly ONCE against those polygons -- one
    detect + one recognize per triggered frame, full stop, regardless of
    how many languages `track_group` expects.

    Every returned region is persisted as its own Observation, tagged
    with `ocr_engine`'s own `language` label as a real-but-not-fully-
    trustworthy hint (unchanged from Milestone 6 -- see
    `assign_observations_to_languages`'s docstring for why the actual
    per-language split happens downstream from real script content, not
    from this tag). A triggered frame with zero detected regions still
    gets a single blank-candidate marker Observation (M4's "OCR-empty is
    candidate evidence, not silence" rule -- see `ocr_evidence_job.py`),
    so an empty frame is real recorded evidence, not an absence
    indistinguishable from "this frame was never processed."

    `metrics.ocr_calls` counts real recognition invocations -- one per
    triggered frame, regardless of `track_group.languages`' length; a
    2-language and a 4-language Track Group cost the same one call per
    frame (ROADMAP: "metrics must come from a real execution path, no
    fake telemetry").
    """
    active_policy = policy if policy is not None else ChangeTriggeredOcrPolicy()

    def work(context: JobContext) -> None:
        wall_start = time.monotonic()
        metadata = probe_media(path)
        range_start, range_end = processing_range.resolve(metadata.duration_seconds)
        range_duration = range_end - range_start

        engine_initialized = False
        conn = None
        source = None
        try:
            init_start = time.monotonic()
            ocr_engine.initialize()
            engine_initialized = True
            metrics.engine_initialization_seconds = time.monotonic() - init_start

            conn = connect(db_path)
            observation_repository = ObservationRepository(conn)

            source = PyAvMediaFrameSource()
            source.open(path)

            for timestamp, frame in source.frames(range_start, range_end):
                if context.is_cancel_requested():
                    return
                metrics.frames_analyzed += 1
                roi_frame = crop_to_roi(frame, track_group.roi)

                if active_policy.should_ocr(roi_frame, timestamp):
                    trigger_reason = getattr(active_policy, "last_trigger_reason", "unspecified")
                    diff_score = getattr(active_policy, "last_difference_score", None)
                    struct_score = getattr(active_policy, "last_structural_score", None)
                    h, w = roi_frame.shape[:2]
                    frame_reference = f"{path}@{timestamp:.6f}s"

                    # ONE shared detection pass, then ONE universal
                    # recognition batch against its ordered polygons --
                    # not one full detect+recognize per expected
                    # language. See RegionOcrEngine's contract
                    # (glyphcue/adapters/ocr_engine.py) and P2/P3's own
                    # PaddleOcrEngine/DirectMlOcrEngine.recognize_regions.
                    polygons = detect(roi_frame)
                    t0 = time.monotonic()
                    if isinstance(ocr_engine, RegionOcrEngine) and polygons:
                        regions = ocr_engine.recognize_regions(roi_frame, polygons)
                    else:
                        regions = ocr_engine.recognize(roi_frame)
                    call_latency = time.monotonic() - t0

                    metrics.record_invocation(
                        timestamp=timestamp,
                        trigger_reason=trigger_reason,
                        difference_score=diff_score,
                        dimensions=(w, h),
                        latency_seconds=call_latency,
                        structural_score=struct_score,
                    )
                    runtime_info = ocr_engine.runtime_info()
                    detail = {
                        "engine_version": runtime_info.version,
                        "backend": runtime_info.backend,
                        "backend_version": runtime_info.backend_version or "",
                    }
                    if trigger_reason != "unspecified":
                        detail[STATE_TRIGGER_DETAIL_KEY] = trigger_reason

                    non_empty_regions = [region for region in regions if region.text]
                    if non_empty_regions:
                        for region in non_empty_regions:
                            observation = Observation(
                                id=str(uuid.uuid4()),
                                text=region.text,
                                start_time=timestamp,
                                end_time=timestamp + INSTANT_SPAN_SECONDS,
                                provenance=Provenance(
                                    kind=ProvenanceKind.OCR_ENGINE,
                                    source=runtime_info.engine_name,
                                    detail=detail,
                                ),
                                language=region.language,
                                confidence=region.confidence,
                                roi=track_group.roi,
                                geometry=region.geometry,
                                frame_reference=frame_reference,
                            )
                            source_id = normalize_source_id(path)
                            observation_repository.add(observation, evidence_run_id, source_id)
                            metrics.observations_created += 1
                    else:
                        observation = Observation(
                            id=str(uuid.uuid4()),
                            text="",
                            start_time=timestamp,
                            end_time=timestamp + INSTANT_SPAN_SECONDS,
                            provenance=Provenance(
                                kind=ProvenanceKind.OCR_ENGINE,
                                source=runtime_info.engine_name,
                                detail=detail,
                            ),
                            language=None,
                            confidence=None,
                            roi=track_group.roi,
                            geometry=None,
                            frame_reference=frame_reference,
                        )
                        source_id = normalize_source_id(path)
                        observation_repository.add(observation, evidence_run_id, source_id)
                        metrics.observations_created += 1

                processed_in_range = timestamp - range_start
                metrics.media_seconds_processed = processed_in_range
                metrics.elapsed_seconds = time.monotonic() - wall_start
                metrics.candidate_transition_episodes = getattr(active_policy, "candidate_transition_episodes", 0)
                metrics.confirmed_transition_episodes = getattr(active_policy, "confirmed_transition_episodes", 0)
                metrics.rejected_transition_episodes = getattr(active_policy, "rejected_transition_episodes", 0)
                metrics.transition_episodes = getattr(active_policy, "transition_episodes", 0)
                metrics.suppressed_candidate_triggers = getattr(active_policy, "suppressed_candidate_triggers", 0)
                context.report_progress("multilingual_ocr_evidence", processed_in_range, range_duration)

            metrics.media_seconds_processed = range_duration
            metrics.elapsed_seconds = time.monotonic() - wall_start
            metrics.candidate_transition_episodes = getattr(active_policy, "candidate_transition_episodes", 0)
            metrics.confirmed_transition_episodes = getattr(active_policy, "confirmed_transition_episodes", 0)
            metrics.rejected_transition_episodes = getattr(active_policy, "rejected_transition_episodes", 0)
            metrics.transition_episodes = getattr(active_policy, "transition_episodes", 0)
            metrics.suppressed_candidate_triggers = getattr(active_policy, "suppressed_candidate_triggers", 0)
            context.report_progress("multilingual_ocr_evidence", range_duration, range_duration)
        finally:
            if source is not None:
                source.close()
            if engine_initialized:
                ocr_engine.shutdown()
            if conn is not None:
                conn.close()
            metrics.elapsed_seconds = time.monotonic() - wall_start

    return Job(work=work)
