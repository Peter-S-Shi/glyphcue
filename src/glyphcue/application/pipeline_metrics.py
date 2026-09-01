from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class OcrInvocationRecord:
    """Individual record for one OCR recognize() call in a run."""

    timestamp: float
    trigger_reason: str
    difference_score: float | None
    dimensions: tuple[int, int]
    latency_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": round(self.timestamp, 4),
            "trigger_reason": self.trigger_reason,
            "difference_score": (
                round(self.difference_score, 4)
                if self.difference_score is not None
                else None
            ),
            "dimensions": list(self.dimensions),
            "latency_ms": round(self.latency_seconds * 1000.0, 2),
            "latency_seconds": round(self.latency_seconds, 4),
        }


@dataclass
class PipelineMetrics:
    """Honest, real-execution instrumentation for an OCR evidence job.

    Mutable and passed in by the caller: accumulated during real job execution
    and read by callers for diagnostics and performance reports.
    """

    frames_analyzed: int = 0
    ocr_calls: int = 0
    observations_created: int = 0
    elapsed_seconds: float = 0.0
    media_seconds_processed: float = 0.0
    engine_initialization_seconds: float = 0.0
    invocation_records: list[OcrInvocationRecord] = field(default_factory=list)

    def record_invocation(
        self,
        timestamp: float,
        trigger_reason: str,
        difference_score: float | None,
        dimensions: tuple[int, int],
        latency_seconds: float,
    ) -> None:
        self.invocation_records.append(
            OcrInvocationRecord(
                timestamp=timestamp,
                trigger_reason=trigger_reason,
                difference_score=difference_score,
                dimensions=dimensions,
                latency_seconds=latency_seconds,
            )
        )
        self.ocr_calls = len(self.invocation_records)

    @property
    def ocr_calls_per_minute(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.ocr_calls / self.elapsed_seconds * 60.0

    @property
    def ocr_calls_per_media_minute(self) -> float:
        if self.media_seconds_processed <= 0:
            return 0.0
        return self.ocr_calls / self.media_seconds_processed * 60.0

    @property
    def effective_processing_speed(self) -> float:
        """Media seconds processed per wall-clock second (real-time factor)."""
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.media_seconds_processed / self.elapsed_seconds

    @property
    def realtime_ratio(self) -> float:
        return self.effective_processing_speed

    @property
    def trigger_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.invocation_records:
            counts[r.trigger_reason] = counts.get(r.trigger_reason, 0) + 1
        return counts

    @property
    def latency_mean_seconds(self) -> float:
        if not self.invocation_records:
            return 0.0
        return float(np.mean([r.latency_seconds for r in self.invocation_records]))

    @property
    def latency_median_seconds(self) -> float:
        if not self.invocation_records:
            return 0.0
        return float(np.median([r.latency_seconds for r in self.invocation_records]))

    @property
    def latency_p95_seconds(self) -> float:
        if not self.invocation_records:
            return 0.0
        return float(np.percentile([r.latency_seconds for r in self.invocation_records], 95))

    def to_dict(self, include_invocations: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "summary": {
                "frames_analyzed": self.frames_analyzed,
                "ocr_calls": self.ocr_calls,
                "observations_created": self.observations_created,
                "media_seconds_processed": round(self.media_seconds_processed, 3),
                "elapsed_seconds": round(self.elapsed_seconds, 3),
                "engine_initialization_seconds": round(self.engine_initialization_seconds, 4),
                "ocr_calls_per_media_minute": round(self.ocr_calls_per_media_minute, 2),
                "realtime_ratio": round(self.realtime_ratio, 2),
                "trigger_counts": self.trigger_counts,
                "latency_mean_ms": round(self.latency_mean_seconds * 1000.0, 2),
                "latency_median_ms": round(self.latency_median_seconds * 1000.0, 2),
                "latency_p95_ms": round(self.latency_p95_seconds * 1000.0, 2),
            }
        }
        if include_invocations:
            result["invocations"] = [r.to_dict() for r in self.invocation_records]
        return result

    def format_summary_report(self) -> str:
        mean_ms = self.latency_mean_seconds * 1000.0
        med_ms = self.latency_median_seconds * 1000.0
        p95_ms = self.latency_p95_seconds * 1000.0
        triggers_str = ", ".join(f"{k}: {v}" for k, v in sorted(self.trigger_counts.items())) or "none"

        return (
            "=== Temporal OCR Baseline Diagnostic Report ===\n\n"
            f"Frames Analyzed:            {self.frames_analyzed}\n"
            f"OCR Calls:                  {self.ocr_calls}\n"
            f"Observations Created:       {self.observations_created}\n"
            f"Media Duration Processed:   {self.media_seconds_processed:.2f}s\n"
            f"Wall-Clock Elapsed Time:    {self.elapsed_seconds:.2f}s\n"
            f"Realtime Factor:            {self.realtime_ratio:.2f}x\n"
            f"OCR Calls / Media Minute:   {self.ocr_calls_per_media_minute:.2f}\n"
            f"Engine Initialization:      {self.engine_initialization_seconds * 1000.0:.1f}ms\n\n"
            "--- OCR Call Latency ---\n"
            f"Mean:                       {mean_ms:.2f}ms\n"
            f"Median:                     {med_ms:.2f}ms\n"
            f"P95:                        {p95_ms:.2f}ms\n\n"
            "--- Trigger Reasons ---\n"
            f"{triggers_str}\n"
        )
