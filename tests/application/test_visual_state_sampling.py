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


def test_characterizes_why_no_grouping_rule_can_separate_the_swallowed_state():
    """CHARACTERIZATION of the M11 Offline Grouping Robustness Gate's
    STOP result. This is a measured property of the EVIDENCE, not a
    limitation of any particular segmentation policy.

    The gate asked whether an offline, non-greedy or look-back
    segmentation rule could give the swallowed short state its own
    representative while still resisting slow drift across a long stable
    run. Four structural rules were compared on cached real observation
    sequences (18 fixture x ROI-variant replays over sample_a/b/d):
    greedy anchor, anchor AND chained, contiguous complete-linkage
    agglomeration, and a parameter-free recursive gap split accepting a
    cut only when the two halves are further from each other than either
    is from itself. None of them recovered the state; the only variants
    that appeared to were degenerate -- allowing a half of ONE member
    forces its diameter to zero, so any two non-identical observations
    separate, which shatters real states (up to 6 representatives for
    one real state) rather than segmenting them.

    The numbers below are why, taken from the contaminated group in the
    real hand-drawn-tighter replay (7 observations: 4 from the longer
    preceding state, 3 from the short state). Ranking every candidate
    cut by its separation margin puts the REAL transition first -- the
    rule looks in the right place -- but its margin is NEGATIVE: under
    that ROI the short state's own three observations scatter by MORE
    (0.1051, itself above the 0.10 grouping threshold) than they are
    separated from the neighbouring state (0.0948).

    So by any internal-consistency measure these observations are more
    like their neighbour than like each other. No segmentation policy --
    greedy or offline, threshold-based or scale-free -- can separate
    clusters whose within-scatter exceeds their between-distance; that
    is a discriminability property of the Beta-S signature under a
    perturbed ROI, one layer upstream of grouping. Fixing it therefore
    requires the signature (or the threshold it feeds), which this round
    is explicitly scoped out of.
    """
    # Measured on the real replay: index 0-3 are the longer preceding
    # state, 4-6 the short state that gets swallowed.
    to_anchor = [0.0, 0.0246, 0.0296, 0.0627, 0.0953, 0.0967, 0.0989]
    measured = {
        (1, 2): 0.0100, (1, 3): 0.0400, (2, 3): 0.0400,  # within the long state
        (4, 5): 0.0240, (5, 6): 0.1051, (4, 6): 0.0900,  # within the short state
        (3, 4): 0.0948,  # the closest pair across the real transition
    }
    for index, distance in enumerate(to_anchor):
        measured[(0, index)] = distance

    def _forensic_distance(a, b):
        i, j = sorted((a[0], b[0]))
        if i == j:
            return 0.0
        return measured.get((i, j), 0.30)

    frames = [_labeled_sampled(i, float(i), i) for i in range(7)]

    def _diameter(members):
        return max(
            (
                _forensic_distance(x.signature, y.signature)
                for a, x in enumerate(members)
                for y in members[a + 1 :]
            ),
            default=0.0,
        )

    # 1. The production rule swallows the state: every one of its
    #    observations sits under the threshold from the anchor.
    result = group_visual_states(
        frames,
        group_distance_threshold=0.10,
        distance=_forensic_distance,
        representative=lambda members: stable_representative(
            members, distance=_forensic_distance
        ),
    )
    assert len(result.groups) == 1
    assert all(distance <= 0.10 for distance in to_anchor)

    # 2. The real transition is where a scale-free rule looks FIRST --
    #    it maximizes the separation margin among all candidate cuts.
    def _margin(cut):
        left, right = frames[:cut], frames[cut:]
        between = min(
            _forensic_distance(x.signature, y.signature) for x in left for y in right
        )
        return between - max(_diameter(left), _diameter(right))

    cuts = range(2, len(frames) - 1)
    assert max(cuts, key=_margin) == 4  # the real transition, ranked first

    # 3. ...and it still must not cut there, because the short state is
    #    internally MORE scattered than it is separated from its
    #    neighbour. This inequality, not the policy, is the blocker.
    assert _diameter(frames[4:]) > min(
        _forensic_distance(x.signature, y.signature)
        for x in frames[:4]
        for y in frames[4:]
    )
    assert _margin(4) < 0


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
