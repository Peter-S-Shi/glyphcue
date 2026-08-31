from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from glyphcue.application.frame_reading_aggregation import (
    aggregate_same_frame_observations,
    member_observation_ids,
)
from glyphcue.application.ocr_evidence_job import STATE_TRIGGER_DETAIL_KEY
from glyphcue.application.text_similarity import character_similarity
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation

_UNDETERMINED_LANGUAGE = "und"
_DEFAULT_SIMILARITY_THRESHOLD = 0.5
"""Two consecutive observations are treated as noisy readings of the
same real subtitle state when their text is at least this similar.
A simple, explainable, tunable knob (like M4's change_threshold) -- not
an opaque model. 0.5 tolerates a handful of OCR-noise character errors
on typical subtitle-length text without merging two genuinely different
captions that happen to share a few characters. Only consulted when the
observation carries no real state-transition evidence from M4 (see
_group_into_state_runs) -- a detected change always wins over
similarity, and text is never used to override it."""

_STATE_CHANGE_TRIGGERS = {"first_frame", "change_detected"}
"""M4 trigger reasons (ChangeTriggeredOcrPolicy.last_trigger_reason,
threaded through Observation.provenance.detail[STATE_TRIGGER_DETAIL_KEY])
that are themselves real evidence of a new state -- these always start
a new run regardless of text similarity to the previous one.
"periodic_confirmation" (or no trigger info at all, e.g. non-M4
provenance) does not: that case falls back to similarity voting, since
it means "state believed unchanged" or "unknown," never "state
changed"."""


@dataclass(frozen=True)
class ConsensusDiagnostics:
    """Explainability record for one reconstructed Cue: what went into
    the vote and whether the supporting observations agreed.

    Not persisted -- this is a same-call companion to the Cue list, for
    tests, logging, and evaluation tooling to inspect *why* a Cue's text
    was chosen, per ROADMAP M5's "reconstruction diagnostics" and
    "failure cases are recorded" acceptance gate.
    """

    cue_id: str
    observation_count: int
    distinct_text_count: int
    agreement_ratio: float
    had_disagreement: bool


def _state_trigger(observation: Observation) -> str | None:
    return observation.provenance.detail.get(STATE_TRIGGER_DETAIL_KEY)


def _group_into_state_runs(
    ordered: list[Observation], similarity_threshold: float
) -> list[tuple[list[Observation], float | None]]:
    """Segments source-PTS-ordered, same-frame-aggregated observations
    into (run, boundary_time) pairs. `boundary_time` is the start_time
    of whatever real evidence closed this run -- either a blank marker
    (a confirmed "no subtitle" reading) or the next kept state's first
    observation -- or None if nothing in this evidence run says what
    happened after it (the caller must supply real processing-end
    evidence, or accept the documented instant-marker fallback -- see
    `reconstruct_cues_with_consensus`).

    A blank-text observation (`text == ""`, M4's confirmed-no-text
    marker) never starts or extends a run -- it only closes whatever
    run precedes it, so blank states never become subtitle Cues.

    Non-blank observations join the current run when EITHER (a) M4's
    own change-detection evidence says this was just a periodic
    confirmation of an unchanged state (or no trigger evidence exists
    at all -- e.g. non-OCR provenance), AND the text is similar enough
    to plausibly be a noisy reading of the same state; or they start a
    new run when M4's evidence says a real change was detected --
    regardless of how textually similar the new reading happens to be
    to the old one (see _STATE_CHANGE_TRIGGERS). Real M4 evidence always
    wins over a text-similarity guess.
    """
    entries: list[tuple[list[Observation], float | None]] = []
    current_run: list[Observation] = []

    for observation in ordered:
        if not observation.text:
            if current_run:
                entries.append((current_run, observation.start_time))
                current_run = []
            continue

        if not current_run:
            current_run = [observation]
            continue

        if _state_trigger(observation) in _STATE_CHANGE_TRIGGERS:
            entries.append((current_run, observation.start_time))
            current_run = [observation]
        elif character_similarity(current_run[-1].text, observation.text) >= similarity_threshold:
            current_run.append(observation)
        else:
            entries.append((current_run, observation.start_time))
            current_run = [observation]

    if current_run:
        entries.append((current_run, None))
    return entries


def _consensus_value(values: list[str], run: list[Observation]) -> tuple[str, int, int]:
    """Majority vote among `values` (one per observation in `run`, same
    order). Ties are broken by the tied candidate's highest-confidence
    observation, then by earliest occurrence in the run -- deterministic
    and independently explainable, no randomness.

    Returns (winning_value, distinct_value_count, winning_vote_count).
    """
    votes = Counter(values)
    top_count = max(votes.values())
    tied = [value for value in votes if votes[value] == top_count]
    if len(tied) == 1:
        return tied[0], len(votes), top_count

    def score(index_and_observation: tuple[int, Observation]) -> tuple[float, int]:
        index, observation = index_and_observation
        confidence = observation.confidence if observation.confidence is not None else -1.0
        return (confidence, -index)

    candidates = [
        (index, observation)
        for index, observation in enumerate(run)
        if values[index] in tied
    ]
    _best_index, best_observation = max(candidates, key=score)
    winning_value = values[run.index(best_observation)]
    return winning_value, len(votes), top_count


def _reconstruct_one_cue(
    run: list[Observation], boundary_time: float | None, processing_end_time: float | None
) -> tuple[Cue, ConsensusDiagnostics]:
    texts = [observation.text for observation in run]
    winning_text, distinct_text_count, top_count = _consensus_value(texts, run)

    languages = [observation.language for observation in run if observation.language]
    if languages:
        winning_language, _distinct, _top = _consensus_value(languages, run)
    else:
        winning_language = _UNDETERMINED_LANGUAGE

    observation_ids = tuple(
        member_id for observation in run for member_id in member_observation_ids(observation)
    )
    layer = LanguageLayer(
        language=winning_language,
        text=winning_text,
        observation_ids=observation_ids,
    )
    if boundary_time is not None:
        end_time = boundary_time
    elif processing_end_time is not None:
        end_time = processing_end_time
    else:
        # No better evidence available: an honest, documented fallback,
        # not a claim about real duration -- see the module docstring.
        end_time = run[-1].end_time
    cue = Cue(
        id=f"cue-{run[0].id}",
        start_time=run[0].start_time,
        end_time=end_time,
        language_layers=(layer,),
    )
    diagnostics = ConsensusDiagnostics(
        cue_id=cue.id,
        observation_count=len(run),
        distinct_text_count=distinct_text_count,
        agreement_ratio=top_count / len(run),
        had_disagreement=distinct_text_count > 1,
    )
    return cue, diagnostics


def reconstruct_cues_with_consensus(
    observations: list[Observation],
    *,
    similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
    processing_end_time: float | None = None,
) -> tuple[list[Cue], list[ConsensusDiagnostics]]:
    """Path A multi-frame consensus reconstruction: noisy OCR Observations
    -> stable, single-language Cues (ROADMAP.md Milestone 5).

    A deliberately independent seam from Path B's `reconstruct_cues`
    (application/reconstruction.py) -- that algorithm groups Observations
    by rolling character-overlap continuation (built for subtitle-file
    import, where every line is already clean and complete); this one
    groups temporally-adjacent OCR Observations by textual *similarity*
    (backstopped by M4's own state-change evidence) and resolves each
    group to one consensus reading by majority vote, because repeated
    OCR samples of the same real subtitle can each be slightly wrong in
    different ways.

    Algorithm (see docs/consensus/multi_frame_consensus.md for the full
    write-up: why this baseline, alternatives considered, failure modes,
    evidence):
    0. Aggregate same-frame regions (see `aggregate_same_frame_observations`):
       one OCR call can return multiple text regions (e.g. a two-line
       subtitle) sharing one frame_reference; these are combined into
       one reading, in reading order, before anything below runs -- they
       are never treated as sequential time states.
    1. Sort the aggregated readings by source-correct start_time (caller
       must have already scoped them to one evidence_run_id -- see
       `reconstruct_cues_for_evidence_run`).
    2. Group consecutive readings into "state runs" (see
       `_group_into_state_runs`): a run only splits on real M4
       state-change evidence when available (never guessed from text
       alone), with character-level similarity (CJK-safe) as the
       fallback signal when no such evidence exists. Blank-text readings
       (M4's confirmed-no-text marker) close the current run without
       becoming a Cue themselves.
    3. Within each run, pick the majority-vote text (and language) as
       the stable reading, keeping every supporting observation's id
       (expanded through same-frame aggregation, if any) in
       `LanguageLayer.observation_ids` for full provenance -- not just
       the winning one.
    4. Cue timing comes from state-transition semantics, not frame
       index/FPS: a Cue's end_time is the moment real evidence says this
       state stopped -- the next kept state's first reading, or an
       intervening blank marker, whichever is real evidence that
       actually closed this run. Only a run with no such evidence in
       this evidence run (typically the last one) uses
       `processing_end_time` if the caller supplied it (e.g. the
       analyzed range's real end), or otherwise honestly falls back to
       its own last reading's `end_time` -- documented as a
       known-imprecise fallback, not a duration claim.

    `similarity_threshold` is the one explainable, tunable knob (default
    0.5) -- see `_group_into_state_runs`. Deterministic: same input
    (any order) always produces the same output.
    """
    ordered = sorted(observations, key=lambda observation: observation.start_time)
    aggregated = aggregate_same_frame_observations(ordered)
    # Re-sort: aggregation can reorder within a frame group but
    # start_time ordering across frames must hold for grouping.
    aggregated = sorted(aggregated, key=lambda observation: observation.start_time)
    entries = _group_into_state_runs(aggregated, similarity_threshold)

    cues: list[Cue] = []
    diagnostics: list[ConsensusDiagnostics] = []
    for run, boundary_time in entries:
        cue, cue_diagnostics = _reconstruct_one_cue(run, boundary_time, processing_end_time)
        cues.append(cue)
        diagnostics.append(cue_diagnostics)
    return cues, diagnostics
