from glyphcue.adapters.media_frame_source import MediaFrameSource
from glyphcue.adapters.media_transform import MediaTransformService
from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.subtitle_io import SubtitleFormatAdapter


def test_subtitle_format_adapter_declares_parse_and_write():
    assert hasattr(SubtitleFormatAdapter, "parse")
    assert hasattr(SubtitleFormatAdapter, "write")


def test_ocr_engine_declares_lifecycle_and_recognition():
    assert hasattr(OcrEngine, "initialize")
    assert hasattr(OcrEngine, "recognize")
    assert hasattr(OcrEngine, "supported_languages")
    assert hasattr(OcrEngine, "runtime_info")
    assert hasattr(OcrEngine, "shutdown")


def test_media_frame_source_declares_open_frames_close():
    assert hasattr(MediaFrameSource, "open")
    assert hasattr(MediaFrameSource, "frames")
    assert hasattr(MediaFrameSource, "close")


def test_media_transform_service_declares_transcode():
    assert hasattr(MediaTransformService, "transcode")
