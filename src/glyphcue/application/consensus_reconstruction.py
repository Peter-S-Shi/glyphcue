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
that mark a reading as a CANDIDATE new-state boundary -- not a
confirmed one. "change_detected" in particular comes from a cheap
pixel-difference detector: a moving/flickering background behind static
burned-in text, a compression artifact, or similar can cross that
threshold without the subtitle itself changing. A candidate is only
promoted to a real run boundary once subsequent evidence continues to
support the new reading -- see `_group_into_state_runs` and
`_confirmed_by_next_evidence`. "periodic_confirmation" (or no trigger
info at all, e.g. non-M4 provenance) never triggers this candidate
mechanism at all: it falls straight to similarity voting, since it
means "state believed unchanged" or "unknown," never "state changed"."""


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


def _run_anchor_text(run: list[Observation]) -> str:
    """The text every subsequent grouping decision for `run` compares
    against: its FIRST member's text -- the reading that originally
    started (or confirmed) this run -- not its last member's.

    Using the last member would drift once a rejected candidate or an
    absorbed blank marker becomes the run's newest entry: e.g. a
    momentary garbage misread absorbed as an outlier must not itself
    become the new "current state" that the *next* real reading is
    compared against (it would then wrongly look like a state change).
    `run[0]` is always non-blank by construction -- a run is only ever
    started from a non-blank observation."""
    return run[0].text


def _next_non_blank_text(ordered: list[Observation], from_index: int) -> str | None:
    """The text of the first non-blank observation strictly after
    `ordered[from_index]`, or None if none exists."""
    for observation in ordered[from_index + 1 :]:
        if observation.text:
            return observation.text
    return None


def _confirmed_by_next_evidence(
    ordered: list[Observation], index: int, candidate_text: str, similarity_threshold: float
) -> bool:
    """Whether a candidate state-change boundary at `ordered[index]`
    should be treated as a real, confirmed new state, per ROADMAP M5's
    corrective: a cheap visual-change detection is only candidate
    evidence, not a confirmed state change. Confirmed when the next
    real (non-blank) reading continues to support the candidate's text;
    rejected when it doesn't. With no further evidence at all (the
    candidate is the last reading in this evidence run), there is
    nothing to contradict it, so it is trusted by default.
    """
    next_text = _next_non_blank_text(ordered, index)
    if next_text is None:
        return True
    return character_similarity(candidate_text, next_text) >= similarity_threshold


def _group_into_state_runs(
    ordered: list[Observation], similarity_threshold: float
) -> list[tuple[list[Observation], float | None]]:
    """Segments source-PTS-ordered, same-frame-aggregated observations
    into (run, boundary_time) pairs. `boundary_time` is the start_time
    of whatever real evidence closed this run -- either the FIRST of a
    confirmed sequence of blank-marker candidates, or the next kept
    state's first observation -- or None if nothing in this evidence
    run says what happened after it (the caller must supply real
    processing-end evidence, or accept the documented instant-marker
    fallback -- see `reconstruct_cues_with_consensus`).

    Both blank markers and "change_detected"/"first_frame" readings are
    treated as CANDIDATES, not confirmed facts, per ROADMAP M5's
    corrective:

    - A blank-text observation (M4's OCR-empty marker) never
      immediately ends a run. It -- and any further consecutive blank
      readings -- are held as pending candidates until the next
      non-blank reading arrives. If that reading still matches the
      run's real text, the blank span was a transient OCR-empty glitch:
      it is rejected, the held blank observations are kept in the run
      for provenance, and the run continues uninterrupted. If it
      doesn't match, the blank gap is confirmed real, and the run ends
      at the FIRST blank candidate's start_time (not the last) -- that
      is when the state actually started going blank. With no further
      evidence at all, a pending blank is confirmed by default (see
      `reconstruct_cues_with_consensus`'s trailing handling).
    - A "change_detected"/"first_frame" reading whose text genuinely
      differs from the run's current text is a CANDIDATE new state --
      see `_confirmed_by_next_evidence`. If confirmed, it starts a new
      run; if not, it is absorbed into the current run as an outlier,
      exactly like a periodic-confirmation misread. A
      "change_detected" reading whose text is unchanged from the run's
      current text needed no candidate/confirmation step at all: no
      real state change is even being proposed, so it is absorbed
      immediately, same as any other matching reading.
    - Everything else (no trigger evidence, or "periodic_confirmation")
      falls back to character-level similarity voting, the same
      CJK-safe mechanism as before.
    """
    entries: list[tuple[list[Observation], float | None]] = []
    current_run: list[Observation] = []
    pending_blanks: list[Observation] = []

    for index, observation in enumerate(ordered):
        if not observation.text:
            if current_run:
                pending_blanks.append(observation)
            continue  # a leading blank with no run yet has nothing to affect

        if pending_blanks:
            reference_text = _run_anchor_text(current_run)
            if character_similarity(reference_text, observation.text) >= similarity_threshold:
                # OCR-empty glitch, not a real blank gap: keep the blank
                # reads for provenance, the run continues uninterrupted.
                current_run.extend(pending_blanks)
            else:
                # Confirmed real blank gap: the run really ended at the
                # FIRST blank candidate, not the last.
                entries.append((current_run, pending_blanks[0].start_time))
                current_run = []
            pending_blanks = []

        if not current_run:
            current_run = [observation]
            continue

        reference_text = _run_anchor_text(current_run)
        if (
            _state_trigger(observation) in _STATE_CHANGE_TRIGGERS
            and observation.text != reference_text
        ):
            if _confirmed_by_next_evidence(ordered, index, observation.text, similarity_threshold):
                entries.append((current_run, observation.start_time))
                current_run = [observation]
            else:
                current_run.append(observation)  # rejected candidate, absorbed as an outlier
        elif character_similarity(reference_text, observation.text) >= similarity_threshold:
            current_run.append(observation)
        else:
            entries.append((current_run, observation.start_time))
            current_run = [observation]

    if pending_blanks:
        # No further evidence after the pending blank(s): confirmed by
        # default, same policy as a state-change candidate with nothing
        # to contradict it.
        if current_run:
            entries.append((current_run, pending_blanks[0].start_time))
        current_run = []
    if current_run:
        entries.append((current_run, None))
    return entries


def _tie_break_index(candidate_indices: list[int], run: list[Observation]) -> int:
    """Deterministic, explainable tie-break shared by text and language
    voting: the tied candidate's highest-confidence observation wins,
    then earliest occurrence in the run. Returns the winning index into
    `run`."""

    def score(index: int) -> tuple[float, int]:
        confidence = run[index].confidence if run[index].confidence is not None else -1.0
        return (confidence, -index)

    return max(candidate_indices, key=score)


def _consensus_value(values: list[str], run: list[Observation]) -> tuple[str, int, int]:
    """Majority vote among `values` (one per observation in `run`, same
    order and same length -- e.g. Observation.text, which is never
    None so this list is always fully aligned with `run`).

    Returns (winning_value, distinct_value_count, winning_vote_count).
    """
    votes = Counter(values)
    top_count = max(votes.values())
    tied = [value for value in votes if votes[value] == top_count]
    if len(tied) == 1:
        return tied[0], len(votes), top_count

    candidate_indices = [index for index, value in enumerate(values) if value in tied]
    winning_index = _tie_break_index(candidate_indices, run)
    return values[winning_index], len(votes), top_count


def _consensus_language(run: list[Observation]) -> str:
    """Majority vote over `run`'s languages, excluding observations with
    no reported language (`None`) from the vote entirely -- falling
    back to `_UNDETERMINED_LANGUAGE` only if NONE of them report one.

    Reads `observation.language` straight off `run` by index rather
    than voting over a separately built, pre-filtered list: a
    pre-filtered list is shorter than `run` whenever any observation
    has no language, which previously caused `_consensus_value`'s
    `values[index]` tie-break lookup (indexed by `enumerate(run)`, the
    UNfiltered length) to read past the end of the filtered list --
    an IndexError whenever a tie occurred with a None-language
    observation present. Working directly off `run`'s own indices makes
    that misalignment structurally impossible.
    """
    candidate_indices = [index for index, observation in enumerate(run) if observation.language]
    if not candidate_indices:
        return _UNDETERMINED_LANGUAGE

    votes = Counter(run[index].language for index in candidate_indices)
    top_count = max(votes.values())
    tied = [language for language in votes if votes[language] == top_count]
    if len(tied) == 1:
        return tied[0]

    tied_indices = [index for index in candidate_indices if run[index].language in tied]
    winning_index = _tie_break_index(tied_indices, run)
    return run[winning_index].language


def _reconstruct_one_cue(
    run: list[Observation], boundary_time: float | None, processing_end_time: float | None
) -> tuple[Cue, ConsensusDiagnostics]:
    texts = [observation.text for observation in run]
    winning_text, distinct_text_count, top_count = _consensus_value(texts, run)

    winning_language = _consensus_language(run)

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
