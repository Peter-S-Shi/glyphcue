from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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


def _construct_text_recognition(*, model_name: str = "PP-OCRv6_medium_rec"):
    """Isolated standalone TextRecognition constructor so tests can
    monkeypatch without a real model load, and to ensure only official
    public standalone API is called."""
    from paddleocr import TextRecognition

    return TextRecognition(
        model_name=model_name,
        enable_mkldnn=False,
    )


def _sort_polygons_in_reading_order(polygons: Sequence[Any]) -> list[Any]:
    """Sort polygon bounding boxes in reading order: top-to-bottom, left-to-right
    with a 10px vertical band tolerance for multi-line and multi-column text."""
    import numpy as np

    if not polygons:
        return []
    dt_boxes = [np.asarray(p, dtype=np.float32) for p in polygons]
    sorted_boxes = sorted(dt_boxes, key=lambda x: (x[0][1], x[0][0]))
    _boxes = list(sorted_boxes)
    num_boxes = len(_boxes)
    for i in range(num_boxes - 1):
        for j in range(i, -1, -1):
            if abs(_boxes[j + 1][0][1] - _boxes[j][0][1]) < 10 and (
                _boxes[j + 1][0][0] < _boxes[j][0][0]
            ):
                tmp = _boxes[j]
                _boxes[j] = _boxes[j + 1]
                _boxes[j + 1] = tmp
            else:
                break
    return _boxes


def _crop_polygon_region(img: Any, poly: Any) -> Any:
    """Perspective-rectify and crop an image patch defined by a quad/polygon
    using standard 4-point perspective warp."""
    import cv2
    import numpy as np

    pts = np.asarray(poly, dtype=np.float32)
    if pts.shape[0] < 4:
        return np.zeros((0, 0, 3), dtype=np.uint8)

    bounding_box = cv2.minAreaRect(pts.astype(np.int32))
    box_pts = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])
    index_a, index_b, index_c, index_d = 0, 1, 2, 3
    if box_pts[1][1] > box_pts[0][1]:
        index_a, index_d = 0, 1
    else:
        index_a, index_d = 1, 0
    if box_pts[3][1] > box_pts[2][1]:
        index_b, index_c = 2, 3
    else:
        index_b, index_c = 3, 2

    box = np.array(
        [box_pts[index_a], box_pts[index_b], box_pts[index_c], box_pts[index_d]],
        dtype=np.float32,
    )
    img_crop_width = int(
        max(
            np.linalg.norm(box[0] - box[1]),
            np.linalg.norm(box[2] - box[3]),
        )
    )
    img_crop_height = int(
        max(
            np.linalg.norm(box[0] - box[3]),
            np.linalg.norm(box[1] - box[2]),
        )
    )
    if img_crop_width <= 0 or img_crop_height <= 0:
        return np.zeros((0, 0, 3), dtype=np.uint8)

    pts_std = np.float32(
        [
            [0, 0],
            [img_crop_width, 0],
            [img_crop_width, img_crop_height],
            [0, img_crop_height],
        ]
    )
    m_matrix = cv2.getPerspectiveTransform(box, pts_std)
    dst_img = cv2.warpPerspective(
        img,
        m_matrix,
        (img_crop_width, img_crop_height),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC,
    )
    if dst_img.shape[0] * 1.0 / dst_img.shape[1] >= 1.5:
        dst_img = np.rot90(dst_img)
    return dst_img



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
        self._recognizer = None

    def initialize(self) -> None:
        try:
            self._engine = _construct_paddleocr(
                language=_CANONICAL_TO_PADDLE_LANG[self._language]
            )
            self._recognizer = _construct_text_recognition(
                model_name="PP-OCRv6_medium_rec"
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
        self, image: object, regions: Sequence[Any]
    ) -> list[OcrTextRegion]:
        if self._recognizer is None:
            raise OcrRecognitionError("PaddleOcrEngine.initialize() must be called first")
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
        rec_results = self._recognizer.predict(crops)
        if len(rec_results) != len(crops_and_polys):
            raise RuntimeError("Recognizer output count does not match valid crop count")

        output_regions = []
        for (_, poly), rec in zip(crops_and_polys, rec_results):
            score = float(rec.get("rec_score", 0.0))
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
        if self._recognizer is not None:
            if hasattr(self._recognizer, "close"):
                try:
                    self._recognizer.close()
                except Exception:
                    pass
            self._recognizer = None
        self._engine = None

