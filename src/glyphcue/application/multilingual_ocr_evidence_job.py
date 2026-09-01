from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Mapping

from glyphcue.adapters.ocr_engine import OcrEngine
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


def build_multilingual_ocr_evidence_job(
    path: Path,
    processing_range: ProcessingRange,
    track_group: TrackGroup,
    ocr_engines: Mapping[str, OcrEngine],
    db_path: Path,
    metrics: PipelineMetrics,
    evidence_run_id: str,
    *,
    policy: OcrInvocationPolicy | None = None,
) -> Job:
    """Milestone 6's real evidence-production seam: the M4 job
    architecture (`ocr_evidence_job.build_ocr_evidence_job`) extended
    from one `OcrEngine` to one engine PER Track Group-expected
    language, so genuinely multilingual evidence can exist in the first
    place.

    This is NOT because a configured-language engine instance only
    reads its own language -- real multi-engine verification
    (`benchmarks/multilingual_reconstruction/`, see
    docs/multilingual/track_group_reconstruction.md's "Evidence
    hygiene") found the opposite: every `PaddleOcrEngine` instance
    detects and transcribes EVERY text region in the frame regardless
    of which language it was constructed for, tagging all of its own
    output with its own configured language either way. One engine call
    per expected language still matters -- it's what gives each
    physical line a genuine reading from a model actually tuned for
    that script, real per-region geometry from that engine's own
    detector, and a real (if not fully trustworthy on its own -- see
    `assign_observations_to_languages`) language hint to work with,
    rather than only ever seeing whatever a single engine's own script
    bias happens to favor.

    `ocr_engines` must have exactly one entry per language in
    `track_group.languages` (raises `ValueError` otherwise) -- callers
    construct each engine themselves (e.g.
    `{"en": PaddleOcrEngine("en"), "zh": PaddleOcrEngine("zh")}`), same
    as M4 callers construct their single engine.

    The OCR-invocation decision (`policy.should_ocr`) is made exactly
    ONCE per frame, shared across every language's engine call for that
    frame -- not once per engine. This is what lets Milestone 6's
    reconstruction reuse M5's `group_into_state_runs` state-run grouping
    unchanged: every language layer sees the identical trigger cadence
    and `state_trigger` reason for a given frame, because they are
    literally evidence about the same physical frame, read multiple
    times.

    Every region every engine finds is persisted as its own Observation
    (tagged with that engine's own `language`, exactly like M4), sharing
    one `evidence_run_id` and one `frame_reference`/timestamp per frame
    regardless of which engine produced it. An engine that finds nothing
    on a triggered frame still gets a blank-candidate marker Observation
    persisted for it (M4's existing "OCR-empty is candidate evidence,
    not silence" rule -- see `ocr_evidence_job.py`), so a genuinely
    missing language layer for that frame is real recorded evidence, not
    an absence indistinguishable from "this frame was never OCR'd."

    `metrics.ocr_calls` counts real engine invocations (one per
    triggered frame per language) -- for a 2-language Track Group, a
    triggered frame costs 2 OCR calls, not 1, and the metric reports
    that honestly (ROADMAP: "metrics must come from a real execution
    path, no fake telemetry").
    """
    expected_languages = set(track_group.languages)
    if set(ocr_engines) != expected_languages:
        raise ValueError(
            "ocr_engines must have exactly one entry per Track Group language: "
            f"expected {sorted(expected_languages)}, got {sorted(ocr_engines)}"
        )

    active_policy = policy if policy is not None else ChangeTriggeredOcrPolicy()

    def work(context: JobContext) -> None:
        wall_start = time.monotonic()
        metadata = probe_media(path)
        range_start, range_end = processing_range.resolve(metadata.duration_seconds)
        range_duration = range_end - range_start

        initialized_languages: list[str] = []
        conn = None
        source = None
        try:
            init_start = time.monotonic()
            for language, engine in ocr_engines.items():
                engine.initialize()
                initialized_languages.append(language)
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
                    frame_reference = f"{path}@{timestamp:.6f}s"
                    h, w = roi_frame.shape[:2]

                    for engine in ocr_engines.values():
                        t0 = time.monotonic()
                        regions = engine.recognize(roi_frame)
                        call_latency = time.monotonic() - t0

                        metrics.record_invocation(
                            timestamp=timestamp,
                            trigger_reason=trigger_reason,
                            difference_score=diff_score,
                            dimensions=(w, h),
                            latency_seconds=call_latency,
                        )
                        runtime_info = engine.runtime_info()
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
                context.report_progress("multilingual_ocr_evidence", processed_in_range, range_duration)

            metrics.media_seconds_processed = range_duration
            metrics.elapsed_seconds = time.monotonic() - wall_start
            context.report_progress("multilingual_ocr_evidence", range_duration, range_duration)
        finally:
            if source is not None:
                source.close()
            for language in initialized_languages:
                ocr_engines[language].shutdown()
            if conn is not None:
                conn.close()
            metrics.elapsed_seconds = time.monotonic() - wall_start

    return Job(work=work)
