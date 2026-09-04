"""Which Path A evidence strategy a run uses.

  * `PRODUCTION_TRIGGER` -- `build_ocr_evidence_job` with
    `ChangeTriggeredOcrPolicy`, the shipped behavior. It is the ONLY
    profile any product or DevQA launch can reach -- there is no UI
    control, launch-time switch, or env var left anywhere that can
    select the other one (M11 Legacy Pipeline Retirement Corrective
    Gate, 2026-09-04, retired the developer OCR Profile selector that
    used to expose it).
  * `EXPERIMENTAL_HYBRID` -- `build_hybrid_ocr_evidence_job`. Retained
    ONLY as historical evaluation/reproducibility infrastructure for
    `benchmarks/private_video_corpus/run_evaluation.py` and the other
    M11 Research Gate benchmark scripts, which construct and invoke it
    directly; it is not a product pipeline and not reachable from
    `src/glyphcue/ui/`.

The switch is explicit on purpose. An implicit default that quietly
changed which pipeline produced a user's evidence would make two runs
incomparable without anything saying so; a caller naming its profile can
be read off the call site.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.application.hybrid_evidence_job import (
    TextDetector,
    build_hybrid_ocr_evidence_job,
)
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI
from glyphcue.jobs.job import Job


class EvidenceJobProfile(Enum):
    PRODUCTION_TRIGGER = "production_trigger"
    EXPERIMENTAL_HYBRID = "experimental_hybrid"


def build_evidence_job_for_profile(
    profile: EvidenceJobProfile,
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    ocr_engine: OcrEngine,
    db_path: Path,
    metrics: PipelineMetrics,
    evidence_run_id: str,
    *,
    detect: TextDetector | None = None,
) -> Job:
    """Builds the evidence job the named profile asks for.

    The experimental profile requires a detector; refusing to build
    without one is deliberate, since silently falling back to the
    production path would produce a run whose profile label is a lie.
    """
    if profile is EvidenceJobProfile.PRODUCTION_TRIGGER:
        return build_ocr_evidence_job(
            path, processing_range, roi, ocr_engine, db_path, metrics, evidence_run_id
        )
    if detect is None:
        raise ValueError(
            "EXPERIMENTAL_HYBRID needs a text detector (`detect`); "
            "it does not fall back to the production profile"
        )
    return build_hybrid_ocr_evidence_job(
        path,
        processing_range,
        roi,
        ocr_engine,
        db_path,
        metrics,
        evidence_run_id,
        detect=detect,
    )
