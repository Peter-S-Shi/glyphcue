from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from glyphcue.adapters.ocr_types import (
    OcrInitializationError,
    OcrRecognitionError,
    OcrRuntimeInfo,
    OcrTextRegion,
)
from glyphcue.adapters.paddleocr_engine import (
    CANONICAL_LANGUAGES,
    _crop_polygon_region,
    _sort_polygons_in_reading_order,
)

# Optional local overrides for offline/pinned-artifact environments (e.g. a
# private test machine with no internet access). Neither is required for a
# normal `pip install -e ".[directml]"`: RapidOCR manages its own model
# download/cache on first use, the same way paddleocr/paddlepaddle already
# do for the Paddle path -- GlyphCue does not bundle or version the .onnx
# weights itself. See docs/adr/0001-ocr-runtime-selection.md's Milestone 11
# addendum for the model provenance/packaging contract.
_DEFAULT_PACKAGES_DIR = Path(os.environ.get("GLYPHCUE_DIRECTML_PACKAGES_DIR", ""))
_DEFAULT_MODELS_DIR = Path(os.environ.get("GLYPHCUE_DIRECTML_MODELS_DIR", ""))


def _construct_rapidocr(
    *,
    model_root_dir: str | None = None,
    use_dml: bool = True,
) -> Any:
    """Isolated constructor for RapidOCR so contract tests can monkeypatch
    without requiring DirectML hardware or downloading ONNX models."""
    if _DEFAULT_PACKAGES_DIR.exists() and str(_DEFAULT_PACKAGES_DIR) not in sys.path:
        sys.path.insert(0, str(_DEFAULT_PACKAGES_DIR))

    from rapidocr import RapidOCR

    models_dir = model_root_dir or (str(_DEFAULT_MODELS_DIR) if _DEFAULT_MODELS_DIR.exists() else None)
    params: dict[str, Any] = {
        "Global.use_cls": False,
        "EngineConfig.onnxruntime.use_dml": use_dml,
    }
    if models_dir is not None:
        params["Global.model_root_dir"] = models_dir

    return RapidOCR(params=params)


class DirectMlOcrEngine:
    """Opt-in experimental RegionOcrEngine backed by RapidOCR with ONNX Runtime DirectML.

    Executes on Windows GPU via DirectML (DmlExecutionProvider) while implementing
    the exact GlyphCue RegionOcrEngine protocol, reading order, and geometry contract.
    Never construct this directly in application code -- use
    glyphcue.adapters.ocr_engine_selection.create_ocr_engine, which gates it behind
    platform/package preflight and falls back to PaddleOcrEngine (the frozen
    default) whenever DirectML isn't usable.
    """

    def __init__(self, language: str = "en") -> None:
        if language not in CANONICAL_LANGUAGES:
            raise ValueError(
                f"Unsupported language {language!r}; DirectMlOcrEngine only accepts "
                f"GlyphCue canonical codes {CANONICAL_LANGUAGES}"
            )
        self._language = language
        self._engine: Any | None = None

    def initialize(self) -> None:
        try:
            self._engine = _construct_rapidocr(use_dml=True)
        except Exception as exc:
            raise OcrInitializationError(str(exc)) from exc

    def recognize(self, image: object) -> list[OcrTextRegion]:
        if self._engine is None:
            raise OcrRecognitionError("DirectMlOcrEngine.initialize() must be called first")
        try:
            out = self._engine(image, use_cls=False)
            if out.txts is None:
                return []
            regions = []
            boxes = out.boxes if out.boxes is not None else [None] * len(out.txts)
            scores = out.scores if out.scores is not None else [0.0] * len(out.txts)
            for text, score, box in zip(out.txts, scores, boxes):
                geometry = None
                if box is not None:
                    geometry = tuple((float(x), float(y)) for x, y in box)
                regions.append(
                    OcrTextRegion(
                        text=str(text),
                        confidence=float(score),
                        language=self._language,
                        geometry=geometry,
                    )
                )
            return regions
        except Exception as exc:
            raise OcrRecognitionError(str(exc)) from exc

    def recognize_regions(
        self, image: object, regions: Sequence[Any]
    ) -> list[OcrTextRegion]:
        if self._engine is None:
            raise OcrRecognitionError("DirectMlOcrEngine.initialize() must be called first")
        if not regions:
            return []
        try:
            return self._recognize_regions(image, regions)
        except Exception as exc:
            raise OcrRecognitionError(str(exc)) from exc

    def _recognize_regions(
        self, image: object, regions: Sequence[Any]
    ) -> list[OcrTextRegion]:
        import numpy as np

        img_arr = np.asarray(image)
        sorted_polygons = _sort_polygons_in_reading_order(regions)
        if not sorted_polygons:
            return []

        crops_and_polys = []
        for poly in sorted_polygons:
            crop = _crop_polygon_region(img_arr, poly)
            if crop.size and crop.shape[0] > 0 and crop.shape[1] > 0:
                crops_and_polys.append((crop, poly))

        if not crops_and_polys:
            return []

        crops = [c for c, _ in crops_and_polys]
        # RapidOCR's own public, standalone recognition-only method
        # (main.py: RapidOCR.recognize_txt -> self.text_rec(...)) -- never
        # touches RapidOCR.text_det, so this performs zero internal
        # detection, matching the Paddle P2 recognize_regions contract.
        rec_res = self._engine.recognize_txt(crops)
        txts = rec_res.txts if rec_res.txts is not None else ()
        scores = rec_res.scores if rec_res.scores is not None else ()

        if len(txts) != len(crops_and_polys):
            raise RuntimeError(
                f"Recognizer output count ({len(txts)}) does not match valid crop count ({len(crops_and_polys)})"
            )

        output_regions = []
        for (_, poly), text, score in zip(crops_and_polys, txts, scores):
            geometry = tuple((float(x), float(y)) for x, y in poly)
            output_regions.append(
                OcrTextRegion(
                    text=str(text),
                    confidence=float(score),
                    language=self._language,
                    geometry=geometry,
                )
            )
        return output_regions

    def supported_languages(self) -> tuple[str, ...]:
        return CANONICAL_LANGUAGES

    def runtime_info(self) -> OcrRuntimeInfo:
        version = "unknown"
        try:
            import rapidocr
            version = getattr(rapidocr, "__version__", "unknown")
        except Exception:
            pass
        return OcrRuntimeInfo(
            engine_name="RapidOCR",
            version=version,
            backend="directml",
            backend_version="onnxruntime-directml",
        )

    def shutdown(self) -> None:
        self._engine = None
