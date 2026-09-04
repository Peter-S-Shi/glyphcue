import numpy as np

from glyphcue.application.detector_assisted_signature import (
    CANONICAL_BAND_HEIGHT,
    CANONICAL_BAND_WIDTH,
    MAX_LINES,
    canonical_line_band,
    detected_lines_from_polygons,
    detector_assisted_signature,
)


def _poly(x0: float, y0: float, x1: float, y1: float):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_each_polygon_on_its_own_vertical_band_becomes_its_own_line():
    polys = [_poly(10, 0, 200, 20), _poly(10, 40, 200, 60)]

    lines = detected_lines_from_polygons(polys)

    assert len(lines) == 2
    assert lines[0] == (10, 0, 200, 20)
    assert lines[1] == (10, 40, 200, 60)


def test_polygons_sharing_a_vertical_extent_merge_into_one_line():
    # A detector often splits one visual caption line into several
    # boxes; those must become ONE line, not several, or the signature
    # layout would shift purely because the detector fragmented a line.
    polys = [_poly(10, 0, 90, 20), _poly(100, 2, 200, 22)]

    lines = detected_lines_from_polygons(polys)

    assert lines == [(10, 0, 200, 22)]


def test_lines_are_returned_in_top_to_bottom_order():
    polys = [_poly(10, 40, 200, 60), _poly(10, 0, 200, 20)]

    lines = detected_lines_from_polygons(polys)

    assert [line[1] for line in lines] == [0, 40]


def test_no_polygons_means_no_lines():
    assert detected_lines_from_polygons([]) == []


def _ink_frame(
    offset: int = 0, spacing: int = 4, height: int = 40, width: int = 240
) -> np.ndarray:
    """Light background with a dark 'glyph' stripe pattern -- stands in
    for real text without depending on any font. `offset` translates the
    same content; `spacing` changes the content itself."""
    frame = np.full((height, width, 3), 230, dtype=np.uint8)
    frame[10:24, 20 + offset : 120 + offset : spacing] = 20
    return frame


def test_canonical_band_has_the_declared_uniform_shape_regardless_of_box_size():
    frame = _ink_frame()

    small = canonical_line_band(frame, (20, 10, 120, 24))
    large = canonical_line_band(frame, (0, 0, 240, 40))

    assert small.shape == (CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH)
    assert large.shape == (CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH)


def test_canonical_band_marks_glyph_ink_as_the_minority_class():
    # Polarity independence: whichever way round the contrast runs, the
    # sparser class is the ink. This is what lets one rule cover
    # white-on-dark and dark-on-light captions without a color prior.
    dark_on_light = canonical_line_band(_ink_frame(), (20, 10, 120, 24))
    light_on_dark = canonical_line_band(255 - _ink_frame(), (20, 10, 120, 24))

    assert dark_on_light.mean() < 0.5
    assert light_on_dark.mean() < 0.5


def test_canonical_band_of_the_same_content_is_stable_under_box_padding_jitter():
    # Detector boxes wobble a few pixels frame to frame on identical
    # content; after ink-tightening + rescaling the signature must not
    # meaningfully move, or every sampled frame would look like a new
    # state.
    frame = _ink_frame()

    tight = canonical_line_band(frame, (20, 10, 120, 24))
    padded = canonical_line_band(frame, (14, 6, 126, 30))

    disagreement = float(np.mean(tight != padded))
    assert disagreement < 0.05


def test_different_glyph_content_produces_a_clearly_different_band():
    a = canonical_line_band(_ink_frame(spacing=4), (0, 0, 240, 40))
    b = canonical_line_band(_ink_frame(spacing=7), (0, 0, 240, 40))

    assert float(np.mean(a != b)) > 0.05


def test_the_same_content_translated_is_deliberately_the_same_band():
    # Ink-tightening makes the band translation-invariant on purpose:
    # a caption that sits a few pixels left or right, or whose detector
    # box shifted, is the SAME subtitle state. Position is not identity.
    a = canonical_line_band(_ink_frame(offset=0), (0, 0, 240, 40))
    b = canonical_line_band(_ink_frame(offset=60), (0, 0, 240, 40))

    np.testing.assert_array_equal(a, b)


def test_signature_canvas_stacks_one_band_per_detected_line():
    frame = _ink_frame(height=80)
    polys = [_poly(20, 10, 120, 24), _poly(20, 40, 120, 54)]

    signature = detector_assisted_signature(frame, polys)

    assert signature.shape == (MAX_LINES * CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH)


def test_signature_is_empty_when_the_detector_finds_no_text():
    # An explicit blank state comes from the detector saying "no text
    # here", not from a pixel-density threshold -- the exact rule that
    # failed to transfer across fixtures in the Alpha family.
    signature = detector_assisted_signature(_ink_frame(), [])

    assert not signature.any()


def test_signature_ignores_lines_beyond_the_declared_maximum():
    frame = _ink_frame(height=200)
    polys = [_poly(20, 10 + 30 * i, 120, 24 + 30 * i) for i in range(MAX_LINES + 3)]

    signature = detector_assisted_signature(frame, polys)

    assert signature.shape == (MAX_LINES * CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH)
