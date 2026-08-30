from __future__ import annotations

from enum import Enum


class ReviewState(str, Enum):
    """Human review status of a Cue."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
