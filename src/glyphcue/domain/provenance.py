from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class ProvenanceKind(str, Enum):
    SUBTITLE_IMPORT = "subtitle_import"
    OCR_ENGINE = "ocr_engine"


@dataclass(frozen=True)
class Provenance:
    """Where a piece of domain evidence came from."""

    kind: ProvenanceKind
    source: str
    detail: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("Provenance.source must not be empty")
