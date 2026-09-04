"""M11 Research Gate -- Hybrid-T detector-anchored scheduler region.

The Hybrid Cascade (000fe1a) kept Beta-S's accuracy for free but only
reached its cost target on sample_b. Measured cause: the cheap scheduler
compares evidence over the WHOLE ROI, and on a talking-head shot the ROI
is mostly face. Inside a single held caption the whole-ROI cheap
signature disagreed with its own anchor on 36/37 (sample_d) and 33/34
(sample_a) grid points, median 0.162 and 0.061 -- at or above the 0.06
threshold Alpha-D2 once used to DECIDE states, so no recall-first
threshold could ever be quiet there. On sample_b, where ROI motion is
mild, the same evidence gave median 0.009 and 7/40 and the cascade
reached 16 calls.

So the problem is not the sensitivity of the cheap gate but its FIELD OF
VIEW. This module narrows it: after the detector has confirmed where the
text is, the cheap gate watches only that text and its immediate
surroundings, and stops watching the presenter. The mask follows the
newest detector output, so it is never stale by more than one
observation.

The safety story is unchanged and deliberately so:

  * With no confirmed text -- before the first observation, or after the
    detector reports a blank frame -- there is nothing to anchor to, so
    the gate falls back to the whole ROI. Blank -> text therefore keeps
    exactly the sensitivity it had in the baseline cascade.
  * A caption that appears somewhere the mask does not cover is invisible
    to the cheap gate, and is caught by the periodic safety sentinel
    instead -- bounded latency, never a lost state. This is the specific
    risk narrowing introduces, and it is characterized by test rather
    than argued away.
  * The mask still only SCHEDULES. It cannot create, merge or name a
    subtitle state; Beta-S decides every semantic question, unchanged.
"""

from __future__ import annotations

import numpy as np

from glyphcue.application.detector_assisted_signature import detected_lines_from_polygons
from glyphcue.application.subtitle_stable_signature import (
    _DEFAULT_MAX_SIGNATURE_HEIGHT,
    _DEFAULT_MAX_SIGNATURE_WIDTH,
)

# Declared a priori for this round and used unchanged on every fixture.
# Padding is expressed relative to each detected line's own height, so it
# self-scales across fixtures instead of being an absolute pixel count.
# A quarter of a line height covers glyph outlines, anti-aliasing, and
# the few pixels of detector box jitter seen in the Beta rounds, while
# staying far short of re-admitting the presenter.
PADDING_TO_LINE_HEIGHT = 0.25


def cheap_grid_mask(
    polygons,
    roi_shape: tuple[int, int],
    padding_to_line_height: float = PADDING_TO_LINE_HEIGHT,
) -> np.ndarray:
    """The detected text region, expressed on the cheap evidence grid.

    Built by painting the padded boxes at ROI resolution and passing them
    through the SAME downsample-and-crop geometry
    `subtitle_stable_signature` uses, rather than re-deriving the index
    arithmetic -- so the mask cannot drift out of alignment with the
    signature it masks.
    """
    height, width = roi_shape
    full = np.zeros((height, width), dtype=bool)
    for x0, y0, x1, y1 in detected_lines_from_polygons(polygons):
        pad = int(round(max(1, y1 - y0) * padding_to_line_height))
        full[
            max(0, y0 - pad) : min(height, y1 + pad),
            max(0, x0 - pad) : min(width, x1 + pad),
        ] = True

    if height > _DEFAULT_MAX_SIGNATURE_HEIGHT or width > _DEFAULT_MAX_SIGNATURE_WIDTH:
        sy = max(1, height // _DEFAULT_MAX_SIGNATURE_HEIGHT)
        sx = max(1, width // _DEFAULT_MAX_SIGNATURE_WIDTH)
        full = full[::sy, ::sx]
    return full[1:-1, 1:-1]


class TextAnchoredRegionMask:
    """Restricts the cheap scheduler to the last detector-confirmed text.

    Implements the cascade's `CheapRegionMask` seam. Stateful by design:
    `update` is called after each detector observation, `apply` on every
    grid point in between.
    """

    def __init__(self, padding_to_line_height: float = PADDING_TO_LINE_HEIGHT) -> None:
        self._padding = padding_to_line_height
        self._mask: np.ndarray | None = None
        self.fallback_count = 0
        self.masked_count = 0

    @property
    def has_confirmed_text(self) -> bool:
        return self._mask is not None

    def update(self, polygons, roi_shape: tuple[int, int]) -> None:
        if not polygons:
            # An observed blank is not a narrow region -- it is the
            # absence of one. Keeping a stale mask here would leave the
            # gate watching where text USED to be.
            self._mask = None
            return
        mask = cheap_grid_mask(polygons, roi_shape, self._padding)
        self._mask = mask if mask.any() else None

    def apply(self, cheap_signature: np.ndarray) -> np.ndarray:
        if self._mask is None or self._mask.shape != cheap_signature.shape:
            self.fallback_count += 1
            return cheap_signature
        self.masked_count += 1
        return cheap_signature & self._mask
