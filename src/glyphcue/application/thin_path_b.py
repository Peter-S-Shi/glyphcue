from __future__ import annotations

from pathlib import Path

from glyphcue.adapters.pysubs2_subtitle_io import ImportWarning, Pysubs2SubtitleFormatAdapter
from glyphcue.application.reconstruction import (
    PathBDiagnostics,
    reconstruct_cues,
    reconstruct_cues_with_diagnostics,
)
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
) -> tuple[list[Cue], dict[str, Observation], dict[str, PathBDiagnostics], list[ImportWarning]]:
    """Parse `source` and reconstruct Cues, also returning the raw
    Observations keyed by id (for QA evidence display), each
    reconstructed Cue's real `PathBDiagnostics`, keyed by Cue id
    (ROADMAP M8) -- so a caller can feed them into
    `review_signals_from_path_b_diagnostics` for a real Review
    Priority -- and any `ImportWarning`s the adapter produced for
    source events it had to skip. The application flow never discards
    these warnings itself; a caller that ignores the returned list is
    choosing to, not being denied the information."""
    adapter = Pysubs2SubtitleFormatAdapter()
    observations, import_warnings = adapter.parse_with_warnings(source)
    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)
    observations_by_id = {observation.id: observation for observation in observations}
    diagnostics_by_cue_id = {entry.cue_id: entry for entry in diagnostics}
    return cues, observations_by_id, diagnostics_by_cue_id, import_warnings
