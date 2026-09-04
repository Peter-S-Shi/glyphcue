import numpy as np

from glyphcue.application.subtitle_stable_signature import (
    CenteredEdgeStabilityIndex,
    EdgeStabilityBuffer,
    downsampled_edge_mask,
    filter_large_components,
    subtitle_stable_signature,
)

_BLANK_FRAME = np.full((20, 60, 3), 20, dtype=np.uint8)


def _text_frame(offset: int = 0, width: int = 60, height: int = 20) -> np.ndarray:
    frame = np.full((height, width, 3), 20, dtype=np.uint8)
    stripe_start = 5 + offset
    stripe_end = min(width - 2, stripe_start + 20)
    frame[8:14, stripe_start:stripe_end:2] = 230
    return frame


def test_blank_frame_has_no_edges():
    mask = downsampled_edge_mask(_BLANK_FRAME)

    assert not mask.any()


def test_text_frame_has_edges():
    mask = downsampled_edge_mask(_text_frame())

    assert mask.any()


def test_stability_buffer_reports_full_persistence_for_an_unchanging_edge():
    mask = downsampled_edge_mask(_text_frame())
    buffer = EdgeStabilityBuffer(window_seconds=1.0)

    for t in (0.0, 0.1, 0.2, 0.3):
        buffer.push(t, mask)

    ratio = buffer.persistence_ratio()
    assert ratio is not None
    np.testing.assert_array_equal(ratio[mask], np.ones(mask.sum()))


def test_stability_buffer_reports_partial_persistence_for_a_flickering_edge():
    on = downsampled_edge_mask(_text_frame())
    off = np.zeros_like(on)
    buffer = EdgeStabilityBuffer(window_seconds=1.0)

    buffer.push(0.0, on)
    buffer.push(0.1, off)
    buffer.push(0.2, on)
    buffer.push(0.3, off)

    ratio = buffer.persistence_ratio()
    assert ratio[on].mean() == pytest_approx(0.5)


def pytest_approx(value, tol=1e-6):
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) < tol

    return _Approx()


def test_stability_buffer_drops_entries_outside_the_time_window():
    mask = downsampled_edge_mask(_text_frame())
    buffer = EdgeStabilityBuffer(window_seconds=0.2)

    buffer.push(0.0, mask)
    buffer.push(0.5, np.zeros_like(mask))  # far later, outside a 0.2s trailing window

    ratio = buffer.persistence_ratio()
    # Only the second (all-zero) push should remain in a 0.2s trailing window at t=0.5.
    assert ratio.max() == 0.0


def test_empty_buffer_reports_no_persistence():
    buffer = EdgeStabilityBuffer(window_seconds=1.0)

    assert buffer.persistence_ratio() is None


def test_large_connected_component_is_filtered_out():
    mask = np.zeros((20, 20), dtype=bool)
    mask[2:18, 2:18] = True  # one huge blob, most of the grid

    filtered = filter_large_components(mask, max_component_fraction=0.12)

    assert not filtered.any()


def test_small_connected_components_survive_the_filter():
    mask = np.zeros((20, 20), dtype=bool)
    mask[3, 3] = True
    mask[3, 4] = True  # a 2-cell stroke fragment, well under the size cap
    mask[15, 15] = True  # an isolated 1-cell fragment

    filtered = filter_large_components(mask, max_component_fraction=0.12)

    np.testing.assert_array_equal(filtered, mask)


def test_filter_is_a_no_op_on_an_all_false_mask():
    mask = np.zeros((10, 10), dtype=bool)

    filtered = filter_large_components(mask)

    assert not filtered.any()


def test_subtitle_stable_signature_keeps_a_persistently_held_small_stroke():
    text_mask = downsampled_edge_mask(_text_frame())
    buffer = EdgeStabilityBuffer(window_seconds=1.0)
    for t in (0.0, 0.1, 0.2, 0.3, 0.4):
        buffer.push(t, text_mask)

    combined = subtitle_stable_signature(text_mask, buffer)

    assert combined.any()


def test_subtitle_stable_signature_drops_an_edge_that_never_persisted():
    text_mask = downsampled_edge_mask(_text_frame())
    buffer = EdgeStabilityBuffer(window_seconds=1.0)
    # Buffer history shows this edge was essentially never present before now.
    buffer.push(0.0, np.zeros_like(text_mask))
    buffer.push(0.1, np.zeros_like(text_mask))
    buffer.push(0.2, np.zeros_like(text_mask))

    combined = subtitle_stable_signature(text_mask, buffer, persistence_threshold=0.6)

    assert not combined.any()


def test_centered_index_sees_a_symmetric_window_around_the_target_timestamp():
    text_mask = downsampled_edge_mask(_text_frame())
    entries = [(t, text_mask) for t in (0.0, 0.1, 0.2, 0.3, 0.4)]
    index = CenteredEdgeStabilityIndex(entries, window_seconds=0.4)

    ratio = index.persistence_ratio(center_timestamp=0.2)

    assert ratio is not None
    np.testing.assert_array_equal(ratio[text_mask], np.ones(text_mask.sum()))


def test_centered_index_fixes_the_onset_artifact_a_causal_buffer_cannot():
    # The exact failure mode Alpha-D2 targets: a real subtitle state
    # begins at t=0.2 and holds steady afterwards, but a purely causal
    # buffer at t=0.2 only has OLD-state history behind it, so it scores
    # the brand-new state's own edge as unstable. A centered index at
    # the SAME t=0.2 also sees the state's own near-future frames and
    # correctly scores it as stable.
    old_state_mask = downsampled_edge_mask(_text_frame(offset=0))
    new_state_mask = downsampled_edge_mask(_text_frame(offset=30))

    causal_buffer = EdgeStabilityBuffer(window_seconds=0.4)
    for t in (-0.3, -0.2, -0.1, 0.0):
        causal_buffer.push(t, old_state_mask)
    causal_buffer.push(0.2, new_state_mask)
    causal_signature = subtitle_stable_signature(new_state_mask, causal_buffer)

    entries = [(-0.3, old_state_mask), (-0.2, old_state_mask), (-0.1, old_state_mask), (0.0, old_state_mask)]
    entries += [(t, new_state_mask) for t in (0.2, 0.3, 0.4, 0.5)]
    centered_index = CenteredEdgeStabilityIndex(entries, window_seconds=0.4)
    centered_ratio = centered_index.persistence_ratio(center_timestamp=0.2)
    from glyphcue.application.subtitle_stable_signature import combine_signature

    centered_signature = combine_signature(new_state_mask, centered_ratio)

    assert not causal_signature.any()  # causal: onset artifact -- signature wiped out
    assert centered_signature.any()  # centered: correctly recognizes the held state


def test_centered_index_handles_a_short_history_near_the_start_of_the_clip():
    text_mask = downsampled_edge_mask(_text_frame())
    entries = [(0.0, text_mask)]
    index = CenteredEdgeStabilityIndex(entries, window_seconds=0.4)

    ratio = index.persistence_ratio(center_timestamp=0.0)

    assert ratio is not None


def test_centered_index_reports_no_persistence_outside_any_entry_window():
    index = CenteredEdgeStabilityIndex([], window_seconds=0.4)

    assert index.persistence_ratio(0.0) is None
