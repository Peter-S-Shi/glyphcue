"""Production adapter for DirectML-accelerated text DETECTION.

Provides an exact ONNX DirectML backend equivalent to the formal PaddlePaddle
`PP-OCRv6_medium_det` text detector, with matching input resizing, ImageNet
normalization, and DBNet contour polygon extraction.

Conforms strictly to `hybrid_evidence_job.TextDetector`:
`Callable[[np.ndarray], list[np.ndarray]]` returning quad polygons of shape `(4, 2)`.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_DEFAULT_PACKAGES_DIR = Path(os.environ.get("GLYPHCUE_DIRECTML_PACKAGES_DIR", ""))
_DEFAULT_MODELS_DIR = Path(os.environ.get("GLYPHCUE_DIRECTML_MODELS_DIR", ""))
DETECTOR_LIMIT_SIDE_LEN = 640


@dataclass(frozen=True)
class _PreprocessingInfo:
    src_height: int
    src_width: int
    ratio_height: float
    ratio_width: float


def _order_box_points(box_points: np.ndarray) -> list[list[float]]:
    """Orders 4 rotated bounding box vertices matching PaddleX DBPostProcess.get_mini_boxes."""
    pts = sorted(box_points.tolist(), key=lambda p: p[0])
    i1, i4 = (0, 1) if pts[1][1] > pts[0][1] else (1, 0)
    i2, i3 = (2, 3) if pts[3][1] > pts[2][1] else (3, 2)
    return [pts[i1], pts[i2], pts[i3], pts[i4]]


def _resolve_medium_detector_model_path(explicit_path: str | None = None) -> Path:
    """Finds the PP-OCRv6_det_medium.onnx weights file across configured and standard locations."""
    if explicit_path:
        p = Path(explicit_path)
        if p.exists():
            return p

    candidates: list[Path] = []
    if _DEFAULT_MODELS_DIR.exists():
        candidates.append(_DEFAULT_MODELS_DIR / "PP-OCRv6_det_medium.onnx")
    candidates.append(Path.home() / ".cache" / "glyphcue" / "models" / "PP-OCRv6_det_medium.onnx")
    candidates.append(Path.home() / ".rapidocr" / "models" / "PP-OCRv6_det_medium.onnx")

    for c in candidates:
        if c.exists():
            return c

    raise RuntimeError(
        f"PP-OCRv6_det_medium.onnx not found in candidate locations: {[str(c) for c in candidates]}. "
        "DirectML text detector requires the exact medium detector weights; cannot fall back to a smaller model."
    )


class _ExactPaddleDirectMlDetectorBackend:
    """ONNX DirectML session executing PP-OCRv6_det_medium with exact Paddle pre/post-processing."""

    def __init__(
        self,
        model_path: str,
        limit_side_len: int = DETECTOR_LIMIT_SIDE_LEN,
        thresh: float = 0.2,
        box_thresh: float = 0.45,
        unclip_ratio: float = 1.4,
        max_side_limit: int = 4000,
    ) -> None:
        self.model_path = model_path
        self.limit_side_len = limit_side_len
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.unclip_ratio = unclip_ratio
        self.max_side_limit = max_side_limit
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        self.scale = 1.0 / 255.0
        self.sess: Any = None
        self.input_name = ""

    def initialize(self) -> None:
        if _DEFAULT_PACKAGES_DIR.exists() and str(_DEFAULT_PACKAGES_DIR) not in sys.path:
            sys.path.insert(0, str(_DEFAULT_PACKAGES_DIR))
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self.sess = ort.InferenceSession(
            self.model_path,
            sess_options=opts,
            providers=["DmlExecutionProvider", "CPUExecutionProvider"],
        )
        self.input_name = self.sess.get_inputs()[0].name

    def preprocess(self, img: np.ndarray) -> tuple[np.ndarray, _PreprocessingInfo]:
        import cv2

        h, w = img.shape[:2]
        if min(h, w) < self.limit_side_len:
            ratio = float(self.limit_side_len) / (h if h < w else w)
        else:
            ratio = 1.0

        resize_h = int(h * ratio)
        resize_w = int(w * ratio)

        if max(resize_h, resize_w) > self.max_side_limit:
            ratio = float(self.max_side_limit) / max(resize_h, resize_w)
            resize_h = int(resize_h * ratio)
            resize_w = int(resize_w * ratio)

        resize_h = max(int(round(resize_h / 32) * 32), 32)
        resize_w = max(int(round(resize_w / 32) * 32), 32)

        resized = cv2.resize(img, (resize_w, resize_h))
        ratio_h = resize_h / float(h)
        ratio_w = resize_w / float(w)

        norm = (resized.astype(np.float32) * self.scale - self.mean) / self.std
        chw = np.transpose(norm, (2, 0, 1))
        batch = np.expand_dims(chw, axis=0)
        return batch, _PreprocessingInfo(src_height=h, src_width=w, ratio_height=ratio_h, ratio_width=ratio_w)

    def postprocess(self, pred: np.ndarray, info: _PreprocessingInfo) -> list[np.ndarray]:
        import cv2
        import pyclipper

        dest_h = info.src_height
        dest_w = info.src_width

        pred_map = pred[0, 0, :, :]
        bitmap = pred_map > self.thresh

        height, width = bitmap.shape
        width_scale = dest_w / width
        height_scale = dest_h / height

        contours, _ = cv2.findContours(
            (bitmap * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )

        boxes: list[np.ndarray] = []
        for contour in contours[:3000]:
            bounding_box = cv2.minAreaRect(contour)
            canonical_box = _order_box_points(cv2.boxPoints(bounding_box))
            min_side_len = min(bounding_box[1])
            if min_side_len < 3:
                continue

            pts = np.array(canonical_box, dtype=np.float32)
            h_b, w_b = pred_map.shape[:2]
            xmin = max(0, min(math.floor(pts[:, 0].min()), w_b - 1))
            xmax = max(0, min(math.ceil(pts[:, 0].max()), w_b - 1))
            ymin = max(0, min(math.floor(pts[:, 1].min()), h_b - 1))
            ymax = max(0, min(math.ceil(pts[:, 1].max()), h_b - 1))

            mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
            pts_shifted = pts.copy()
            pts_shifted[:, 0] -= xmin
            pts_shifted[:, 1] -= ymin
            cv2.fillPoly(mask, pts_shifted.reshape(1, -1, 2).astype(np.int32), 1)
            score = cv2.mean(pred_map[ymin : ymax + 1, xmin : xmax + 1], mask)[0]

            if score < self.box_thresh:
                continue

            area = cv2.contourArea(pts)
            length = cv2.arcLength(pts, True)
            if length <= 0:
                continue
            distance = area * self.unclip_ratio / length
            offset = pyclipper.PyclipperOffset()
            offset.AddPath(pts, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
            try:
                expanded = np.array(offset.Execute(distance))
            except ValueError:
                expanded = np.array(offset.Execute(distance)[0])

            if len(expanded) == 0:
                continue

            unclipped_box = cv2.minAreaRect(expanded)
            if min(unclipped_box[1]) < 5:
                continue

            unclipped_canonical = _order_box_points(cv2.boxPoints(unclipped_box))
            box = np.array(unclipped_canonical, dtype=np.float32)
            for i in range(4):
                box[i, 0] = max(0.0, min(round(box[i, 0] * width_scale), float(dest_w)))
                box[i, 1] = max(0.0, min(round(box[i, 1] * height_scale), float(dest_h)))

            boxes.append(box)

        return boxes

    def __call__(self, roi_frame: np.ndarray) -> list[np.ndarray]:
        batch, shape_info = self.preprocess(roi_frame)
        preds = self.sess.run(None, {self.input_name: batch})
        return self.postprocess(preds[0], shape_info)

    def shutdown(self) -> None:
        self.sess = None


def _construct_detector_backend(
    *,
    model_path: str | None = None,
    limit_side_len: int = DETECTOR_LIMIT_SIDE_LEN,
    use_dml: bool = True,
) -> Any:
    """Isolated factory for detector backend, allowing contract unit tests to monkeypatch."""
    resolved_path = _resolve_medium_detector_model_path(model_path)
    backend = _ExactPaddleDirectMlDetectorBackend(
        model_path=str(resolved_path),
        limit_side_len=limit_side_len,
    )
    backend.initialize()
    return backend


class DirectMlTextDetector:
    """Callable text detector matching `hybrid_evidence_job.TextDetector` using DirectML GPU."""

    def __init__(
        self,
        limit_side_len: int = DETECTOR_LIMIT_SIDE_LEN,
        *,
        model_path: str | None = None,
    ) -> None:
        self._limit_side_len = limit_side_len
        self._model_path = model_path
        self._detector: Any = None

    def initialize(self) -> None:
        try:
            self._detector = _construct_detector_backend(
                model_path=self._model_path,
                limit_side_len=self._limit_side_len,
                use_dml=True,
            )
        except Exception as exc:
            raise RuntimeError(f"DirectML detector initialization failed: {exc}") from exc

    def __call__(self, roi_frame: np.ndarray) -> list[np.ndarray]:
        if self._detector is None:
            raise RuntimeError("DirectMlTextDetector.initialize() must be called first")
        boxes = self._detector(roi_frame)
        if not boxes:
            return []
        return [np.asarray(box, dtype=np.float32) for box in boxes]

    def shutdown(self) -> None:
        if hasattr(self._detector, "shutdown"):
            self._detector.shutdown()
        self._detector = None
