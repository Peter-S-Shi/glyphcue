from __future__ import annotations

from glyphcue.domain.cue import Cue
from glyphcue.domain.review_state import ReviewState


def _is_protected(cue: Cue) -> bool:
    """A Cue is protected from automated reprocessing overwrite if it has
    been Approved, Rejected (Discarded), or marked Needs Review (edited/nudged/split/merged).
    Only pure machine PENDING cues may be overwritten by newly reconstructed cues.
    """
    return cue.review_state in (
        ReviewState.APPROVED,
        ReviewState.REJECTED,
        ReviewState.NEEDS_REVIEW,
    )


def _overlaps(c1: Cue, c2: Cue) -> bool:
    """Returns True if two Cues overlap in time."""
    return c1.start_time < c2.end_time and c1.end_time > c2.start_time


def merge_incremental_cues(
    existing_cues: list[Cue],
    new_cues: list[Cue],
    range_start: float,
    range_end: float,
) -> list[Cue]:
    """Non-destructively merges newly reconstructed 
ew_cues for processing
    range [range_start, range_end] into existing_cues.

    Rules:
    1. Outside Cues: existing cues fully outside [range_start, range_end] are retained 100%.
    2. Protected Cues: existing cues with human review / edits are retained 100% and never overwritten.
    3. Boundary-Straddling Cues: existing unreviewed cues crossing range_start or range_end are retained.
    4. Interior Unreviewed Cues: pure machine PENDING cues completely inside [range_start, range_end] are replaced.
    5. Conflict Resolution: new candidate cues that collide with any protected existing cues are skipped.
    """
    retained_existing: list[Cue] = []
    protected_cues: list[Cue] = []

    for cue in existing_cues:
        # Fully outside the processing range
        if cue.end_time <= range_start or cue.start_time >= range_end:
            retained_existing.append(cue)
            if _is_protected(cue):
                protected_cues.append(cue)
        # Protected cue overlapping the range
        elif _is_protected(cue):
            retained_existing.append(cue)
            protected_cues.append(cue)
        # Straddling boundary cues (extends outside the range)
        elif cue.start_time < range_start or cue.end_time > range_end:
            retained_existing.append(cue)
        # Otherwise: interior unreviewed machine cue -> replaced (discarded)

    # Filter new cues: do not collide with protected cues
    accepted_new_cues: list[Cue] = []
    for new_cue in new_cues:
        collides_with_protected = any(_overlaps(new_cue, p) for p in protected_cues)
        if not collides_with_protected:
            accepted_new_cues.append(new_cue)

    all_cues = retained_existing + accepted_new_cues
    all_cues.sort(key=lambda c: (c.start_time, c.end_time, c.id))
    return all_cues