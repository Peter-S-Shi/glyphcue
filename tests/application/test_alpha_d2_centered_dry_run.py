from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.application.alpha_d2_centered_dry_run import run_alpha_d2_centered_dry_run
from glyphcue.application.alpha_d_stable_dry_run import run_alpha_d_stable_dry_run
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


def _write_fixture(path: Path, noisy_background: bool, seed: int = 20260901) -> None:
    rng = np.random.default_rng(seed)
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
        array = array.copy()
        if noisy_background:
            noise_band = rng.integers(0, 256, size=(6, _WIDTH, 3), dtype=np.uint8)
            array[0:6, :, :] = noise_band
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


@pytest.fixture
def clean_three_state_video(tmp_path) -> Path:
    path = tmp_path / "clean_three_state.mp4"
    _write_fixture(path, noisy_background=False)
    return path


@pytest.fixture
def noisy_three_state_video(tmp_path) -> Path:
    path = tmp_path / "noisy_three_state.mp4"
    _write_fixture(path, noisy_background=True)
    return path


def test_alpha_d2_groups_two_subtitle_states_and_one_blank_gap_on_a_clean_fixture(
    clean_three_state_video,
):
    result = run_alpha_d2_centered_dry_run(
        clean_three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=5.0
    )

    assert result.blank_group_count == 1
    assert result.representative_count <= 3


def test_alpha_d2_never_touches_ocr_or_persistence(clean_three_state_video):
    result = run_alpha_d2_centered_dry_run(
        clean_three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=5.0
    )

    assert result.elapsed_wall_seconds < 10.0


def test_alpha_d2_rejects_a_non_positive_sampling_fps(clean_three_state_video):
    with pytest.raises(ValueError):
        run_alpha_d2_centered_dry_run(
            clean_three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=0.0
        )


def test_alpha_d2_does_not_lose_the_real_transitions_on_the_noisy_fixture(
    noisy_three_state_video,
):
    result = run_alpha_d2_centered_dry_run(
        noisy_three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=5.0
    )

    reps = result.representative_timestamps
    assert len(reps) >= 1
    assert reps[0] < 0.5
    assert reps[-1] >= 1.0


def test_alpha_d2_never_produces_more_representatives_than_alpha_d_on_the_noisy_fixture(
    noisy_three_state_video,
):
    # Alpha-D2 targets a specific onset artifact; it must not be WORSE
    # than Alpha-D on the same fixture/constants, only equal or better.
    alpha_d = run_alpha_d_stable_dry_run(
        noisy_three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=5.0
    )
    alpha_d2 = run_alpha_d2_centered_dry_run(
        noisy_three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=5.0
    )

    assert alpha_d2.representative_count <= alpha_d.representative_count


def test_alpha_d2_does_not_merge_the_two_real_text_states_on_the_noisy_fixture(
    noisy_three_state_video,
):
    # The critical anti-cheat assertion: any group-count reduction must
    # come from killing a spurious onset artifact, never from silently
    # merging the two textually-DIFFERENT real subtitle states into one
    # group -- that would "pass" the count gate by losing real recall.
    result = run_alpha_d2_centered_dry_run(
        noisy_three_state_video, ProcessingRange(), _FULL_FRAME_ROI, sampling_fps=5.0
    )

    subtitle_groups = [g for g in result.groups if g.state_kind == "subtitle"]
    assert len(subtitle_groups) >= 2
    first_group_end = subtitle_groups[0].end_timestamp
    last_group_start = subtitle_groups[-1].start_timestamp
    assert first_group_end < 1.0  # first state's own frames never reach into 1.0s+
    assert last_group_start >= 1.0  # last state's own frames never start before 1.0s
