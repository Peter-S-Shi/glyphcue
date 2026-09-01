import numpy as np

from glyphcue.application.subtitle_stable_signature import (
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
