from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LanguageLayer:
    """One language's reconstructed text within a Cue.

    V1 multilingual timing is frozen (see ROADMAP.md section 4): a
    LanguageLayer has no timing fields of its own and always inherits its
    owning Cue's start_time / end_time. Do not add timing fields here.
    """

    language: str
    text: str
    observation_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.language:
            raise ValueError("LanguageLayer.language must not be empty")
