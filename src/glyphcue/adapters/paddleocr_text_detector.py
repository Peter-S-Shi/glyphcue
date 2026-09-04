"""Production adapter for PaddleOCR text DETECTION (localization only).

Wraps `paddleocr.TextDetection` behind the plain callable shape
`hybrid_evidence_job.TextDetector` expects: one ROI-cropped frame in,
detected polygons out. Settings mirror, unchanged, the ones the M11
Research Gate verified in its own experiment tooling
(`benchmarks/m11_detector_assisted_beta/paddle_text_detector.py`):

  * `enable_mkldnn=False` -- the same ADR-0001 workaround production's
    `PaddleOcrEngine` already needs.
  * `limit_side_len=640` -- the conservative middle of the
    latency/accuracy curve the research gate measured; not retuned here.

This is shared, load-bearing production infrastructure: `create_text_detector`
(`text_detector_selection.py`) constructs one, with real fallback safety,
as the default CPU text detector for the shipped multilingual
PRODUCTION_TRIGGER path (`build_multilingual_ocr_evidence_job`) -- reachable
from a normal product launch with zero dev flags, whenever a user
configures more than one language on a Track Group. It is also usable by
the retained, research-only EXPERIMENTAL_HYBRID benchmark infrastructure
(`benchmarks/private_video_corpus/run_evaluation.py` and the M11
Research Gate benchmark scripts), which is not reachable from any
product or DevQA launch (M11 Legacy Pipeline Retirement Corrective Gate,
2026-09-04, removed that launch path entirely).
"""

from __future__ import annotations

from typing import Any

import numpy as np

DETECTOR_LIMIT_SIDE_LEN = 640


class PaddleOcrTextDetector:
    """Callable adapter matching `hybrid_evidence_job.TextDetector`."""

    def __init__(self, limit_side_len: int = DETECTOR_LIMIT_SIDE_LEN) -> None:
        self._limit_side_len = limit_side_len
        self._detector: Any = None

    def initialize(self) -> None:
        from paddleocr import TextDetection

        self._detector = TextDetection(
            enable_mkldnn=False, limit_side_len=self._limit_side_len
        )

    def __call__(self, roi_frame: np.ndarray):
        if self._detector is None:
            raise RuntimeError("PaddleOcrTextDetector.initialize() must be called first")
        result = self._detector.predict(roi_frame)
        if not result:
            return []
        polygons = result[0].get("dt_polys")
        if polygons is None:
            return []
        return [np.asarray(polygon) for polygon in polygons]

    def shutdown(self) -> None:
        self._detector = None
