from __future__ import annotations

from glyphcue.domain.observation import Observation


def select_curated_evidence(
    observations: list[Observation], winning_text: str | None
) -> list[Observation]:
    """The default "Compact Curated Evidence" subset for one Cue
    (DESIGN.md sections 19-20): in-point, disagreement/ambiguity,
    representative consensus, and out-point -- picked because each
    answers "why did GlyphCue produce this reconstruction?", not
    because they're simply the first few observations.

    This selects a DEFAULT subset only; it never mutates or drops
    `observations` itself -- callers keep the full list available for
    "expand full evidence" (ROADMAP M7 acceptance gate: "full evidence
    remains accessible").
    """
    if not observations:
        return []
    ordered = sorted(observations, key=lambda observation: observation.start_time)
    if len(ordered) == 1:
        return list(ordered)

    curated: list[Observation] = []
    seen_ids: set[str] = set()

    def _add(observation: Observation) -> None:
        if observation.id not in seen_ids:
            curated.append(observation)
            seen_ids.add(observation.id)

    _add(ordered[0])  # in-point

    if winning_text is not None:
        for observation in ordered[1:-1]:
            if observation.text != winning_text:
                _add(observation)  # disagreement / ambiguity -- ANY deviation, not a fuzzy threshold

    if not any(observation.id in seen_ids for observation in ordered[1:-1]):
        middle = ordered[len(ordered) // 2]
        _add(middle)  # representative consensus, when nothing disagreed

    _add(ordered[-1])  # out-point

    curated.sort(key=lambda observation: observation.start_time)
    return curated
