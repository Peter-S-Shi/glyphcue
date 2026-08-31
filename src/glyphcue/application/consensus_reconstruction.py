from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

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
captions that happen to share a few characters."""


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


def _group_into_state_runs(
    ordered: list[Observation], similarity_threshold: float
) -> list[list[Observation]]:
    """Segments source-PTS-ordered observations into runs that each
    represent one real, stable subtitle state.

    Consecutive observations join the same run when their text is
    similar enough (character-level, CJK-safe -- see
    `character_similarity`) to plausibly be noisy readings of the same
    state; a genuinely new state starts a new run. This is the
    "state-stabilization" baseline: no timing-overlap heuristic is used
    here (unlike M1's Path B algorithm) because M4's OCR calls are
    already sparse/selective, not a dense frame stream -- adjacency in
    the observation list already reflects real temporal adjacency.
    """
    if not ordered:
        return []

    runs: list[list[Observation]] = [[ordered[0]]]
    for observation in ordered[1:]:
        current_run = runs[-1]
        if character_similarity(current_run[-1].text, observation.text) >= similarity_threshold:
            current_run.append(observation)
        else:
            runs.append([observation])
    return runs


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
    run: list[Observation], next_run_start_time: float | None
) -> tuple[Cue, ConsensusDiagnostics]:
    texts = [observation.text for observation in run]
    winning_text, distinct_text_count, top_count = _consensus_value(texts, run)

    languages = [observation.language for observation in run if observation.language]
    if languages:
        winning_language, _distinct, _top = _consensus_value(languages, run)
    else:
        winning_language = _UNDETERMINED_LANGUAGE

    layer = LanguageLayer(
        language=winning_language,
        text=winning_text,
        observation_ids=tuple(observation.id for observation in run),
    )
    end_time = next_run_start_time if next_run_start_time is not None else run[-1].end_time
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
) -> tuple[list[Cue], list[ConsensusDiagnostics]]:
    """Path A multi-frame consensus reconstruction: noisy OCR Observations
    -> stable, single-language Cues (ROADMAP.md Milestone 5).

    A deliberately independent seam from Path B's `reconstruct_cues`
    (application/reconstruction.py) -- that algorithm groups Observations
    by rolling character-overlap continuation (built for subtitle-file
    import, where every line is already clean and complete); this one
    groups temporally-adjacent OCR Observations by textual *similarity*
    and resolves each group to one consensus reading by majority vote,
    because repeated OCR samples of the same real subtitle can each be
    slightly wrong in different ways.

    Algorithm (see docs/consensus/multi_frame_consensus.md for the full
    write-up: why this baseline, alternatives considered, failure modes,
    evidence):
    1. Sort observations by source-correct start_time (caller must have
       already scoped them to one evidence_run_id -- see
       `reconstruct_cues_for_evidence_run`).
    2. Group consecutive observations into "state runs" using
       character-level text similarity (CJK-safe, no whitespace
       tokenization) -- see `_group_into_state_runs`.
    3. Within each run, pick the majority-vote text (and language) as
       the stable reading, keeping every supporting observation's id in
       `LanguageLayer.observation_ids` for full provenance -- not just
       the winning one.
    4. Cue timing comes from state-transition semantics, not frame
       index/FPS: a Cue's end_time is the moment the *next* state was
       confirmed (the next run's first observation's start_time), since
       that is the real evidence for when this state stopped being
       shown. Only the last run (no known next state) falls back to its
       own last observation's end_time.

    `similarity_threshold` is the one explainable, tunable knob (default
    0.5) -- see `_group_into_state_runs`. Deterministic: same input
    (any order) always produces the same output.
    """
    ordered = sorted(observations, key=lambda observation: observation.start_time)
    runs = _group_into_state_runs(ordered, similarity_threshold)

    cues: list[Cue] = []
    diagnostics: list[ConsensusDiagnostics] = []
    for index, run in enumerate(runs):
        next_run_start_time = runs[index + 1][0].start_time if index + 1 < len(runs) else None
        cue, cue_diagnostics = _reconstruct_one_cue(run, next_run_start_time)
        cues.append(cue)
        diagnostics.append(cue_diagnostics)
    return cues, diagnostics
