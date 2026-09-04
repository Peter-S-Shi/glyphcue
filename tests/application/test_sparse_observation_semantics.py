from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.application.hybrid_cascade_dry_run import run_hybrid_cascade_dry_run
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.sparse_observation_semantics import stable_representative
from glyphcue.application.visual_state_sampling import (
    SampledFrame,
    group_visual_states,
)
from glyphcue.domain.roi import ROI

_WIDTH, _HEIGHT = 240, 48
_FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)
_SAMPLING_FPS = 5.0


def _frame(timestamp: float, signature: np.ndarray, index: int = 0) -> SampledFrame:
    return SampledFrame(
        index=index, timestamp=timestamp, signature=signature, is_blank=False
    )


def _sig(*rows: str) -> np.ndarray:
    return np.array([[c == "#" for c in row] for row in rows], dtype=bool)


# --- failure mode 1: an observed state losing its own representative -----


def test_a_state_observed_once_keeps_a_representative_inside_itself():
    """The sample_a state 1 regression, at the seam that caused it.

    Sparse scheduling gave state 1 (27.00-27.77s) exactly one
    observation, at 27.0. The group then also picked up the next
    scheduled look at 28.0, and the middle-member rule -- written for
    dense sampling, where a group has many members -- put the
    representative at 28.0, in the gap AFTER the state. The state was
    observed and still scored as swallowed.
    """
    identical = _sig("##..", "##..")
    members = [_frame(27.0, identical, 0), _frame(28.0, identical, 1)]

    groups = group_visual_states(members, representative=stable_representative).groups

    assert len(groups) == 1
    assert groups[0].representative_timestamp == 27.0


def test_the_representative_is_the_most_typical_observation_not_the_middle_one():
    # "Stable" has to mean something measurable: the representative is
    # the member that agrees most with the rest of the group, so a
    # transition-adjacent or partially-rendered frame cannot be chosen
    # merely for sitting at the temporal midpoint.
    typical = _sig("###.", "###.")
    outlier = _sig("...#", "#...")
    members = [
        _frame(1.0, typical, 0),
        _frame(2.0, outlier, 1),  # the temporal middle
        _frame(3.0, typical, 2),
    ]

    groups = group_visual_states(
        members, group_distance_threshold=1.0, representative=stable_representative
    ).groups

    assert groups[0].representative_timestamp in (1.0, 3.0)


def test_ties_are_broken_towards_the_observation_that_established_the_state():
    # With nothing to separate the candidates, the earliest observation
    # is the one guaranteed to lie inside the state that produced the
    # group -- later members may already belong to the next state's
    # neighbourhood, which is exactly how sample_a state 1 was lost.
    identical = _sig("#.#.", ".#.#")
    members = [_frame(5.0, identical, 0), _frame(6.0, identical, 1), _frame(7.0, identical, 2)]

    groups = group_visual_states(members, representative=stable_representative).groups

    assert groups[0].representative_timestamp == 5.0


def test_the_default_representative_rule_is_left_untouched():
    # The frozen baseline must stay byte-identical so every previous
    # round's numbers remain comparable.
    identical = _sig("##..", "##..")
    members = [_frame(27.0, identical, 0), _frame(28.0, identical, 1)]

    groups = group_visual_states(members).groups

    assert groups[0].representative_timestamp == 28.0


def test_a_blank_group_still_yields_a_representative():
    blank = np.zeros((2, 4), dtype=bool)
    members = [
        SampledFrame(index=0, timestamp=1.0, signature=blank, is_blank=True),
        SampledFrame(index=1, timestamp=2.0, signature=blank, is_blank=True),
    ]

    groups = group_visual_states(members, representative=stable_representative).groups

    assert groups[0].state_kind == "blank"
    assert groups[0].representative_timestamp == 1.0


def test_stable_representative_of_a_single_observation_is_that_observation():
    only = _frame(9.0, _sig("#..#"), 0)

    assert stable_representative([only]) is only


# --- failure mode 2: the tail of the processing range never observed ----


def _text_frame(spacing: int) -> np.ndarray:
    frame = np.full((_HEIGHT, _WIDTH, 3), 230, dtype=np.uint8)
    frame[12:30, 20:180:spacing] = 20
    return frame


def _write_fixture(path: Path, plan) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width, stream.height = _WIDTH, _HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0
    for pts_ms in range(0, 3000, 100):
        frame = av.VideoFrame.from_ndarray(plan(pts_ms), format="rgb24").reformat(
            format="yuv420p"
        )
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


@pytest.fixture
def late_short_caption(tmp_path) -> Path:
    """One caption for most of the clip, then a DIFFERENT one for the
    final 0.2s -- the sample_b state 5 shape: a real state shorter than
    the sentinel interval, sitting at the very end of the window."""
    path = tmp_path / "late_short_caption.mp4"
    _write_fixture(path, lambda pts: _text_frame(4 if pts < 2800 else 11))
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


def _blind_gate(edge_mask, stability):
    return np.zeros((4, 4), dtype=bool)


def _run(video, detect=None, **kwargs):
    return run_hybrid_cascade_dry_run(
        video,
        ProcessingRange(),
        _FULL_FRAME_ROI,
        _SAMPLING_FPS,
        detect=detect if detect is not None else _FakeDetector(),
        **kwargs,
    )


def test_the_end_of_the_processing_range_is_always_observed(late_short_caption):
    result = _run(late_short_caption, cheap_signature_fn=_blind_gate, guarantee_tail=True)

    last_observation = result.observations[-1][0]
    assert last_observation >= result.media_duration_seconds - 1.0 / _SAMPLING_FPS
    assert result.trigger_counts.get("boundary", 0) == 1


def test_the_tail_guarantee_costs_at_most_one_extra_detector_call(late_short_caption):
    without = _run(late_short_caption, cheap_signature_fn=_blind_gate)
    with_tail = _run(late_short_caption, cheap_signature_fn=_blind_gate, guarantee_tail=True)

    assert with_tail.detector_invocations - without.detector_invocations == 1


def test_no_extra_call_when_the_last_sampled_frame_was_already_observed(
    late_short_caption,
):
    # A gate that fires on everything already observes the tail, so the
    # guarantee must be a no-op rather than a duplicate call.
    hysterical = _run(
        late_short_caption,
        cheap_signature_fn=lambda mask, stability: np.random.default_rng(mask.sum()).random(
            (8, 8)
        )
        > 0.5,
        guarantee_tail=True,
    )

    assert hysterical.trigger_counts.get("boundary", 0) == 0


def test_a_short_state_at_the_end_of_the_window_survives_a_blind_cheap_gate(
    late_short_caption,
):
    # The two rules together on the sample_b shape: the tail guarantee
    # observes the final state, and the representative rule keeps that
    # observation inside it.
    result = _run(
        late_short_caption,
        cheap_signature_fn=_blind_gate,
        guarantee_tail=True,
        representative=stable_representative,
    )

    assert result.representative_count >= 2
    assert result.representative_timestamps[-1] >= 2.8 - 1.0 / _SAMPLING_FPS


def test_the_tail_guarantee_is_off_by_default(late_short_caption):
    result = _run(late_short_caption, cheap_signature_fn=_blind_gate)

    assert result.trigger_counts.get("boundary", 0) == 0
