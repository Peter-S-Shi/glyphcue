from __future__ import annotations

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation

_UNDETERMINED_LANGUAGE = "und"


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


def _continues_run(
    previous_observation: Observation, accumulated_text: str, next_observation: Observation
) -> tuple[bool, int]:
    """Whether `next_observation` is a rolling continuation of the current
    run (M1 baseline).

    Conservative on purpose: temporal overlap alone is not evidence of a
    rolling caption (two genuinely unrelated, simultaneous captions also
    overlap in time). A continuation additionally requires character-level
    textual overlap at the boundary -- i.e. the run's accumulated text and
    the next observation actually share text, not just a timing window.
    """
    if not previous_observation.end_time > next_observation.start_time:
        return False, 0
    overlap = _character_overlap_length(accumulated_text, next_observation.text)
    return overlap > 0, overlap


def _close_run(observations: list[Observation], merged_text: str) -> Cue:
    layer = LanguageLayer(
        language=observations[0].language or _UNDETERMINED_LANGUAGE,
        text=merged_text,
        observation_ids=tuple(observation.id for observation in observations),
    )
    return Cue(
        id=f"cue-{observations[0].id}",
        start_time=observations[0].start_time,
        end_time=observations[-1].end_time,
        language_layers=(layer,),
    )


def reconstruct_cues(observations: list[Observation]) -> list[Cue]:
    """Minimal Path B reconstruction: Observation(s) -> Cue(s).

    ROADMAP.md Milestone 1 scope: this is intentionally thin. Observations
    are scanned in order and grouped into contiguous rolling runs; a run
    requires both temporal overlap AND character-level textual
    continuation between each consecutive pair (see _continues_run).
    Only observations inside a detected run are merged into one Cue --
    everything else, including runs that only span part of a file, maps
    1:1 to unchanged Cues. This does not implement sentence-level
    resegmentation, punctuation-based breaking, or full CJK normalization
    -- those are Milestone 8 concerns.
    """
    ordered = sorted(observations, key=lambda observation: observation.start_time)
    if not ordered:
        return []

    cues: list[Cue] = []
    run = [ordered[0]]
    run_text = ordered[0].text

    for observation in ordered[1:]:
        continues, overlap = _continues_run(run[-1], run_text, observation)
        if continues:
            run.append(observation)
            run_text += observation.text[overlap:]
        else:
            cues.append(_close_run(run, run_text))
            run = [observation]
            run_text = observation.text

    cues.append(_close_run(run, run_text))
    return cues
