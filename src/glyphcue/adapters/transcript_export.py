from __future__ import annotations

from pathlib import Path

from glyphcue.domain.cue import Cue
from glyphcue.domain.review_state import ReviewState

# GLYPHCUE_PRODUCT_ARCHITECTURE.md section 18 / DESIGN.md section 30:
# transcript export is an export PRESET over the existing Cue model, not
# a separate document/AI subsystem. Both presets share the same
# non-destructive contract as SRT/VTT export -- discarded Cues are
# excluded, remaining Cues stay in their current QA-edited state and
# start_time order.

_AI_READY_GAP_SECONDS = 30.0


def _timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _kept_cues(cues: list[Cue]) -> list[Cue]:
    return [cue for cue in cues if cue.review_state != ReviewState.REJECTED]


def write_readable_transcript(cues: list[Cue], path: Path) -> None:
    """A plain-TXT transcript meant for normal human reading: one
    timestamped block per Cue, every language layer shown, in
    start_time order. Every Cue keeps its own timestamp -- readability
    is the point, not density reduction (that is the AI-ready preset's
    job, see `write_ai_ready_transcript`)."""
    lines: list[str] = []
    for cue in _kept_cues(cues):
        lines.append(f"[{_timestamp(cue.start_time)}]")
        for layer in cue.language_layers:
            lines.append(layer.text)
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_ai_ready_transcript(
    cues: list[Cue], path: Path, languages: tuple[str, ...] | None = None
) -> None:
    """A Markdown transcript preset tuned for external AI consumption
    (GLYPHCUE_PRODUCT_ARCHITECTURE.md section 18): no per-cue numbering,
    reduced timestamp density (a new timestamp heading only after a gap
    of at least `_AI_READY_GAP_SECONDS`, not one per Cue), and an
    optional `languages` filter so only the requested layer(s) are
    included. GlyphCue produces this clean source text; summary/Q&A is
    left to the external AI tool (DESIGN.md section 70)."""
    kept = _kept_cues(cues)
    lines: list[str] = []
    last_timestamp_at: float | None = None

    for cue in kept:
        layers = (
            cue.language_layers
            if languages is None
            else tuple(layer for layer in cue.language_layers if layer.language in languages)
        )
        if not layers:
            continue

        if last_timestamp_at is None or cue.start_time - last_timestamp_at >= _AI_READY_GAP_SECONDS:
            lines.append(f"## {_timestamp(cue.start_time)}")
            last_timestamp_at = cue.start_time

        for layer in layers:
            lines.append(layer.text)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
