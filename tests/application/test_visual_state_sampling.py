import numpy as np

from glyphcue.application.visual_state_sampling import (
    SampledFrame,
    group_visual_states,
    is_blank_signature,
    signature_distance,
    subtitle_visual_signature,
)

_BLANK_FRAME = np.full((20, 60, 3), 20, dtype=np.uint8)


def _text_frame(offset: int = 0, width: int = 60, height: int = 20) -> np.ndarray:
    """A synthetic "text-like" ROI frame: a block of alternating-pixel
    vertical stripes (real, detectable luminance edges) against a flat
    background, shifted by `offset` columns to simulate different text."""
    frame = np.full((height, width, 3), 20, dtype=np.uint8)
    stripe_start = 5 + offset
    stripe_end = min(width - 5, stripe_start + 20)
    frame[8:14, stripe_start:stripe_end:2] = 230
    return frame


def test_blank_frame_has_a_near_zero_density_signature():
    signature = subtitle_visual_signature(_BLANK_FRAME)

    assert is_blank_signature(signature) is True


def test_text_frame_is_not_blank():
    signature = subtitle_visual_signature(_text_frame())

    assert is_blank_signature(signature) is False


def test_identical_text_signatures_have_zero_distance():
    a = subtitle_visual_signature(_text_frame())
    b = subtitle_visual_signature(_text_frame())

    assert signature_distance(a, b) == 0.0


def test_different_text_signatures_have_nonzero_distance():
    a = subtitle_visual_signature(_text_frame(offset=0))
    b = subtitle_visual_signature(_text_frame(offset=30))

    assert signature_distance(a, b) > 0.0


def test_mismatched_shapes_are_maximally_distant():
    a = np.zeros((5, 5), dtype=bool)
    b = np.zeros((6, 6), dtype=bool)

    assert signature_distance(a, b) == 1.0


def _sampled(index: int, timestamp: float, frame: np.ndarray) -> SampledFrame:
    signature = subtitle_visual_signature(frame)
    return SampledFrame(
        index=index,
        timestamp=timestamp,
        signature=signature,
        is_blank=is_blank_signature(signature),
    )


def test_a_single_stable_run_collapses_to_one_group_and_middle_representative():
    frames = [_sampled(i, float(i), _text_frame()) for i in range(5)]

    result = group_visual_states(frames)

    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.state_kind == "subtitle"
    assert group.frame_count == 5
    assert group.representative_index == 2  # middle of 0..4


def test_a_real_text_change_starts_a_new_group():
    frames = [_sampled(i, float(i), _text_frame(offset=0)) for i in range(3)]
    frames += [_sampled(i, float(i), _text_frame(offset=30)) for i in range(3, 6)]

    result = group_visual_states(frames)

    assert len(result.groups) == 2
    assert result.groups[0].frame_count == 3
    assert result.groups[1].frame_count == 3


def test_blank_frames_form_their_own_explicit_state_group():
    frames = [_sampled(i, float(i), _text_frame()) for i in range(3)]
    frames += [_sampled(i, float(i), _BLANK_FRAME) for i in range(3, 6)]
    frames += [_sampled(i, float(i), _text_frame(offset=30)) for i in range(6, 9)]

    result = group_visual_states(frames)

    assert [g.state_kind for g in result.groups] == ["subtitle", "blank", "subtitle"]
    assert result.subtitle_group_count == 2
    assert result.blank_group_count == 1


def test_anchor_comparison_does_not_drift_across_a_long_stable_run():
    # Every frame stays within threshold of the FIRST frame (the anchor),
    # even though a naive frame-to-frame chain could accumulate drift
    # across many small steps -- this is the failure mode being tested.
    frames = [_sampled(i, float(i), _text_frame()) for i in range(50)]

    result = group_visual_states(frames)

    assert len(result.groups) == 1


def test_group_distance_threshold_controls_sensitivity():
    frames = [_sampled(0, 0.0, _text_frame(offset=0))]
    frames.append(_sampled(1, 1.0, _text_frame(offset=8)))

    permissive = group_visual_states(frames, group_distance_threshold=0.9)
    strict = group_visual_states(frames, group_distance_threshold=0.0001)

    assert len(permissive.groups) == 1
    assert len(strict.groups) == 2


def test_empty_input_produces_no_groups():
    result = group_visual_states([])

    assert result.groups == []
    assert result.representative_timestamps == []


def test_representative_timestamps_excludes_blank_groups():
    frames = [_sampled(i, float(i), _text_frame()) for i in range(2)]
    frames += [_sampled(i, float(i), _BLANK_FRAME) for i in range(2, 4)]

    result = group_visual_states(frames)

    assert result.representative_timestamps == [1.0]


def test_grouping_uses_the_plain_signature_distance_by_default():
    # Pins the Alpha-family default: injecting a custom comparison is an
    # additive option, never a change to existing grouping behavior.
    frames = [_sampled(i, float(i), _text_frame(offset=0)) for i in range(3)]
    frames += [_sampled(i, float(i), _text_frame(offset=30)) for i in range(3, 6)]

    assert len(group_visual_states(frames).groups) == 2


def test_an_injected_distance_that_sees_everything_as_identical_yields_one_group():
    frames = [_sampled(i, float(i), _text_frame(offset=0)) for i in range(3)]
    frames += [_sampled(i, float(i), _text_frame(offset=30)) for i in range(3, 6)]

    result = group_visual_states(frames, distance=lambda a, b: 0.0)

    assert len(result.groups) == 1


def test_an_injected_distance_that_sees_everything_as_different_splits_every_frame():
    frames = [_sampled(i, float(i), _text_frame()) for i in range(4)]

    result = group_visual_states(frames, distance=lambda a, b: 1.0)

    assert len(result.groups) == 4
