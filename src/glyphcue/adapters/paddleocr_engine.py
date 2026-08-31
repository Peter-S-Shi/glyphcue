from __future__ import annotations

from glyphcue.adapters.ocr_types import (
    OcrInitializationError,
    OcrRecognitionError,
    OcrRuntimeInfo,
    OcrTextRegion,
)

_SUPPORTED_LANGUAGES = ("en", "ch", "japan")


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


class PaddleOcrEngine:
    """Concrete OcrEngine backed by PaddleOCR -- the V1 chosen default
    (see docs/adr/0001-ocr-runtime-selection.md for why).

    paddleocr/paddlex/paddle exceptions are caught here and re-raised as
    OcrError subclasses; paddlex result dicts never cross this boundary
    -- only OcrTextRegion does.
    """

    def __init__(self, language: str = "en") -> None:
        self._language = language
        self._engine = None

    def initialize(self) -> None:
        try:
            self._engine = _construct_paddleocr(language=self._language)
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
        return [
            OcrTextRegion(text=text, confidence=float(score), language=self._language)
            for text, score in zip(texts, scores)
        ]

    def supported_languages(self) -> tuple[str, ...]:
        return _SUPPORTED_LANGUAGES

    def runtime_info(self) -> OcrRuntimeInfo:
        return OcrRuntimeInfo(
            engine_name="PaddleOCR", version=_paddleocr_version(), backend="cpu"
        )

    def shutdown(self) -> None:
        self._engine = None
