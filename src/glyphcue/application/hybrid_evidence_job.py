"""Experimental Hybrid: frozen visual envelopes, bounded caption verification.

The 5fps grid, detector scheduler, Beta-S, occupancy_normalized_distance,
0.300 grouping and medoid are unchanged. Grouping is visual evidence only.
OCR probes happen before member pixels are released. Every raw region is
persisted at its actual PTS; a versioned envelope companion preserves refs,
blocks, identity support and unresolved coverage for reconstruction/review.

The default call cap is four per envelope: first/medoid/last plus one interior
refinement. This is a resource policy, NOT a calibrated production constant or
a guarantee of caption recall. Callers may explicitly raise it; performance
validation is pending. No text is extrapolated through unqueried time.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable

import numpy as np

from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.hybrid_cascade_dry_run import (
    CASCADE_CANDIDATE_DISTANCE_THRESHOLD,
    MAX_DETECTOR_GAP_SECONDS,
)
from glyphcue.application.caption_identity_verification import CaptionProbeReadError, verify_caption_identity
from glyphcue.domain.caption_identity import (
    CAPTION_IDENTITY_VERSION, CONTRACT_KEY, ENVELOPE_KEY, PAYLOAD_KEY, ROLE_KEY,
    CoarseEnvelope, FrameObservationRef, REPRESENTATIVE_PTS_KEY,
    OBSERVED_STATE_START_KEY, OBSERVED_STATE_END_KEY,
)
from glyphcue.application.occupancy_normalized_distance import (
    OCCUPANCY_GROUP_DISTANCE_THRESHOLD,
    occupancy_normalized_distance,
)
from glyphcue.application.ocr_evidence_job import (
    INSTANT_SPAN_SECONDS,
    STATE_TRIGGER_DETAIL_KEY,
)
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.application.source_identity import normalize_source_id
from glyphcue.application.sparse_observation_semantics import stable_representative
from glyphcue.application.subtitle_stable_signature import (
    EdgeStabilityBuffer,
    downsampled_edge_mask,
    subtitle_stable_signature,
)
from glyphcue.application.text_anchored_region_mask import TextAnchoredRegionMask
from glyphcue.application.visual_state_sampling import (
    IncrementalVisualStateGrouper,
    SampledFrame,
    signature_distance,
)
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.jobs.job import Job, JobContext
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository


def _state_representative(members: list[SampledFrame]) -> SampledFrame:
    """The group's medoid, measured with the SAME distance the grouping
    used. Keeping one definition here is what stops the two from
    drifting apart -- a representative chosen under a different metric
    than the one that formed the group is how you get the right state
    with the wrong frame."""
    return stable_representative(members, distance=occupancy_normalized_distance)


HYBRID_EVIDENCE_GRID_FPS = 5.0
"""The frozen research evidence grid. Not a quality knob: every gate in
the M11 Research Gate was decided at this rate, so changing it here would
invalidate the evidence this profile rests on."""

TextDetector = Callable[[np.ndarray], Any]


def build_hybrid_ocr_evidence_job(
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    ocr_engine: OcrEngine,
    db_path: Path,
    metrics: PipelineMetrics,
    evidence_run_id: str,
    *,
    detect: TextDetector,
    sampling_fps: float = HYBRID_EVIDENCE_GRID_FPS,
    caption_probe_budget: int = 4,
) -> Job:
    """The experimental hybrid Path A evidence job.

        decoded frames -> 5 fps grid -> cheap scheduler (detector-anchored)
          -> sparse text DETECTION -> Beta-S signature
          -> coarse visual envelopes -> bounded full-OCR identity probes

    Same job/DB/cancellation/progress contract as
    `build_ocr_evidence_job`; see the module docstring for what is
    deliberately identical downstream and what the known residual risk
    is.
    """
    if sampling_fps <= 0:
        raise ValueError("sampling_fps must be positive")
    if isinstance(caption_probe_budget, bool) or not isinstance(caption_probe_budget, int) or caption_probe_budget < 3:
        raise ValueError("caption_probe_budget must be an integer >= 3 (first/medoid/last)")

    def work(context: JobContext) -> None:
        wall_start = time.monotonic()
        metadata = probe_media(path)
        range_start, range_end = processing_range.resolve(metadata.duration_seconds)
        range_duration = range_end - range_start
        sample_interval = 1.0 / sampling_fps
        source_id = normalize_source_id(path)

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

            grouper = IncrementalVisualStateGrouper(
                group_distance_threshold=OCCUPANCY_GROUP_DISTANCE_THRESHOLD,
                distance=occupancy_normalized_distance,
                representative=_state_representative,
            )
            region_mask = TextAnchoredRegionMask()
            stability = EdgeStabilityBuffer()
            # ROI crops of observed frames, kept only until their state
            # closes -- recognition needs the medoid frame's pixels, and
            # which frame that is is not known until then.
            observed_frames: dict[int, np.ndarray] = {}
            observed_count = 0

            def persist(observation: Observation) -> None:
                observation_repository.add(observation, evidence_run_id, source_id)
                metrics.observations_created += 1

            def emit_state(group, members: list[SampledFrame]) -> None:
                representative = _state_representative(members)
                envelope = CoarseEnvelope(
                    str(uuid.uuid4()), group.start_timestamp, group.end_timestamp,
                    representative.timestamp,
                    tuple(FrameObservationRef(m.index, m.timestamp, f"{path}@{m.timestamp:.6f}s")
                          for m in members),
                )
                runtime = ocr_engine.runtime_info()
                detail = {
                    "engine_version": runtime.version,
                    "backend": runtime.backend,
                    "backend_version": runtime.backend_version or "",
                    STATE_TRIGGER_DETAIL_KEY: group.state_kind,
                    CONTRACT_KEY: CAPTION_IDENTITY_VERSION,
                    ENVELOPE_KEY: envelope.id,
                    REPRESENTATIVE_PTS_KEY: str(envelope.representative_pts),
                    OBSERVED_STATE_START_KEY: str(envelope.observed_start),
                    OBSERVED_STATE_END_KEY: str(envelope.observed_end),
                }

                def observation_for(text, language, confidence, geometry, ref, extra):
                    return Observation(
                        id=str(uuid.uuid4()), text=text, start_time=ref.pts,
                        end_time=ref.pts + INSTANT_SPAN_SECONDS,
                        provenance=Provenance(ProvenanceKind.OCR_ENGINE, runtime.engine_name,
                                              {**detail, **extra}),
                        language=language, confidence=confidence, roi=roi,
                        geometry=geometry, frame_reference=ref.frame_reference,
                    )

                def recognize(ref, reason):
                    if group.state_kind == "blank":
                        regions = []
                    else:
                        frame = observed_frames[ref.index]
                        call_start = time.monotonic()
                        try:
                            regions = list(ocr_engine.recognize(frame))
                        except Exception as error:
                            raise CaptionProbeReadError("OCR probe failed") from error
                        metrics.record_invocation(
                            timestamp=ref.pts, trigger_reason="hybrid_caption_probe",
                            difference_score=None, dimensions=(frame.shape[1], frame.shape[0]),
                            latency_seconds=time.monotonic() - call_start,
                        )
                    extra = {ROLE_KEY: "raw_probe", "probe_reason": reason,
                             "probe_observation_index": str(ref.index)}
                    raw = tuple(observation_for(r.text, r.language, r.confidence, r.geometry, ref, extra)
                                for r in regions)
                    if not raw:
                        raw = (observation_for("", None, None, None, ref, extra),)
                    for observation in raw:
                        persist(observation)
                    return raw

                try:
                    evidence = verify_caption_identity(
                        envelope, recognize, probe_budget=caption_probe_budget,
                        is_cancel_requested=context.is_cancel_requested,
                    )
                    ref = next(r for r in envelope.observations if r.pts == envelope.representative_pts)
                    persist(observation_for("", None, None, None, ref,
                                            {ROLE_KEY: "envelope", PAYLOAD_KEY: evidence.to_json()}))
                    if evidence.stop_reason == "ocr_failed":
                        raise CaptionProbeReadError("OCR failed; partial envelope evidence was preserved")
                finally:
                    for member in members:
                        observed_frames.pop(member.index, None)

            next_sample_time = range_start
            cheap_anchor: np.ndarray | None = None
            last_observed_time: float | None = None
            force_next_observation = False
            pending_tail: tuple[float, np.ndarray, np.ndarray] | None = None

            def observe(timestamp: float, roi_frame: np.ndarray, edge_mask: np.ndarray) -> None:
                """One scheduled detector observation: localize, reduce to
                the Beta-S signature, and feed the state grouper --
                recognizing whatever state that closes."""
                nonlocal cheap_anchor, observed_count

                detector_start = time.monotonic()
                polygons = detect(roi_frame)
                metrics.detector_seconds += time.monotonic() - detector_start
                metrics.detector_calls += 1

                polygons = list(polygons) if polygons is not None else []
                # The cheap gate's field of view follows the newest
                # confirmed text, and its anchor is re-taken THROUGH the
                # new mask so the next comparison cannot register a
                # change caused by the mask itself.
                region_mask.update(polygons, roi_frame.shape[:2])
                cheap_anchor = region_mask.apply(
                    subtitle_stable_signature(edge_mask, stability)
                )

                observed_frames[observed_count] = roi_frame
                closed = grouper.push(
                    SampledFrame(
                        index=observed_count,
                        timestamp=timestamp,
                        signature=beta_s_signature(roi_frame, polygons),
                        is_blank=not polygons,
                    )
                )
                observed_count += 1
                if closed is not None:
                    emit_state(*closed)

            source = PyAvMediaFrameSource()
            source.open(path)

            for timestamp, frame in source.frames(range_start, range_end):
                if context.is_cancel_requested():
                    partial = grouper.flush()
                    if partial is not None:
                        emit_state(*partial)
                    return
                metrics.frames_analyzed += 1
                roi_frame = crop_to_roi(frame, roi)

                edge_mask = downsampled_edge_mask(roi_frame)
                stability.push(timestamp, edge_mask)

                if timestamp >= next_sample_time:
                    next_sample_time += sample_interval
                    cheap = region_mask.apply(subtitle_stable_signature(edge_mask, stability))
                    changed = cheap_anchor is None or (
                        signature_distance(cheap, cheap_anchor)
                        > CASCADE_CANDIDATE_DISTANCE_THRESHOLD
                    )

                    if last_observed_time is None:
                        reason = "bootstrap"
                    elif force_next_observation:
                        reason = "candidate_followup"
                    elif changed:
                        reason = "candidate"
                    elif timestamp - last_observed_time >= MAX_DETECTOR_GAP_SECONDS:
                        reason = "sentinel"
                    else:
                        reason = None
                    force_next_observation = reason == "candidate"

                    if reason is None:
                        # Remember the most recent grid point nothing
                        # scheduled, so the boundary rule below can
                        # observe it without decoding the range twice.
                        pending_tail = (timestamp, roi_frame, edge_mask)
                    else:
                        pending_tail = None
                        observe(timestamp, roi_frame, edge_mask)
                        last_observed_time = timestamp

                processed_in_range = timestamp - range_start
                metrics.media_seconds_processed = processed_in_range
                metrics.elapsed_seconds = time.monotonic() - wall_start
                context.report_progress("ocr_evidence", processed_in_range, range_duration)

            # The range has two boundaries and the scheduler protects
            # one: the first grid point is always the bootstrap, while a
            # sentinel due after the range ends never fires. A state
            # living only in that last stretch would never be observed
            # at all -- sample_b's final 0.23s state is exactly that.
            # Observing the last grid point nothing else claimed closes
            # the range symmetrically, for at most one extra call.
            if pending_tail is not None:
                observe(*pending_tail)

            final = grouper.flush()
            if final is not None:
                emit_state(*final)

            metrics.media_seconds_processed = range_duration
            metrics.elapsed_seconds = time.monotonic() - wall_start
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
