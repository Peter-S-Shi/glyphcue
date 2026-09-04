from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.application.hybrid_cascade_dry_run import (
    MAX_DETECTOR_GAP_SECONDS,
    run_hybrid_cascade_dry_run,
)
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

_WIDTH, _HEIGHT = 240, 48
_FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)
_SAMPLING_FPS = 5.0


def _text_frame(spacing: int) -> np.ndarray:
    frame = np.full((_HEIGHT, _WIDTH, 3), 230, dtype=np.uint8)
    frame[12:30, 20:180:spacing] = 20
    return frame


def _blank_frame() -> np.ndarray:
    return np.full((_HEIGHT, _WIDTH, 3), 230, dtype=np.uint8)


def _write_three_state_fixture(path: Path) -> None:
    """State A (0-400ms), blank (500-900ms), state B (1000-1900ms) --
    the same synthetic fixture the Beta dry run is pinned against, so
    cascade behavior is compared against a known baseline."""
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
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, roi_frame: np.ndarray):
        self.calls += 1
        luminance = roi_frame.mean(axis=2) if roi_frame.ndim == 3 else roi_frame
        if not bool((luminance < 128).any()):
            return []
        return [[[20, 12], [180, 12], [180, 30], [20, 30]]]


def _blind_cheap_gate(edge_mask, stability):
    """A cheap gate that reports "nothing ever changes" -- the worst case
    the safety sentinel exists for."""
    return np.zeros((4, 4), dtype=bool)


def _run(video, detect=None, **kwargs):
    return run_hybrid_cascade_dry_run(
        video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        sampling_fps=kwargs.pop("sampling_fps", _SAMPLING_FPS),
        detect=detect if detect is not None else _FakeDetector(),
        **kwargs,
    )


# --- cost: the detector stops running on every sampled frame -------------


def test_the_cascade_runs_the_detector_on_fewer_frames_than_it_samples(three_state_video):
    detector = _FakeDetector()

    result = _run(three_state_video, detector)

    assert result.detector_invocations < result.sampled_frame_count
    assert detector.calls == result.detector_invocations


def test_every_detector_invocation_is_attributed_to_a_trigger(three_state_video):
    result = _run(three_state_video)

    assert sum(result.trigger_counts.values()) == result.detector_invocations
    assert set(result.trigger_counts) <= {
        "bootstrap",
        "candidate",
        "candidate_followup",
        "sentinel",
    }


# --- the cheap gate may schedule, but may never decide -------------------


def test_the_cascade_keeps_two_different_captions_apart(three_state_video):
    # The contract that must never bend: scheduling may cost the cascade
    # an observation, but it must never merge two genuinely different
    # subtitle states into one.
    result = _run(three_state_video)

    assert result.representative_count == 2


def test_characterizes_a_state_shorter_than_the_sentinel_period_being_missed(
    three_state_video,
):
    """CHARACTERIZATION of the cascade's declared limit.

    `MAX_DETECTOR_GAP_SECONDS` guarantees the detector observes at least
    once in any window of that length, so a state SHORTER than it is
    guaranteed only if the cheap gate happens to fire. Here it does not,
    and the 0.5s blank (0.5-0.9s) falls inside a 0.8s detector gap.

    The cheap gate misses it for an instructive reason, and not the one
    that looks obvious: it is not that blank resembles text, but that on
    this synthetic h264 grating the Alpha-D persistence filter washes out
    the text itself (cheap density 0.153 raw -> 0.0003 after persistence,
    because compression jitters the stroke edges frame to frame). Held
    text and blank therefore look equally empty to the SCHEDULER -- while
    Beta-S, running on the same frames, still separates them perfectly.

    That is the whole argument for the cascade's two safety rules: the
    cheap gate is allowed to be this wrong, because being wrong costs a
    delayed look (bounded by the sentinel) rather than a decision.
    """
    result = _run(three_state_video)

    assert "blank" not in [g.state_kind for g in result.groups]
    assert result.max_detector_gap_seconds < MAX_DETECTOR_GAP_SECONDS
    assert result.max_detector_gap_seconds > 0.5  # longer than the blank state itself


def test_a_state_longer_than_the_sentinel_period_is_observed_even_by_a_blind_gate(
    three_state_video,
):
    # The other side of the same guarantee, and the one the real
    # fixtures rely on: state B holds for 0.9s from 1.0s, so a detector
    # that looks at least once a second cannot miss it -- with no help
    # from the cheap gate at all.
    result = _run(three_state_video, cheap_signature_fn=_blind_cheap_gate)

    assert any(t >= 1.0 for t, _ in result.observations)
    assert result.representative_count >= 1


def test_state_identity_comes_from_the_detector_signature_not_the_cheap_gate(
    three_state_video,
):
    # A cheap gate that screams "changed!" on every frame may only cause
    # MORE detector calls -- it must not manufacture extra subtitle
    # states, because grouping is decided by the Beta-S signature alone.
    noisy = _run(
        three_state_video,
        cheap_signature_fn=lambda mask, stability: np.random.default_rng(
            mask.sum()
        ).random((8, 8))
        > 0.5,
    )

    assert [g.state_kind for g in noisy.groups] == ["subtitle", "blank", "subtitle"]
    assert noisy.representative_count == 2


def test_a_blind_cheap_gate_cannot_permanently_skip_a_stretch_of_video(
    three_state_video,
):
    # The recall-safety contract: even when the cheap gate never fires,
    # the detector still gets a look, bounded by the maximum gap.
    result = _run(three_state_video, cheap_signature_fn=_blind_cheap_gate)

    assert result.detector_invocations >= 2
    assert result.trigger_counts.get("sentinel", 0) >= 1
    assert result.max_detector_gap_seconds <= MAX_DETECTOR_GAP_SECONDS + 1.0 / _SAMPLING_FPS


def test_the_detector_gap_stays_bounded_with_the_real_cheap_gate(three_state_video):
    result = _run(three_state_video)

    assert result.max_detector_gap_seconds <= MAX_DETECTOR_GAP_SECONDS + 1.0 / _SAMPLING_FPS


def test_a_cheap_evidence_change_schedules_a_detector_call_near_the_change(
    three_state_video,
):
    result = _run(three_state_video)

    candidates = [t for t, reason in result.observations if reason == "candidate"]
    # The second caption appears at 1.0s. The cheap gate must schedule a
    # detector look promptly after it, without waiting for the sentinel.
    assert any(1.0 <= t < 1.0 + MAX_DETECTOR_GAP_SECONDS for t in candidates), result.observations


# --- bookkeeping ---------------------------------------------------------


def test_the_cascade_reports_the_baseline_it_is_being_compared_against(
    three_state_video,
):
    result = _run(three_state_video)

    # The baseline is one detector call per sampled frame -- what Beta-S
    # does today, and the number the cost gate is scored against.
    assert result.baseline_detector_invocations == result.sampled_frame_count
    assert result.detector_wall_seconds >= 0.0
    assert result.cheap_gate_wall_seconds >= 0.0


def test_the_cascade_rejects_a_non_positive_sampling_fps(three_state_video):
    with pytest.raises(ValueError):
        _run(three_state_video, sampling_fps=0.0)
