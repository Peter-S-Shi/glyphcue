"""Canonical GlyphCue domain types.

This package owns Observation, Cue, LanguageLayer, ReviewState, and
Provenance. It must not import third-party media/OCR/subtitle libraries;
adapters translate vendor types into these domain types at the boundary.
"""

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.review_state import ReviewState

__all__ = [
    "Cue",
    "LanguageLayer",
    "Observation",
    "Provenance",
    "ProvenanceKind",
    "ReviewState",
]
