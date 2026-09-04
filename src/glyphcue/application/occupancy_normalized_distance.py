"""M11 Research Gate -- occupancy-normalized signature distance.

Used by the EXPERIMENTAL_HYBRID Path A profile. The default
PRODUCTION_TRIGGER profile is untouched and still uses
`visual_state_sampling.signature_distance`, so both pipelines remain
live and independently selectable.

The forensic in 810d632 located the last blocker, and it was not the
detector, the stroke mask, the tighten step, the grouping rules or the
ROI. It was this metric's denominator. A Beta-S signature is a fixed
canvas of `MAX_LINES` canonical bands, and `signature_distance` divides
the cell mismatch by ALL of it -- so a band no line was detected in
contributes zeros to both operands and does nothing but dilute the
result. The measured distance between two captions therefore scales
with how many bands the detector happened to fill:

    sample_d  frozen ROI        2.00 detected lines   mean pairwise 0.1930
    sample_d  hand-drawn tight  1.00 detected line    mean pairwise 0.0895
    sample_b  frozen ROI        2.00 detected lines   mean pairwise 0.2027
    sample_b  hand-drawn tight  0.92 detected lines   mean pairwise 0.1034

A user drawing their ROI slightly tighter can crop away the second line
of a two-line caption, and every distance in that run halves. That is
why the frozen 0.10 threshold had no ROI-invariant meaning: it was not a
property of caption content, it was entangled with a mean band occupancy
of about two.

This module normalizes over the bands that actually carry evidence. The
denominator is the UNION of the two signatures' occupied bands, which is
the only choice that is symmetric AND keeps line presence/absence
discriminative: a band occupied on one side only stays inside the
denominator, so all of its ink counts as mismatch rather than being
quietly dropped the way an intersection would drop it. Gaining or losing
a caption line is real evidence that the state changed, and it survives.

Everything else is untouched -- same Beta-S stroke extraction, same
canonical bands, same canvas layout, same detector, same scheduler, same
grouping topology. Only the denominator changes.

Because the denominator shrinks, distances under this metric are LARGER
than under the production one (by `MAX_LINES / occupied`), so the old
0.10 operating point does not carry over. Scale and operating point are
one quantity, which is why the threshold calibrated against this scale
lives here beside it rather than anywhere else.
"""

from __future__ import annotations

import numpy as np

from glyphcue.application.detector_assisted_signature import (
    CANONICAL_BAND_HEIGHT,
    MAX_LINES,
)


def occupied_bands(signature: np.ndarray) -> list[bool]:
    """Which canonical bands of a signature carry any ink at all.

    A band is occupied when the detector found a caption line for it and
    that line produced stroke evidence; an empty band means no line, not
    "a line that happens to be blank".
    """
    return [
        bool(
            signature[
                index * CANONICAL_BAND_HEIGHT : (index + 1) * CANONICAL_BAND_HEIGHT
            ].any()
        )
        for index in range(MAX_LINES)
    ]


def occupancy_normalized_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Fraction of disagreeing cells, measured over the UNION of the two
    signatures' occupied bands rather than over the whole fixed canvas.

    0.0 = identical (two fully blank signatures included, since they
    agree that there is no text). Shape mismatch is treated as maximally
    different, never compared cell-wise -- same rule as the production
    distance.
    """
    if a.shape != b.shape:
        return 1.0

    union = [x or y for x, y in zip(occupied_bands(a), occupied_bands(b))]
    if not any(union):
        return 0.0

    rows = np.concatenate(
        [
            np.arange(index * CANONICAL_BAND_HEIGHT, (index + 1) * CANONICAL_BAND_HEIGHT)
            for index, occupied in enumerate(union)
            if occupied
        ]
    )
    return float(np.mean(a[rows] != b[rows]))


OCCUPANCY_GROUP_DISTANCE_THRESHOLD = 0.300
"""The state-grouping operating point for THIS metric.

Not a knob. It was derived once, by a policy declared before it was run,
from sample_d and its ROI perturbation family alone -- sample_a and
sample_b were held out and never consulted while deriving it:

    S95 = p95(same-state pairwise distances)      = 0.2530
    D05 = p05(adjacent different-state distances) = 0.3569
    D05 > S95, so the threshold is sqrt(S95 * D05) = 0.3005 -> 0.300,
    a symmetric 1.19x multiplicative margin from each bound.

Validated afterwards with both the metric and this value frozen:
sample_d 7/7 and sample_a 6/6 with zero swallowed states on all eight
ROI variants each, sample_b 5/5 on six of eight. The two sample_b
variants that fall short lose only its 0.265s tail caption, and only
because the ROI crops that caption out of frame entirely -- see the
residual risk in `hybrid_evidence_job`.

Changing this number invalidates that evidence, and it cannot be
retuned independently of the metric above: the two were calibrated as
one quantity.
"""
