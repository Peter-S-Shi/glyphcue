"""Path A OCR evidence job, experimental HYBRID profile.

This is the M11 Research Gate's surviving candidate wired into the real
Path A job, unchanged. Every algorithmic constant below is imported from
the module that won its own gate rather than restated here, so this file
cannot silently drift from the研究 result it integrates:

    5 fps evidence grid                 frozen research profile
    detector-anchored cheap scheduler   text_anchored_region_mask
    1.0s safety sentinel                hybrid_cascade_dry_run
    bootstrap + tail boundary rule      hybrid_cascade_dry_run
    Beta-S stroke-structural signature  beta_stroke_structural
    occupancy-normalized distance       occupancy_normalized_distance
    0.300 state grouping threshold      occupancy_normalized_distance
    stable medoid representative        sparse_observation_semantics

What the research runs never did is call recognition. The shape of the
saving is: the detector observes a sparse subset of the 5 fps grid, those
observations are grouped into subtitle states, and RECOGNITION runs once
per state -- on the state's medoid frame -- instead of once per triggered
frame. A state the detector confirmed as blank costs no recognition call
at all: the detector already answered the question, so the job records
the same empty-text observation the production job records for an
OCR-empty candidate, without paying for the call.

Deliberately identical to `build_ocr_evidence_job` in every respect that
is visible downstream:

  * one Observation per recognized text region, plus the empty-text
    marker for a blank state, with the same instant span
    (`INSTANT_SPAN_SECONDS`) and the same provenance shape;
  * persisted as soon as each state closes, so a cancel partway through
    keeps the evidence already found (ROADMAP M4);
  * the same run tagging, the same source identity, the same metrics
    object, the same progress reporting and cancellation contract.

So Cue reconstruction, review state, workspace persistence and the UI
see the same kind of evidence they already see -- fewer, more
deliberately chosen observations, not a different contract.

RESIDUAL RISK, measured and NOT solved here. It is not a scheduling
gap: a state shorter than the sentinel is still covered, by the
bootstrap at the head of the range and the boundary rule at its tail,
and replaying the corpus confirms such a state is observed inside its
own span on every ROI tested.

The real exposure is spatial. If the user's ROI does not cover the area
an unusually wide or tall caption occupies, the detector finds nothing
there on ANY frame for that caption's whole duration, so it is never
observed as text at all and produces no cue. Measured on the corpus: a
caption spanning 81% and 76% of frame width across two lines was
detected on every frame of its span under a generous ROI and on ZERO
frames under a tighter hand-drawn one, while the neighbouring 32-35%
wide captions survived both. No sampling rate, sentinel or grouping
change can recover it -- there is no frame in which the text is
visible to the detector.

V1 accepts this deliberately: the ROI stays a coarse, user-drawn search
envelope. Uniform ROI padding was tried and rejected (it cost real
states on the frozen research framing), and software-proposed ROIs were
tried and rejected (probing the full frame under-resolves captions, so
the proposals cropped real captions on held-out fixtures). The UI asks
the user to leave margin for wider and taller captions instead.

`detect` is injected, so this module never imports PaddleOCR's detector
and the job stays testable without the heavy `[ocr]` extra.
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
) -> Job:
    """The experimental hybrid Path A evidence job.

        decoded frames -> 5 fps grid -> cheap scheduler (detector-anchored)
          -> sparse text DETECTION -> Beta-S signature
          -> subtitle-state grouping -> ONE recognition per state

    Same job/DB/cancellation/progress contract as
    `build_ocr_evidence_job`; see the module docstring for what is
    deliberately identical downstream and what the known residual risk
    is.
    """
    if sampling_fps <= 0:
        raise ValueError("sampling_fps must be positive")

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
                for member in members:
                    if member.index != representative.index:
                        observed_frames.pop(member.index, None)
                frame = observed_frames.pop(representative.index, None)
                timestamp = representative.timestamp
                runtime_info = ocr_engine.runtime_info()
                detail = {
                    "engine_version": runtime_info.version,
                    "backend": runtime_info.backend,
                    "backend_version": runtime_info.backend_version or "",
                    STATE_TRIGGER_DETAIL_KEY: group.state_kind,
                }

                def observation_for(text, language, confidence, geometry) -> Observation:
                    return Observation(
                        id=str(uuid.uuid4()),
                        text=text,
                        start_time=timestamp,
                        end_time=timestamp + INSTANT_SPAN_SECONDS,
                        provenance=Provenance(
                            kind=ProvenanceKind.OCR_ENGINE,
                            source=runtime_info.engine_name,
                            detail=detail,
                        ),
                        language=language,
                        confidence=confidence,
                        roi=roi,
                        geometry=geometry,
                        frame_reference=f"{path}@{timestamp:.6f}s",
                    )

                if group.state_kind == "blank" or frame is None:
                    # The detector already established there is no text
                    # here. Recording the same empty-text marker the
                    # production job records for an OCR-empty candidate
                    # keeps M5's "went blank" evidence intact, and costs
                    # no recognition call.
                    persist(observation_for("", None, None, None))
                    return

                height, width = frame.shape[:2]
                call_start = time.monotonic()
                regions = ocr_engine.recognize(frame)
                metrics.record_invocation(
                    timestamp=timestamp,
                    trigger_reason=f"hybrid_state_{group.state_kind}",
                    difference_score=None,
                    dimensions=(width, height),
                    latency_seconds=time.monotonic() - call_start,
                )

                non_empty = [region for region in regions if region.text]
                if not non_empty:
                    persist(observation_for("", None, None, None))
                    return
                for region in non_empty:
                    persist(
                        observation_for(
                            region.text, region.language, region.confidence, region.geometry
                        )
                    )

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
