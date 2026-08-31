from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PipelineMetrics:
    """Honest, real-execution instrumentation for an OCR evidence job.

    Mutable and passed in by the caller (mirroring how `JobContext` is
    passed into a `Job`'s work function): the job's work closure
    accumulates into it as it actually runs, and the caller reads it
    after the job finishes. Every field is a plain count/measurement
    taken from the real execution path -- nothing here is estimated or
    fabricated (ROADMAP Milestone 4: "metrics must come from a real
    execution path, no fake telemetry").
    """

    frames_analyzed: int = 0
    ocr_calls: int = 0
    observations_created: int = 0
    elapsed_seconds: float = 0.0
    media_seconds_processed: float = 0.0

    @property
    def ocr_calls_per_minute(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.ocr_calls / self.elapsed_seconds * 60.0

    @property
    def effective_processing_speed(self) -> float:
        """Media seconds processed per wall-clock second (real-time factor)."""
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.media_seconds_processed / self.elapsed_seconds
