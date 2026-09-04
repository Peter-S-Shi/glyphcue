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
from glyphcue.application.subtitle_stable_signature import downsampled_edge_mask
from glyphcue.application.text_anchored_region_mask import (
    TextAnchoredRegionMask,
    cheap_grid_mask,
)
from glyphcue.application.visual_state_sampling import SampledFrame, group_visual_states
from glyphcue.domain.roi import ROI

_WIDTH, _HEIGHT = 320, 120
_FULL_FRAME_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)
_SAMPLING_FPS = 5.0

# The caption band, and a detector box over it.
_CAPTION_TOP, _CAPTION_BOTTOM = 86, 110
_CAPTION_BOX = [[[40, _CAPTION_TOP], [280, _CAPTION_TOP], [280, _CAPTION_BOTTOM], [40, _CAPTION_BOTTOM]]]


def _poly(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# --- mask geometry -------------------------------------------------------


def test_the_mask_lands_on_the_detected_text_and_not_elsewhere():
    roi_shape = (_HEIGHT, _WIDTH)
    grid = cheap_grid_mask(_CAPTION_BOX, roi_shape)
    reference = downsampled_edge_mask(np.zeros((*roi_shape, 3), dtype=np.uint8))

    assert grid.shape == reference.shape
    rows = np.flatnonzero(grid.any(axis=1))
    # The caption occupies the bottom fifth of the ROI; the mask must not
    # reach the presenter's half of the frame.
    assert rows.min() > grid.shape[0] * 0.5
    assert grid.mean() < 0.5


def test_the_mask_includes_a_padding_margin_around_the_box():
    roi_shape = (_HEIGHT, _WIDTH)
    padded = cheap_grid_mask(_CAPTION_BOX, roi_shape)
    unpadded = cheap_grid_mask(_CAPTION_BOX, roi_shape, padding_to_line_height=0.0)

    assert padded.sum() > unpadded.sum()
    assert (padded | unpadded == padded).all()  # padding only grows the region


def test_two_caption_lines_produce_one_mask_covering_both():
    roi_shape = (_HEIGHT, _WIDTH)
    two_lines = [_poly(40, 60, 280, 80), _poly(40, 90, 280, 110)]

    grid = cheap_grid_mask(two_lines, roi_shape)
    top_only = cheap_grid_mask([_poly(40, 60, 280, 80)], roi_shape)

    assert grid.sum() > top_only.sum()


# --- the fallback that keeps blank -> text sensitive ---------------------


def test_with_no_confirmed_text_the_gate_still_sees_the_whole_roi():
    mask = TextAnchoredRegionMask()
    cheap = np.ones((20, 40), dtype=bool)

    assert mask.apply(cheap) is cheap
    assert not mask.has_confirmed_text


def test_an_observed_blank_frame_clears_the_mask_instead_of_keeping_a_stale_one():
    mask = TextAnchoredRegionMask()
    mask.update(_CAPTION_BOX, (_HEIGHT, _WIDTH))
    assert mask.has_confirmed_text

    mask.update([], (_HEIGHT, _WIDTH))

    assert not mask.has_confirmed_text
    cheap = np.ones((20, 40), dtype=bool)
    assert mask.apply(cheap) is cheap


def test_a_shape_mismatch_falls_back_rather_than_masking_wrongly():
    mask = TextAnchoredRegionMask()
    mask.update(_CAPTION_BOX, (_HEIGHT, _WIDTH))

    cheap = np.ones((7, 9), dtype=bool)

    assert mask.apply(cheap) is cheap


def test_masking_only_ever_removes_evidence_outside_the_text_region():
    mask = TextAnchoredRegionMask()
    mask.update(_CAPTION_BOX, (_HEIGHT, _WIDTH))
    grid = cheap_grid_mask(_CAPTION_BOX, (_HEIGHT, _WIDTH))
    cheap = np.ones(grid.shape, dtype=bool)

    applied = mask.apply(cheap)

    assert applied.sum() == grid.sum()
    assert (applied & ~grid).sum() == 0


# --- end to end on a talking-head-shaped fixture -------------------------


def _frame(distractor_shift: int, caption_spacing: int | None, caption_top: int = _CAPTION_TOP):
    """A moving high-contrast object in the upper frame (the presenter)
    plus an optional static caption in the lower band."""
    frame = np.full((_HEIGHT, _WIDTH, 3), 210, dtype=np.uint8)
    for column in range(distractor_shift % 24, _WIDTH, 24):
        frame[10:70, column : column + 9] = 40
    if caption_spacing is not None:
        frame[caption_top + 4 : caption_top + 20, 40:280:caption_spacing] = 20
    return frame


def _write_fixture(path: Path, plan) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width, stream.height = _WIDTH, _HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0

    for index, pts_ms in enumerate(range(0, 4000, 100)):
        array = plan(index, pts_ms)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


class _BandDetector:
    """Reports a box wherever the frame actually has caption-band ink --
    localization only, exactly like the real detector's role here."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, roi_frame: np.ndarray):
        self.calls += 1
        luminance = roi_frame.mean(axis=2) if roi_frame.ndim == 3 else roi_frame
        boxes = []
        for top in (_CAPTION_TOP, 10):
            band = luminance[top + 2 : top + 22, 30:290]
            # Caption ink is 20, the moving distractor is 40: a detector
            # that reported the presenter as text would make this whole
            # fixture meaningless.
            if bool((band < 30).any()):
                boxes.append(_poly(40, top, 280, top + 24))
        return boxes


@pytest.fixture
def held_caption_over_motion(tmp_path) -> Path:
    """A caption held for the whole clip while the upper frame moves --
    the sample_d/sample_a shape, reduced to its essentials."""
    path = tmp_path / "held_over_motion.mp4"
    _write_fixture(path, lambda index, pts: _frame(index * 3, caption_spacing=6))
    return path


def _run(video, detect, **kwargs):
    return run_hybrid_cascade_dry_run(
        video, ProcessingRange(), _FULL_FRAME_ROI, _SAMPLING_FPS, detect=detect, **kwargs
    )


def test_narrowing_to_the_text_region_stops_scheduling_on_presenter_motion(
    held_caption_over_motion,
):
    # The whole point of Hybrid-T: the caption never changes, so the
    # detector should be running on sentinels, not on the moving object
    # that shares the ROI with it.
    baseline = _run(held_caption_over_motion, _BandDetector())
    hybrid_t = _run(
        held_caption_over_motion, _BandDetector(), cheap_region_mask=TextAnchoredRegionMask()
    )

    assert hybrid_t.detector_invocations < baseline.detector_invocations
    assert hybrid_t.trigger_counts.get("candidate", 0) < baseline.trigger_counts.get("candidate", 0)


def test_narrowing_does_not_cost_state_identity(held_caption_over_motion):
    # One caption held throughout stays one state either way -- the mask
    # schedules, it does not decide.
    hybrid_t = _run(
        held_caption_over_motion, _BandDetector(), cheap_region_mask=TextAnchoredRegionMask()
    )

    assert hybrid_t.representative_count == 1


@pytest.fixture
def caption_changing_in_place(tmp_path) -> Path:
    """Same caption band, different text from 2.0s -- a change INSIDE the
    mask, which the narrowed gate must still catch promptly."""
    path = tmp_path / "changing_in_place.mp4"
    _write_fixture(
        path,
        lambda index, pts: _frame(index * 3, caption_spacing=6 if pts < 2000 else 13),
    )
    return path


def test_a_change_inside_the_text_region_is_still_scheduled_promptly(
    caption_changing_in_place,
):
    result = _run(
        caption_changing_in_place, _BandDetector(), cheap_region_mask=TextAnchoredRegionMask()
    )

    candidates = [t for t, reason in result.observations if reason == "candidate"]
    assert any(2.0 <= t < 2.0 + MAX_DETECTOR_GAP_SECONDS for t in candidates), result.observations
    assert result.representative_count == 2


@pytest.fixture
def caption_moving_to_a_new_position(tmp_path) -> Path:
    """The caption jumps out of the masked band at 2.0s -- the case the
    narrowed gate is structurally blind to."""
    path = tmp_path / "moving_caption.mp4"
    _write_fixture(
        path,
        lambda index, pts: _frame(
            index * 3, caption_spacing=6, caption_top=_CAPTION_TOP if pts < 2000 else 10
        ),
    )
    return path


def test_a_caption_that_moves_out_of_the_mask_is_still_caught_by_the_sentinel(
    caption_moving_to_a_new_position,
):
    # CHARACTERIZATION of the risk narrowing introduces: the cheap gate
    # cannot see a caption that leaves its mask, so recovery is the
    # sentinel's job -- bounded latency, never a lost state.
    result = _run(
        caption_moving_to_a_new_position,
        _BandDetector(),
        cheap_region_mask=TextAnchoredRegionMask(),
    )

    # One grid interval of slack for the sentinel's own quantization, and
    # a second because decoded timestamps are floats: a nominal 1.0s gap
    # can measure as 0.9999 and postpone the sentinel by one grid point.
    assert result.max_detector_gap_seconds <= MAX_DETECTOR_GAP_SECONDS + 2.0 / _SAMPLING_FPS
    assert any(t >= 2.0 for t, _ in result.observations)
    assert result.representative_count >= 2


@pytest.fixture
def caption_appearing_after_blank(tmp_path) -> Path:
    path = tmp_path / "blank_then_text.mp4"
    _write_fixture(
        path,
        lambda index, pts: _frame(index * 3, caption_spacing=None if pts < 2000 else 6),
    )
    return path


def test_characterizes_sparse_observation_placing_a_representative_outside_its_state():
    """CHARACTERIZATION of how Hybrid-T lost sample_a state 1.

    The frozen representative rule picks the temporally MIDDLE member of
    a group. Under dense 5 fps observation a held state contributes many
    members, so the middle lands well inside it. Under sparse scheduling
    a state can contribute only ONE observation; if the group also picks
    up the next scheduled look after the state has ended, "middle" of two
    members is the LATER one -- and the representative lands outside the
    state that earned it.

    Measured on sample_a: state 1 (27.00-27.77s) WAS observed, at 27.0 by
    the bootstrap, but its group ran 27.0-28.0 and the representative
    came out at 28.0 -- in the gap before state 2. The state was
    observed and still scored as swallowed.

    This is a property of sparse scheduling meeting a rule designed for
    dense sampling, not of the region mask itself; it is recorded here
    rather than worked around, because changing the representative rule
    is outside this round.
    """
    state_frame = SampledFrame(
        index=0, timestamp=27.0, signature=np.ones((4, 4), dtype=bool), is_blank=False
    )
    later_frame = SampledFrame(
        index=1, timestamp=28.0, signature=np.ones((4, 4), dtype=bool), is_blank=False
    )

    groups = group_visual_states([state_frame, later_frame]).groups

    assert len(groups) == 1
    assert groups[0].representative_timestamp == 28.0  # not the 27.0 that saw the state


def test_blank_to_text_keeps_its_baseline_sensitivity(caption_appearing_after_blank):
    # With no confirmed text there is nothing to anchor to, so the gate
    # reverts to the whole ROI and a caption appearing is seen the same
    # way the baseline cascade saw it.
    result = _run(
        caption_appearing_after_blank,
        _BandDetector(),
        cheap_region_mask=TextAnchoredRegionMask(),
    )

    assert result.blank_group_count >= 1
    assert result.representative_count >= 1
    assert any(t >= 2.0 for t, _ in result.observations)
