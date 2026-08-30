from __future__ import annotations

from pathlib import Path
from typing import Protocol

from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation


class SubtitleFormatAdapter(Protocol):
    """Boundary for reading/writing timed-text subtitle formats (SRT/VTT).

    Implementations own any third-party subtitle library (e.g. pysubs2)
    entirely internally. Vendor cue/subtitle objects must never cross this
    boundary — only GlyphCue Observation/Cue domain objects may.
    """

    def parse(self, path: Path) -> list[Observation]:
        """Read a subtitle file into raw GlyphCue Observations."""
        ...

    def write(self, cues: list[Cue], path: Path) -> None:
        """Write reconstructed Cues to a new subtitle file (non-destructive)."""
        ...
