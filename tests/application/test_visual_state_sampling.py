import numpy as np

from glyphcue.application.sparse_observation_semantics import stable_representative
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


def _labeled_sampled(index: int, timestamp: float, label: str) -> SampledFrame:
    """A synthetic sample whose "signature" is just a state label, for
    tests that inject a custom `distance` keyed on that label rather
    than deriving distance from real pixels."""
    return SampledFrame(index=index, timestamp=timestamp, signature=(label,), is_blank=False)


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


def test_characterizes_a_short_intervening_state_being_swallowed_by_anchor_based_grouping():
    """CHARACTERIZATION of a real M11 production-integration forensic
    finding (transition-overlay false-negative diagnosis, sample_d), not
    a bug this round fixes.

    The anchor-based design in `test_anchor_comparison_does_not_drift_
    across_a_long_stable_run` above is deliberately resistant to SLOW
    drift across a long real state: every candidate is compared to the
    group's FIRST member, not the previous one, so many small steps can
    never silently accumulate past the threshold.

    That same design has a dual failure mode this test pins: a SHORT
    real state wedged between two longer ones can be swallowed whole if
    each of its own samples' distance to the OLDER neighbor's anchor
    individually stays under threshold, even though the content
    genuinely changed. Once that happens, the closed group is dominated
    by the longer state's members, so a distance-based medoid
    representative (`stable_representative`) also picks one of THEM --
    the short state ends up with zero representative anywhere in the
    run, not merely mislabeled.

    Forensic origin: replaying the exact frozen sample_d fixture and a
    real detector/Beta-S signature under a plausibly hand-drawn (tighter
    than the research ROI) crop reproduced this precisely -- a real
    ~1.0s subtitle state, sandwiched between two longer ones, whose
    only two clean detector samples measured 0.095-0.097 distance to the
    PRECEDING state's anchor (just under the frozen 0.10 grouping
    threshold) while the state that followed measured 0.105 (just over
    it) -- confirmed via real OCR recognition on the exact swallowed
    frames (independently legible, high confidence) and via a real,
    unmodified `build_hybrid_ocr_evidence_job` run against the exact
    frozen ROI (which does NOT reproduce this -- it stayed on the
    resistant side of the same threshold there). Scheduling and
    recognition were both ruled out as the failing layer; only grouping
    was.

    A structural fix was investigated and DELIBERATELY NOT applied:
    requiring a candidate to also stay within threshold of the group's
    most recent member (in addition to the anchor) only splits the group
    one step later in the reproduced case and still fails to recover the
    swallowed state, because the swallowed state's own samples measure
    just as close to its long neighbor as to each other. Any fix that
    actually recovers it requires either moving the 0.10 threshold or
    changing the Beta-S signature itself -- both explicitly out of scope
    for a diagnosis round that must not reopen the frozen Research Gate.
    """
    # Distances chosen to match what the real forensic measured, not
    # picked to make this pass: same-state ~0.02-0.03, the swallowed
    # state's distance to its OLDER neighbor is just under threshold
    # (0.095), and its distance to the state that follows is just over
    # it (0.105) -- both matching the measured values almost exactly.
    def _label(signature):
        return signature[0]

    def _forensic_distance(a, b):
        la, lb = _label(a), _label(b)
        if la == lb:
            return 0.03
        pair = {la, lb}
        if pair == {"A", "B"}:
            return 0.095
        if pair == {"B", "C"}:
            return 0.105
        return 0.30

    frames = (
        [_labeled_sampled(i, float(i), "A") for i in range(4)]  # the longer preceding state
        + [_labeled_sampled(i, float(i), "B") for i in range(4, 6)]  # the short swallowed state
        + [_labeled_sampled(i, float(i), "C") for i in range(6, 10)]  # the following state
    )

    result = group_visual_states(
        frames,
        group_distance_threshold=0.10,  # the production hybrid job's real threshold
        distance=_forensic_distance,
        representative=lambda members: stable_representative(members, distance=_forensic_distance),
    )

    assert len(result.groups) == 2  # not 3: A+B merged into one group
    assert result.groups[0].frame_count == 6  # all 4 A's AND both B's
    # The swallowed state's own timestamps (4.0, 5.0) never surface as a
    # representative anywhere in the run -- not mislabeled, genuinely gone.
    assert 4.0 not in result.representative_timestamps
    assert 5.0 not in result.representative_timestamps


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
