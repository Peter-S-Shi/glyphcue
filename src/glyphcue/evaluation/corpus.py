"""Milestone 10 evaluation corpus manifest schema.

A corpus entry describes one representative-video evaluation sample:
which video, which 2-5 minute segment of it, and the independent
ground-truth Cues for that segment (ROADMAP.md section 17's evaluation
corpus).

Privacy is a file-layout concern, not a schema concern: a public,
demo-safe manifest is committed to git; a private manifest covering
real/sensitive samples is kept local (gitignored) and uses the exact
same schema. Callers load and merge multiple manifests rather than the
schema special-casing private entries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CorpusVisibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass(frozen=True)
class GroundTruthCue:
    start_time: float
    end_time: float
    text: str
    language: str | None = None


@dataclass(frozen=True)
class CorpusEntry:
    id: str
    video_path: str
    segment_start_seconds: float
    segment_end_seconds: float
    languages: tuple[str, ...]
    visibility: CorpusVisibility
    ground_truth_cues: tuple[GroundTruthCue, ...]
    notes: str = ""


def _parse_ground_truth_cue(raw: dict) -> GroundTruthCue:
    return GroundTruthCue(
        start_time=raw["start_time"],
        end_time=raw["end_time"],
        text=raw["text"],
        language=raw.get("language"),
    )


_REQUIRED_ENTRY_FIELDS = (
    "id",
    "video_path",
    "segment_start_seconds",
    "segment_end_seconds",
    "languages",
    "visibility",
    "ground_truth_cues",
)


def _parse_entry(raw: dict) -> CorpusEntry:
    for field in _REQUIRED_ENTRY_FIELDS:
        if field not in raw:
            raise ValueError(f"Corpus entry missing required field {field!r}")
    segment_start = raw["segment_start_seconds"]
    segment_end = raw["segment_end_seconds"]
    if segment_end <= segment_start:
        raise ValueError(
            f"Corpus entry {raw['id']!r}: segment end must be after segment start"
        )
    return CorpusEntry(
        id=raw["id"],
        video_path=raw["video_path"],
        segment_start_seconds=segment_start,
        segment_end_seconds=segment_end,
        languages=tuple(raw["languages"]),
        visibility=CorpusVisibility(raw["visibility"]),
        ground_truth_cues=tuple(
            _parse_ground_truth_cue(cue) for cue in raw["ground_truth_cues"]
        ),
        notes=raw.get("notes", ""),
    )


def load_corpus_manifest(path: Path) -> tuple[CorpusEntry, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(_parse_entry(entry) for entry in raw["entries"])


def load_corpus(*manifest_paths: Path) -> tuple[CorpusEntry, ...]:
    """Loads and merges one or more manifests (e.g. a committed public
    manifest plus a gitignored private manifest) into one corpus, sharing
    the exact same schema -- see the module docstring on why privacy is
    handled at the file layer rather than the schema."""
    entries: list[CorpusEntry] = []
    seen_ids: set[str] = set()
    for manifest_path in manifest_paths:
        for entry in load_corpus_manifest(manifest_path):
            if entry.id in seen_ids:
                raise ValueError(f"duplicate corpus entry id {entry.id!r}")
            seen_ids.add(entry.id)
            entries.append(entry)
    return tuple(entries)
