import numpy as np
import pytest

from glyphcue.application.change_detection import (
    frame_difference_score,
    subtitle_structural_difference,
)
from glyphcue.application.ocr_invocation_policy import ChangeTriggeredOcrPolicy
from glyphcue.application.pipeline_metrics import PipelineMetrics


def _make_scene_frame(width: int = 100, height: int = 40, offset_x: float = 0.0, illumination: float = 100.0) -> np.ndarray:
    y, x = np.mgrid[0:height, 0:width]
    vals = illumination + 30.0 * np.sin((x + offset_x) / 15.0) + 20.0 * np.cos(y / 10.0)
    vals = np.clip(vals, 0, 255).astype(np.uint8)
    return np.stack([vals, vals, vals], axis=-1)


def _add_subtitle_text(frame: np.ndarray, text_pattern: str = "A", color: tuple[ int, int, int] = (240, 240, 240)) -> np.ndarray:
    out = frame.copy()
    h, w, _ = out.shape
    if text_pattern == "A":
        for start_col in range(20, w - 30, 20):
            out[10:30, start_col:start_col+14] = (20, 20, 20)
            out[12:28, start_col+2:start_col+12] = color
            out[18:22, start_col+4:start_col+10] = (20, 20, 20)
    elif text_pattern == "B":
        for start_col in range(20, w - 30, 20):
            out[10:30, start_col:start_col+14] = (20, 20, 20)
            out[12:28, start_col+2:start_col+12] = color
            out[14:18, start_col+3:start_col+11] = (20, 20, 20)
            out[22:26, start_col+3:start_col+11] = (20, 20, 20)
    elif text_pattern == "CJK":
        for start_col in range(15, w - 35, 25):
            out[8:32, start_col:start_col+20] = (20, 20, 20)
            out[10:30, start_col+2:start_col+18] = color
            out[15:18, start_col+4:start_col+16] = (20, 20, 20)
            out[22:25, start_col+4:start_col+16] = (20, 20, 20)
            out[10:30, start_col+9:start_col+12] = (20, 20, 20)
    return out


def test_subtitle_structural_difference_discriminates_text_from_background_motion():
    bg1 = _make_scene_frame(offset_x=0.0, illumination=100.0)
    bg2 = _make_scene_frame(offset_x=12.0, illumination=125.0)

    raw_bg_diff = frame_difference_score(bg1, bg2)
    struct_bg_diff = subtitle_structural_difference(bg1, bg2)

    assert raw_bg_diff > 0.05
    assert struct_bg_diff < 0.01

    sub_frame = _add_subtitle_text(bg1, "A")
    struct_sub_diff = subtitle_structural_difference(bg1, sub_frame)

    assert struct_sub_diff > 0.05
    assert struct_sub_diff > struct_bg_diff * 10


def test_persistent_moving_background_offset_is_rejected_without_ocr():
    policy = ChangeTriggeredOcrPolicy()
    frame0 = _make_scene_frame(offset_x=0.0, illumination=100.0)
    assert policy.should_ocr(frame0, 0.0) is True

    frame1 = _make_scene_frame(offset_x=5.0, illumination=115.0)
    assert policy.should_ocr(frame1, 0.033) is False
    assert policy.should_ocr(frame1, 0.066) is False
    assert policy.should_ocr(frame1, 0.100) is False

    assert policy.candidate_transition_episodes >= 1
    assert policy.rejected_transition_episodes >= 1
    assert policy.confirmed_transition_episodes == 0
    assert policy.transition_episodes == 0


def test_genuine_subtitle_appearance_on_moving_background_confirms_one_ocr_call():
    policy = ChangeTriggeredOcrPolicy()
    bg0 = _make_scene_frame(offset_x=0.0, illumination=100.0)
    assert policy.should_ocr(bg0, 0.0) is True

    sub_t1 = _add_subtitle_text(_make_scene_frame(offset_x=10.0, illumination=110.0), "A")
    assert policy.should_ocr(sub_t1, 1.000) is False

    sub_t2 = _add_subtitle_text(_make_scene_frame(offset_x=10.0, illumination=110.0), "A")
    assert policy.should_ocr(sub_t2, 1.066) is True
    assert policy.last_trigger_reason == "change_detected"
    assert policy.confirmed_transition_episodes == 1


def test_subtitle_text_change_confirms_one_ocr_call():
    policy = ChangeTriggeredOcrPolicy()
    bg = _make_scene_frame()
    sub_a = _add_subtitle_text(bg, "A")
    assert policy.should_ocr(sub_a, 0.0) is True

    sub_b = _add_subtitle_text(bg, "B")
    assert policy.should_ocr(sub_b, 1.000) is False
    assert policy.should_ocr(sub_b, 1.066) is True
    assert policy.last_trigger_reason == "change_detected"
    assert policy.confirmed_transition_episodes == 1


def test_subtitle_disappearance_confirms_one_ocr_call():
    policy = ChangeTriggeredOcrPolicy()
    bg = _make_scene_frame()
    sub_a = _add_subtitle_text(bg, "A")
    assert policy.should_ocr(sub_a, 0.0) is True

    assert policy.should_ocr(bg, 1.000) is False
    assert policy.should_ocr(bg, 1.066) is True
    assert policy.last_trigger_reason == "change_detected"
    assert policy.confirmed_transition_episodes == 1


def test_cjk_subtitle_appearance_and_text_change():
    policy = ChangeTriggeredOcrPolicy()
    bg = _make_scene_frame()
    assert policy.should_ocr(bg, 0.0) is True

    sub_cjk = _add_subtitle_text(bg, "CJK")
    assert policy.should_ocr(sub_cjk, 0.500) is False
    assert policy.should_ocr(sub_cjk, 0.566) is True
    assert policy.confirmed_transition_episodes == 1


def test_unchanged_subtitle_with_moving_background_behind_it_is_rejected():
    policy = ChangeTriggeredOcrPolicy()
    bg1 = _make_scene_frame(offset_x=0.0, illumination=100.0)
    sub1 = _add_subtitle_text(bg1, "A")
    assert policy.should_ocr(sub1, 0.0) is True

    bg2 = _make_scene_frame(offset_x=15.0, illumination=120.0)
    sub2 = _add_subtitle_text(bg2, "A")

    assert policy.should_ocr(sub2, 0.500) is False
    assert policy.should_ocr(sub2, 0.566) is False

    assert policy.confirmed_transition_episodes == 0
    assert policy.rejected_transition_episodes >= 1


def test_diagnostics_track_rejected_episodes_and_structural_diff():
    metrics = PipelineMetrics()
    metrics.frames_analyzed = 300
    metrics.ocr_calls = 5
    metrics.candidate_transition_episodes = 20
    metrics.confirmed_transition_episodes = 4
    metrics.rejected_transition_episodes = 16
    metrics.suppressed_candidate_triggers = 80


    diag = metrics.to_dict()
    assert diag["summary"]["candidate_transition_episodes"] == 20
    assert diag["summary"]["confirmed_transition_episodes"] == 4
    assert diag["summary"]["rejected_transition_episodes"] == 16
    assert diag["summary"]["suppressed_candidate_triggers"] == 80

    report = metrics.format_summary_report()
    assert "Candidate Episodes:" in report and "20" in report
    assert "Confirmed Episodes:" in report and "4" in report
    assert "Rejected Episodes:" in report and "16" in report
