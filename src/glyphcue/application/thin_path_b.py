from __future__ import annotations

from pathlib import Path

from glyphcue.adapters.pysubs2_subtitle_io import Pysubs2SubtitleFormatAdapter
from glyphcue.application.reconstruction import reconstruct_cues
from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation


def run_thin_path_b(
    source: Path, destination: Path | None = None
) -> Path:
    """SRT/VTT -> Observation -> minimal reconstruction -> Cue -> export.

    ROADMAP.md Milestone 1: the thin Path B vertical slice. Never writes
    to `source`; the original file is left untouched.
    """
    if destination is None:
        destination = source.with_name(
            f"{source.stem}.reconstructed{source.suffix}"
        )
    if destination.resolve() == source.resolve():
        raise ValueError(
            "Thin Path B must not overwrite the source subtitle file"
        )

    adapter = Pysubs2SubtitleFormatAdapter()
    observations = adapter.parse(source)
    cues = reconstruct_cues(observations)
    adapter.write(cues, destination)
    return destination


def parse_and_reconstruct(
    source: Path,
) -> tuple[list[Cue], dict[str, Observation]]:
    """Parse `source` and reconstruct Cues, also returning the raw
    Observations keyed by id (for QA evidence display)."""
    adapter = Pysubs2SubtitleFormatAdapter()
    observations = adapter.parse(source)
    cues = reconstruct_cues(observations)
    observations_by_id = {observation.id: observation for observation in observations}
    return cues, observations_by_id
