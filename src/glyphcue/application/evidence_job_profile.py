"""Which Path A evidence strategy a run uses.

Two strategies now exist and both are real:

  * `PRODUCTION_TRIGGER` -- `build_ocr_evidence_job` with
    `ChangeTriggeredOcrPolicy`, the shipped behavior. It stays the
    default everywhere, it is not deprecated, and it remains the
    fallback if the experimental profile is ever withdrawn.
  * `EXPERIMENTAL_HYBRID` -- `build_hybrid_ocr_evidence_job`, the M11
    Research Gate candidate. Opt-in only, and it needs a text detector
    the production profile does not use.

The switch is explicit on purpose. An implicit default that quietly
changed which pipeline produced a user's evidence would make two runs
incomparable without anything in the UI saying so; a caller naming its
profile can be read off the call site.
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
