from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pysubs2

from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.review_state import ReviewState


@dataclass(frozen=True)
class ImportWarning:
    """One source event pysubs2 successfully parsed as a *structural*
    entry, but that could not become a valid `Observation` on its own
    (e.g. inverted/zero-duration timing) -- named explicitly (source
    index + reason) rather than silently dropped. This is a per-event
    defensive seam, not a parser rewrite: a file pysubs2 itself cannot
    parse at all still fails fast, as before."""

    source_index: int
    reason: str


class Pysubs2SubtitleFormatAdapter:
    """Concrete SubtitleFormatAdapter (SRT/VTT) backed by pysubs2.

    pysubs2 objects (SSAFile/SSAEvent) never cross this module's
    boundary; only glyphcue domain types (Observation/Cue) do.
    """

    def parse_with_warnings(self, path: Path) -> tuple[list[Observation], list[ImportWarning]]:
        """Like `parse`, but also returns an `ImportWarning` for every
        source event pysubs2 could structurally read that nonetheless
        failed `Observation`'s own domain invariants (negative or
        inverted timing) -- one bad event does not take down the whole
        file; the events around it are still recovered, and the skipped
        one is never silently dropped."""
        subtitles = pysubs2.load(str(path))
        provenance = Provenance(kind=ProvenanceKind.SUBTITLE_IMPORT, source=str(path))
        observations: list[Observation] = []
        warnings: list[ImportWarning] = []
        for index, event in enumerate(subtitles):
            text = event.plaintext.strip()
            if not text:
                continue
            try:
                observations.append(
                    Observation(
                        id=f"{path.name}:{index}",
                        text=text,
                        start_time=event.start / 1000.0,
                        end_time=event.end / 1000.0,
                        provenance=provenance,
                    )
                )
            except ValueError as exc:
                warnings.append(ImportWarning(source_index=index, reason=str(exc)))
        return observations, warnings

    def parse(self, path: Path) -> list[Observation]:
        observations, _warnings = self.parse_with_warnings(path)
        return observations

    def write(self, cues: list[Cue], path: Path) -> None:
        """Write `cues` to a new file at `path`, atomically.

        Writes to a sibling temporary file first, then renames it into
        place, so a crash mid-write never leaves a partially written
        subtitle file at `path`.

        Discarded Cues (`ReviewState.REJECTED`) are excluded from the
        exported file -- Discard's whole point is "do not ship this
        line" (DESIGN.md section 23); `REJECTED` is still kept
        internally as real review history (who rejected what), it is
        only the export boundary that enforces the exclusion.
        """
        subtitles = pysubs2.SSAFile()
        for cue in cues:
            if cue.review_state == ReviewState.REJECTED:
                continue
            text = "\n".join(layer.text for layer in cue.language_layers)
            subtitles.append(
                pysubs2.SSAEvent(
                    start=round(cue.start_time * 1000),
                    end=round(cue.end_time * 1000),
                    text=text,
                )
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        try:
            subtitles.save(str(temporary_path), format_=path.suffix.lstrip("."))
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)
