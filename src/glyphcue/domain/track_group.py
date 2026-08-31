from __future__ import annotations

from dataclasses import dataclass

from glyphcue.domain.roi import ROI


@dataclass(frozen=True)
class TrackGroup:
    """A configured visual region and its expected language layers.

    Product model (see GLYPHCUE_PRODUCT_ARCHITECTURE.md section 11):
    Track Group -> ROI -> Language Layers 1..N. `languages` is the set of
    languages expected to appear in this region; it is a configuration
    concept, not the reconstructed per-Cue LanguageLayer content.
    """

    id: str
    roi: ROI
    languages: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.languages:
            raise ValueError("TrackGroup.languages must contain at least one language")
