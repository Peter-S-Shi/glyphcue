from __future__ import annotations

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation

_UNDETERMINED_LANGUAGE = "und"
_ROLLING_OVERLAP_RATIO_THRESHOLD = 0.6
_MIN_OBSERVATIONS_FOR_ROLLING = 3


def _is_rolling_run(observations: list[Observation]) -> bool:
    """A simple, explainable rolling-caption heuristic (M1 baseline).

    Requires at least 3 observations (a smaller sample is not confident
    evidence of a rolling pattern) and a majority of consecutive pairs
    overlapping in time. Deepened in Milestone 8 with real evidence.
    """
    if len(observations) < _MIN_OBSERVATIONS_FOR_ROLLING:
        return False
    pairs = list(zip(observations, observations[1:]))
    overlaps = sum(
        1 for current, following in pairs if current.end_time > following.start_time
    )
    return (overlaps / len(pairs)) >= _ROLLING_OVERLAP_RATIO_THRESHOLD


def _character_overlap_length(previous: str, current: str) -> int:
    """Largest k where the last k characters of `previous` equal the first
    k characters of `current`.

    Operates on characters, not whitespace-split tokens, so it works for
    CJK text with no spaces between words.
    """
    limit = min(len(previous), len(current))
    for k in range(limit, 0, -1):
        if previous[-k:] == current[:k]:
            return k
    return 0


def _merge_rolling_text(observations: list[Observation]) -> str:
    text = observations[0].text
    for observation in observations[1:]:
        overlap = _character_overlap_length(text, observation.text)
        addition = observation.text[overlap:]
        if not addition:
            continue
        needs_separator = (
            overlap == 0
            and text
            and not text.endswith(" ")
            and not addition.startswith(" ")
        )
        text = f"{text} {addition}" if needs_separator else text + addition
    return text


def reconstruct_cues(observations: list[Observation]) -> list[Cue]:
    """Minimal Path B reconstruction: Observation(s) -> Cue(s).

    ROADMAP.md Milestone 1 scope: this is intentionally thin. A detected
    rolling run is merged into a single Cue; otherwise each Observation
    becomes its own unchanged Cue. This does not implement sentence-level
    resegmentation, punctuation-based breaking, or full CJK normalization
    -- those are Milestone 8 concerns.
    """
    ordered = sorted(observations, key=lambda observation: observation.start_time)
    if not ordered:
        return []

    if _is_rolling_run(ordered):
        layer = LanguageLayer(
            language=ordered[0].language or _UNDETERMINED_LANGUAGE,
            text=_merge_rolling_text(ordered),
            observation_ids=tuple(observation.id for observation in ordered),
        )
        return [
            Cue(
                id=f"cue-{ordered[0].id}",
                start_time=ordered[0].start_time,
                end_time=ordered[-1].end_time,
                language_layers=(layer,),
            )
        ]

    return [
        Cue(
            id=f"cue-{observation.id}",
            start_time=observation.start_time,
            end_time=observation.end_time,
            language_layers=(
                LanguageLayer(
                    language=observation.language or _UNDETERMINED_LANGUAGE,
                    text=observation.text,
                    observation_ids=(observation.id,),
                ),
            ),
        )
        for observation in ordered
    ]
