from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.application.beta_detector_dry_run import run_beta_detector_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

_WIDTH, _HEIGHT = 240, 48
_FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)


def _text_frame(spacing: int) -> np.ndarray:
    frame = np.full((_HEIGHT, _WIDTH, 3), 230, dtype=np.uint8)
    frame[12:30, 20:180:spacing] = 20
    return frame


def _blank_frame() -> np.ndarray:
    return np.full((_HEIGHT, _WIDTH, 3), 230, dtype=np.uint8)


def _write_three_state_fixture(path: Path) -> None:
    """State A (0-400ms), blank (500-900ms), state B (1000-1900ms)."""
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
            array = _text_frame(spacing=4)
        elif pts_ms < 1000:
            array = _blank_frame()
        else:
            array = _text_frame(spacing=9)
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


class _FakeDetector:
    """Stands in for real text detection: reports one caption-line box
    when the frame actually has ink, and nothing when it is blank."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, roi_frame: np.ndarray):
        self.calls += 1
        luminance = roi_frame.mean(axis=2) if roi_frame.ndim == 3 else roi_frame
        has_ink = bool((luminance < 128).any())
        if not has_ink:
            return []
        return [[[20, 12], [180, 12], [180, 30], [20, 30]]]


def test_beta_dry_run_separates_two_text_states_and_the_blank_gap(three_state_video):
    result = run_beta_detector_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
        detect=_FakeDetector(),
    )

    assert [g.state_kind for g in result.groups] == ["subtitle", "blank", "subtitle"]
    assert result.representative_count == 2
    assert result.blank_group_count == 1


def test_beta_dry_run_calls_the_detector_once_per_sampled_frame(three_state_video):
    # The gate's cost model: detector invocations scale with SAMPLED
    # frames, not decoded frames -- this is the number the cost
    # comparison against full recognition is built on.
    detector = _FakeDetector()

    result = run_beta_detector_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
        detect=detector,
    )

    assert detector.calls == result.sampled_frame_count
    assert result.detector_invocations == result.sampled_frame_count
    assert result.decoded_frame_count > result.sampled_frame_count


def test_beta_dry_run_records_cold_and_warm_detector_latency(three_state_video):
    result = run_beta_detector_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
        detect=_FakeDetector(),
    )

    assert result.detector_cold_latency_seconds >= 0.0
    assert result.detector_warm_mean_latency_seconds >= 0.0
    assert result.detector_wall_seconds >= 0.0


def test_beta_dry_run_treats_a_detector_finding_nothing_as_an_explicit_blank(
    three_state_video,
):
    result = run_beta_detector_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
        detect=lambda frame: [],
    )

    assert result.representative_count == 0
    assert result.blank_group_count == 1


def test_beta_dry_run_rejects_a_non_positive_sampling_fps(three_state_video):
    with pytest.raises(ValueError):
        run_beta_detector_dry_run(
            three_state_video,
            ProcessingRange(),
            _FULL_FRAME_ROI,
            sampling_fps=0.0,
            detect=_FakeDetector(),
        )


def test_beta_dry_run_uses_the_original_beta_signature_pairing_by_default(
    three_state_video,
):
    # Pins the Beta baseline: Beta-N supplies its own signature/distance
    # pairing explicitly, so the default path stays the 41e80f9 behavior
    # and the before/after comparison is a real comparison.
    result = run_beta_detector_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
        detect=_FakeDetector(),
    )

    assert result.representative_count == 2


def test_beta_dry_run_grouping_is_driven_by_the_injected_distance(three_state_video):
    # An injected distance that calls every pair different must split
    # each held text run frame by frame -- proving grouping really went
    # through the injected comparison and not the baseline one. (A
    # distance of 0.0 would NOT be a valid probe here: blank is a
    # structural state, so the blank gap separates the two text runs
    # regardless of any distance.)
    baseline = run_beta_detector_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
        detect=_FakeDetector(),
    )
    split_everything = run_beta_detector_dry_run(
        three_state_video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=5.0,
        detect=_FakeDetector(),
        distance_fn=lambda a, b: 1.0,
    )

    assert baseline.representative_count == 2
    assert split_everything.representative_count > baseline.representative_count
    assert split_everything.blank_group_count == 1
