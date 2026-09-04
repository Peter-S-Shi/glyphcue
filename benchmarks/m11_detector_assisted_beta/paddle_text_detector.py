"""Experiment-only PaddleOCR text DETECTION wrapper (localization only).

Deliberately lives under `benchmarks/`, not `src/glyphcue/adapters/`:
this is M11 Research Gate experiment tooling, not a production adapter,
and nothing in production Path A imports it. It exists so
`glyphcue.application.beta_detector_dry_run` can stay free of any
paddleocr import (its detector is injected), which is what keeps the
Beta dry run unit-testable and CI-runnable without the heavy `[ocr]`
extra.

Recognition is never called here -- only `paddleocr.TextDetection`,
which runs the detection half of the same PP-OCR pipeline the
production `PaddleOcrEngine` runs end to end.

Two settings are fixed a priori and used unchanged for every fixture:

- `enable_mkldnn=False`: the SAME documented workaround production's
  `_construct_paddleocr` already needs. Verified during this round that
  detection-only hits the identical crash without it
  (`NotImplementedError: ConvertPirAttribute2RuntimeAttribute not
  support`) -- see docs/adr/0001-ocr-runtime-selection.md.
- `limit_side_len=640`: a standard PaddleOCR detection input bound, not
  a value searched against any fixture. Detection latency is dominated
  by this: measured on one real 1728x249 ROI crop, warm latency was
  ~3.36s at the library default, 0.93s at 960, 0.50s at 640, 0.25s at
  480 and 0.10s at 320, with an identical detected-box count at every
  scale. 640 is chosen as the conservative middle -- cheap enough to be
  a gate, still well above the point where boxes started to change.
"""

from __future__ import annotations

from typing import Any

import numpy as np

DETECTOR_LIMIT_SIDE_LEN = 640


class PaddleTextDetector:
    """Callable adapter matching `beta_detector_dry_run.TextDetector`:
    one ROI-cropped frame in, detected polygons out."""

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
            raise RuntimeError("PaddleTextDetector.initialize() must be called first")
        result = self._detector.predict(roi_frame)
        if not result:
            return []
        polygons = result[0].get("dt_polys")
        if polygons is None:
            return []
        return [np.asarray(polygon) for polygon in polygons]

    def shutdown(self) -> None:
        self._detector = None
