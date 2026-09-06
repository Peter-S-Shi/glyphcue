from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN_ONNX_MODELS = {
    "det_medium": "PP-OCRv6_det_medium.onnx",
    "rec_small": "PP-OCRv6_rec_small.onnx",
    "cls_mobile": "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
}

PADDLE_MODEL_DIRS = {
    "det_medium": "PP-OCRv6_medium_det",
    "rec_medium": "PP-OCRv6_medium_rec",
}


def packaged_app_root() -> Path:
    override = os.environ.get("GLYPHCUE_APP_ROOT")
    if override:
        return Path(override)
    return Path(sys.executable).resolve().parent.parent


def packaged_models_dir() -> Path:
    override = os.environ.get("GLYPHCUE_PACKAGED_MODELS_DIR")
    if override:
        return Path(override)
    return packaged_app_root() / "models"


def resolve_packaged_onnx_model(name: str) -> Path | None:
    filename = FROZEN_ONNX_MODELS[name]
    candidate = packaged_models_dir() / filename
    return candidate if candidate.is_file() else None


def require_packaged_onnx_model(name: str) -> Path:
    candidate = resolve_packaged_onnx_model(name)
    if candidate is None:
        raise FileNotFoundError(
            f"Required frozen ONNX model is missing from packaged models directory: "
            f"{packaged_models_dir() / FROZEN_ONNX_MODELS[name]}"
        )
    return candidate


def resolve_packaged_paddle_model_dir(name: str) -> Path | None:
    dirname = PADDLE_MODEL_DIRS[name]
    candidate = packaged_models_dir() / "paddle" / dirname
    has_model = (candidate / "inference.json").is_file() or (
        candidate / "inference.pdmodel"
    ).is_file()
    if has_model and (candidate / "inference.pdiparams").is_file():
        return candidate
    return None
