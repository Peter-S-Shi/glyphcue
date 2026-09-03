from __future__ import annotations

from glyphcue.adapters.ocr_types import (
    OcrInitializationError,
    OcrRecognitionError,
    OcrRuntimeInfo,
    OcrTextRegion,
)

# GlyphCue-owned canonical language codes. PaddleOCR's own `lang=` codes
# ("ch", "japan") are a vendor detail and must never leak past this
# module -- see _CANONICAL_TO_PADDLE_LANG. Public: this is also the
# single source of truth for which languages the real production Path A
# Track Group language picker can offer a user (see
# ui/language_selection_panel.py) -- never a placeholder like "und",
# which this engine cannot actually be constructed with.
CANONICAL_LANGUAGES = ("en", "zh", "ja")
_CANONICAL_TO_PADDLE_LANG = {"en": "en", "zh": "ch", "ja": "japan"}


def _construct_paddleocr(*, language: str):
    """Isolated so tests can monkeypatch construction without a real
    model load, and so importing this module never requires paddleocr
    to be installed -- only calling initialize() does."""
    from paddleocr import PaddleOCR

    # enable_mkldnn=False works around a real crash observed with the
    # paddleocr==3.7.0 / paddlepaddle==3.3.1 pairing used for the V1
    # benchmark: NotImplementedError: (Unimplemented)
    # ConvertPirAttribute2RuntimeAttribute not support
    # [pir::ArrayAttribute<pir::DoubleAttribute>]. See
    # docs/adr/0001-ocr-runtime-selection.md.
    return PaddleOCR(
        lang=language,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )


def _paddleocr_version() -> str:
    try:
        import paddleocr

        return getattr(paddleocr, "__version__", "unknown")
    except Exception:
        return "unknown"


def _paddlepaddle_version() -> str:
    """PaddlePaddle's own version (imports as `paddle`, not `paddlepaddle`).

    Reported separately from _paddleocr_version() because the known
    enable_mkldnn crash worked around below is specific to one
    (paddleocr, paddlepaddle) version pairing, not to paddleocr alone --
    see docs/adr/0001-ocr-runtime-selection.md.
    """
    try:
        import paddle

        return getattr(paddle, "__version__", "unknown")
    except Exception:
        return "unknown"


class PaddleOcrEngine:
    """Concrete OcrEngine backed by PaddleOCR -- the V1 chosen default
    (see docs/adr/0001-ocr-runtime-selection.md for why).

    paddleocr/paddlex/paddle exceptions are caught here and re-raised as
    OcrError subclasses; paddlex result dicts never cross this boundary
    -- only OcrTextRegion does.
    """

    def __init__(self, language: str = "en") -> None:
        if language not in _CANONICAL_TO_PADDLE_LANG:
            raise ValueError(
                f"Unsupported language {language!r}; PaddleOcrEngine only accepts "
                f"GlyphCue canonical codes {CANONICAL_LANGUAGES}"
            )
        self._language = language
        self._engine = None

    def initialize(self) -> None:
        try:
            self._engine = _construct_paddleocr(
                language=_CANONICAL_TO_PADDLE_LANG[self._language]
            )
        except Exception as exc:
            raise OcrInitializationError(str(exc)) from exc

    def recognize(self, image: object) -> list[OcrTextRegion]:
        if self._engine is None:
            raise OcrRecognitionError("PaddleOcrEngine.initialize() must be called first")
        try:
            result = self._engine.predict(image)
        except Exception as exc:
            raise OcrRecognitionError(str(exc)) from exc

        if not result:
            return []
        texts = result[0].get("rec_texts", [])
        scores = result[0].get("rec_scores", [])
        polys = result[0].get("rec_polys") or [None] * len(texts)
        regions = []
        for text, score, poly in zip(texts, scores, polys):
            geometry = None
            if poly is not None:
                geometry = tuple((float(x), float(y)) for x, y in poly)
            regions.append(
                OcrTextRegion(
                    text=text,
                    confidence=float(score),
                    language=self._language,
                    geometry=geometry,
                )
            )
        return regions

    def recognize_regions(
        self, image: object, regions: object
    ) -> list[OcrTextRegion]:
        if self._engine is None:
            raise OcrRecognitionError("PaddleOcrEngine.initialize() must be called first")
        if not regions:
            return []
        try:
            return self._recognize_regions(image, regions)
        except Exception as exc:
            raise OcrRecognitionError(str(exc)) from exc

    def _recognize_regions(self, image: object, regions: object) -> list[OcrTextRegion]:
        import numpy as np

        pipeline = getattr(self._engine, "paddlex_pipeline", None)
        if pipeline is None:
            raise RuntimeError("PaddleOcrEngine underlying pipeline does not support region recognition")


        poly_list = [np.asarray(poly, dtype=np.float32) for poly in regions]
        if not poly_list:
            return []

        sorted_polygons = pipeline._sort_boxes(poly_list)
        crops = list(pipeline._crop_by_polys(image, sorted_polygons))
        valid = [
            (crop, poly)
            for crop, poly in zip(crops, sorted_polygons)
            if crop.size and crop.shape[0] and crop.shape[1]
        ]
        if not valid:
            return []

        ratios = sorted(
            range(len(valid)),
            key=lambda i: valid[i][0].shape[1] / float(valid[i][0].shape[0]),
        )
        sorted_crops = [valid[i][0] for i in ratios]
        rec_results = list(pipeline.text_rec_model(sorted_crops, return_word_box=False))
        if len(rec_results) != len(valid):
            raise RuntimeError("Recognizer output count does not match valid crop count")

        restored = [None] * len(valid)
        for i, rec_res in zip(ratios, rec_results):
            restored[i] = rec_res

        score_thresh = getattr(pipeline, "text_rec_score_thresh", 0.0)
        output_regions = []
        for (crop, poly), rec in zip(valid, restored):
            score = float(rec.get("rec_score", 0.0))
            if score >= score_thresh:
                geometry = tuple((float(x), float(y)) for x, y in poly)
                output_regions.append(
                    OcrTextRegion(
                        text=rec.get("rec_text", ""),
                        confidence=score,
                        language=self._language,
                        geometry=geometry,
                    )
                )
        return output_regions


    def supported_languages(self) -> tuple[str, ...]:
        return CANONICAL_LANGUAGES

    def runtime_info(self) -> OcrRuntimeInfo:
        return OcrRuntimeInfo(
            engine_name="PaddleOCR",
            version=_paddleocr_version(),
            backend="cpu",
            backend_version=_paddlepaddle_version(),
        )

    def shutdown(self) -> None:
        self._engine = None
