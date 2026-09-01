from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.application.alpha_visual_dry_run import run_alpha_visual_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

_WIDTH, _HEIGHT = 64, 24
_FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)


def _text_frame(offset: int = 0) -> np.ndarray:
    frame = np.full((_HEIGHT, _WIDTH, 3), 20, dtype=np.uint8)
    stripe_start = 5 + offset
    stripe_end = min(_WIDTH - 2, stripe_start + 20)
    frame[8:16, stripe_start:stripe_end:2] = 230
    return frame


def _blank_frame() -> np.ndarray:
    return np.full((_HEIGHT, _WIDTH, 3), 20, dtype=np.uint8)


def _write_three_state_fixture(path: Path) -> None:
    """20 frames @ 100ms: state A (0-400ms), blank (500-900ms), state B
    (1000-1900ms) -- one real transition, one explicit blank gap, then
    another real transition. Ground truth is exact by construction."""
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width = _WIDTH
    stream.height = _HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0

    for pts_ms in range(0, 2000, 100):
        if pts_ms < 500:
            array = _text_frame(offset=0)
        elif pts_ms < 1000:
            array = _blank_frame()
        else:
            array = _text_frame(offset=30)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


@pytest.fixture
def three_state_video(tmp_path) -> Path:
    path = tmp_path / "three_state.mp4"
    _write_three_state_fixture(path)
    return path


def test_alpha_dry_run_groups_two_subtitle_states_and_one_blank_gap(three_state_video):
    result = run_alpha_visual_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
    )

    assert [g.state_kind for g in result.groups] == ["subtitle", "blank", "subtitle"]
    assert result.representative_count == 2
    assert result.blank_group_count == 1


def test_alpha_dry_run_never_touches_ocr_or_persistence(three_state_video):
    # Purely a decode/crop/signature/group pipeline -- no PaddleOCR
    # import anywhere near it, provable by the fact this test needs no
    # OCR engine, no DB connection, and completes near-instantly.
    result = run_alpha_visual_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
    )

    assert result.elapsed_wall_seconds < 5.0


def test_alpha_dry_run_reports_decoded_and_sampled_frame_counts(three_state_video):
    result = run_alpha_visual_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
    )

    assert result.decoded_frame_count == 20
    assert result.sampled_frame_count == 10


def test_alpha_dry_run_representative_timestamps_bracket_both_real_states(three_state_video):
    result = run_alpha_visual_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
    )

    reps = result.representative_timestamps
    assert reps[0] < 0.5  # state A representative falls before the blank gap
    assert reps[-1] >= 1.0  # state B representative falls after the blank gap


def test_alpha_dry_run_rejects_a_non_positive_sampling_fps(three_state_video):
    with pytest.raises(ValueError):
        run_alpha_visual_dry_run(
            three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=0.0
        )


def test_higher_sampling_fps_never_loses_a_real_transition(three_state_video):
    for fps in (5.0, 8.0, 10.0):
        result = run_alpha_visual_dry_run(
            three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=fps
        )
        assert result.representative_count == 2, f"lost a transition at {fps} fps"
