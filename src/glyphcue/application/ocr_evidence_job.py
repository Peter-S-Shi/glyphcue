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
from glyphcue.application.source_identity import normalize_source_id
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.jobs.job import Job, JobContext
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository

INSTANT_SPAN_SECONDS = 0.001
"""An OCR observation is a point-in-time sample, not a duration claim --
Observation requires end_time > start_time, so this is a small fixed
span marking "this is an instant," not a measured/estimated duration.
Real duration/spanning across neighboring observations is Milestone 5's
job (multi-frame consensus / Cue reconstruction), not this one's."""

STATE_TRIGGER_DETAIL_KEY = "state_trigger"
"""Provenance.detail key carrying why this OCR call ran (see
ChangeTriggeredOcrPolicy.last_trigger_reason: "first_frame",
"change_detected", or "periodic_confirmation"). Milestone 5 reads this
as candidate evidence when reconstructing state-change boundaries,
instead of inferring them from OCR text similarity alone. Absent (key
not present) for policies that don't expose a reason, e.g.
NaiveDenseOcrPolicy."""


def build_ocr_evidence_job(
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    ocr_engine: OcrEngine,
    db_path: Path,
    metrics: PipelineMetrics,
    evidence_run_id: str,
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
    It likewise owns its SQLite connection's lifecycle inside `work`,
    opening it fresh on the job's own worker thread and closing it in
    `finally` -- callers pass a `db_path`, never an already-open
    connection/repository, so the worker thread's connection is never
    shared with (or must never be confused for) the caller's own
    connection on a different thread. Read results afterward with a
    separate `ObservationRepository(connect(db_path))` opened on the
    caller's own thread once `job.finished` has fired.

    Persists each Observation as soon as it is produced, so a
    cancel/failure partway through the run still keeps whatever evidence
    was already found (ROADMAP M4: "partial working state where
    appropriate"), tagged with `evidence_run_id` so one run's evidence
    (partial or complete) never mixes with a different run's -- see
    `ObservationRepository.list_for_run`.

    `metrics` is filled in as the job actually runs (the same
    passed-in-mutable-object pattern `JobContext` uses for cancellation)
    so its counts are read from the real execution path, never
    estimated. `frames_analyzed`/`ocr_calls`/`media_seconds_processed`/
    `elapsed_seconds` are all relative to the *resolved processing
    range*, not the source media's absolute timeline: a range starting
    well into a longer source must not have its progress or
    `effective_processing_speed` inflated by that source offset.
    Emitted Observations still carry source-correct absolute PTS
    (`start_time`/`end_time`/`frame_reference`) -- only the
    instrumentation/progress figures are range-relative.

    `policy` defaults to `ChangeTriggeredOcrPolicy()` -- the selective,
    production behavior. Passing `NaiveDenseOcrPolicy()` is supported
    only to produce a dense-OCR comparison baseline (ROADMAP M4
    acceptance gate 3), never as a production default.
    """
    active_policy = policy if policy is not None else ChangeTriggeredOcrPolicy()

    def work(context: JobContext) -> None:
        wall_start = time.monotonic()
        metadata = probe_media(path)
        range_start, range_end = processing_range.resolve(metadata.duration_seconds)
        range_duration = range_end - range_start

        # Every resource below is acquired inside this single
        # try/finally, in the order acquired, so a failure at any step
        # (engine init, DB connect, source open) still releases whatever
        # was already acquired before it -- never just the ones after
        # the last resource that happened to succeed.
        engine_initialized = False
        conn = None
        source = None
        try:
            init_start = time.monotonic()
            ocr_engine.initialize()
            metrics.engine_initialization_seconds = time.monotonic() - init_start
            engine_initialized = True

            conn = connect(db_path)
            observation_repository = ObservationRepository(conn)

            source = PyAvMediaFrameSource()
            source.open(path)

            for timestamp, frame in source.frames(range_start, range_end):
                if context.is_cancel_requested():
                    return
                metrics.frames_analyzed += 1
                roi_frame = crop_to_roi(frame, roi)

                if active_policy.should_ocr(roi_frame, timestamp):
                    trigger_reason = getattr(active_policy, "last_trigger_reason", "unspecified")
                    diff_score = getattr(active_policy, "last_difference_score", None)
                    struct_score = getattr(active_policy, "last_structural_score", None)
                    h, w = roi_frame.shape[:2]

                    t0 = time.monotonic()
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
                                roi=roi,
                                geometry=region.geometry,
                                frame_reference=f"{path}@{timestamp:.6f}s",
                            )
                            source_id = normalize_source_id(path)
                            observation_repository.add(observation, evidence_run_id, source_id)
                            metrics.observations_created += 1
                    else:
                        # OCR-empty candidate: the engine found no
                        # readable text at all on this OCR call -- this
                        # is only candidate evidence that the subtitle
                        # went blank, not a confirmed fact (Milestone 5
                        # decides confirmation, not M4). Persisting an
                        # empty-text marker (rather than silently doing
                        # nothing) gives Milestone 5 real evidence to
                        # work with in the first place, as opposed to
                        # "no OCR call happened to run" -- the two are
                        # otherwise indistinguishable.
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
                            roi=roi,
                            geometry=None,
                            frame_reference=f"{path}@{timestamp:.6f}s",
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
                context.report_progress("ocr_evidence", processed_in_range, range_duration)

            # The frame iterator was exhausted naturally -- not by a
            # cancel-triggered `return` above and not by an exception
            # (either would skip this) -- so this really did complete.
            # Emit one final completion progress at exactly the range
            # total: the last frame's own relative timestamp can fall
            # short of range_duration, and a successful run must still
            # report 100%, not "close to it."
            metrics.media_seconds_processed = range_duration
            metrics.elapsed_seconds = time.monotonic() - wall_start
            metrics.candidate_transition_episodes = getattr(active_policy, "candidate_transition_episodes", 0)
            metrics.confirmed_transition_episodes = getattr(active_policy, "confirmed_transition_episodes", 0)
            metrics.rejected_transition_episodes = getattr(active_policy, "rejected_transition_episodes", 0)
            metrics.transition_episodes = getattr(active_policy, "transition_episodes", 0)
            metrics.suppressed_candidate_triggers = getattr(active_policy, "suppressed_candidate_triggers", 0)
            context.report_progress("ocr_evidence", range_duration, range_duration)
        finally:
            if source is not None:
                source.close()
            if engine_initialized:
                ocr_engine.shutdown()
            if conn is not None:
                conn.close()
            metrics.elapsed_seconds = time.monotonic() - wall_start

    return Job(work=work)
