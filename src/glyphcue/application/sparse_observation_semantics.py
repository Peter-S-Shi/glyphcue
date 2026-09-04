"""M11 Research Gate -- state semantics under SPARSE observation.

Hybrid-T (e8a1910) reached the cost target -- 23/14/13 detector calls per
10s window against a dense 50 -- and then lost two real states. Neither
loss was the scheduler mislocating text; both were rules written for
dense sampling meeting observations that are now sparse:

  * sample_a state 1 (27.00-27.77s) WAS observed, at 27.0. Its group ran
    27.0-28.0, and `_close_group`'s middle-member rule put the
    representative at 28.0 -- in the gap after the state. Observed, and
    still scored as swallowed.
  * sample_b state 5 lasts 0.23s at the very end of the window, so it
    fell entirely inside a sentinel interval and was never observed at
    all.

This module answers the first with a representative rule that reads the
group's own evidence instead of counting positions, and the second with a
structural boundary guarantee in the dry run. They are independent fixes
for independent failures and are reported as such: neither one would
have solved the other's case.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

from glyphcue.application.visual_state_sampling import SampledFrame, signature_distance


def stable_representative(
    members: Sequence[SampledFrame],
    distance: Callable[[np.ndarray, np.ndarray], float] = signature_distance,
) -> SampledFrame:
    """The observation that best represents its group: the one whose
    signature disagrees least with the rest (the group's medoid).

    The rule it replaces picked the temporal midpoint, which under dense
    sampling is a decent proxy for "not a transition-adjacent frame" --
    a long run of samples has its atypical frames at the edges. Under
    sparse scheduling that proxy breaks: a group can hold two members,
    the state's own observation and the next scheduled look after the
    state has already ended, and "middle" then means "the later one".

    Choosing by evidence keeps what the positional rule was reaching for
    -- a frame typical of the state, not one caught mid-transition --
    without assuming anything about how many observations there are or
    how they are spaced. Ties go to the EARLIEST member: with nothing to
    separate the candidates, the observation that established the group
    is the one guaranteed to lie inside the state that produced it,
    which is precisely where sample_a state 1 was lost.
    """
    if not members:
        raise ValueError("a group always has at least one member")
    if len(members) == 1:
        return members[0]

    best_index = 0
    best_total = float("inf")
    for index, candidate in enumerate(members):
        total = sum(
            distance(candidate.signature, other.signature)
            for position, other in enumerate(members)
            if position != index
        )
        if total < best_total:
            best_total = total
            best_index = index
    return members[best_index]
