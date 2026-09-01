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
group_into_state_runs) -- a detected change is only ever treated as
CANDIDATE evidence, never trusted outright, and an unconfirmed
candidate never gets to override the vote on its own (see
`_confirmed_by_next_evidence` and `_reconstruct_one_cue`)."""

_STATE_CHANGE_TRIGGERS = {"first_frame", "change_detected"}
"""M4 trigger reasons (ChangeTriggeredOcrPolicy.last_trigger_reason,
threaded through Observation.provenance.detail[STATE_TRIGGER_DETAIL_KEY])
that mark a reading as a CANDIDATE new-state boundary -- not a
confirmed one. "change_detected" in particular comes from a cheap
pixel-difference detector: a moving/flickering background behind static
burned-in text, a compression artifact, or similar can cross that
threshold without the subtitle itself changing. A candidate is only
promoted to a real run boundary once subsequent evidence continues to
support the new reading -- see `group_into_state_runs` and
`_confirmed_by_next_evidence`. A TRAILING candidate -- one with no
further evidence at all after it in the evidence run -- is neither
confirmed nor refuted: it never opens a new run on its own, and it is
excluded from the run's own text/language vote so it can't silently
override the already-established reading just by carrying a higher OCR
confidence score. "periodic_confirmation" (or no trigger info at all,
e.g. non-M4 provenance) never triggers this candidate mechanism at
all: it falls straight to similarity voting, since it means "state
believed unchanged" or "unknown," never "state changed"."""


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


_MIN_TRAILING_BLANK_CONFIRMATION = 2
"""A single trailing OCR-empty (blank) candidate at the very end of an
evidence run has no later reading to confirm or refute it, so on its
own it must not truncate the current Cue -- the same "no evidence to
contradict it" situation is just as inconclusive as it is for a
trailing state-change candidate (see `_confirmed_by_next_evidence`).
Two or more consecutive trailing blank reads is treated as the minimum
sustained evidence needed to confirm a real blank gap even with no
later non-blank reading to compare against."""


def _confirmed_by_next_evidence(
    ordered: list[Observation], index: int, candidate_text: str, similarity_threshold: float
) -> bool | None:
    """Whether a candidate state-change boundary at `ordered[index]`
    should be treated as a real, confirmed new state, per ROADMAP M5's
    corrective: a cheap visual-change detection is only candidate
    evidence, not a confirmed state change.

    Returns True when the next real (non-blank) reading continues to
    support the candidate's text (confirmed); False when it reverts to
    something else (rejected, a false-positive detection); or None when
    there is no further evidence at all in this evidence run (a
    TRAILING candidate). None is deliberately distinct from True: with
    nothing to contradict it, a trailing candidate is not *proven*
    wrong, but it is not confirmed either -- it must not be trusted to
    open a new Cue, and it must not be allowed to win a text/language
    vote against the run's already-established reading just because it
    happens to carry a higher OCR confidence (see `_reconstruct_one_cue`).
    """
    next_text = _next_non_blank_text(ordered, index)
    if next_text is None:
        return None
    return character_similarity(candidate_text, next_text) >= similarity_threshold


def group_into_state_runs(
    ordered: list[Observation], similarity_threshold: float
) -> list[tuple[list[Observation], float | None, set[str]]]:
    """Segments source-PTS-ordered, same-frame-aggregated observations
    into (run, boundary_time, non_voting_ids) triples. `boundary_time`
    is the start_time of whatever real evidence closed this run --
    either the FIRST of a confirmed sequence of blank-marker
    candidates, or the next kept state's first observation -- or None
    if nothing in this evidence run says what happened after it (the
    caller must supply real processing-end evidence, or accept the
    documented instant-marker fallback -- see
    `reconstruct_cues_with_consensus`). `non_voting_ids` is the set of
    `Observation.id`s within `run` that are kept for provenance but
    must NOT count toward that run's text/language majority vote (see
    `_reconstruct_one_cue`) -- unconfirmed trailing state-change
    candidates land here; blank-text observations are always excluded
    from the vote regardless of this set, since an empty reading can
    never sensibly win a text vote.

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
      evidence at all (the blanks are trailing), at least
      `_MIN_TRAILING_BLANK_CONFIRMATION` consecutive blank reads are
      required to confirm the gap; fewer than that is inconclusive and
      is absorbed into the run instead, uninterrupted, exactly like a
      rejected mid-run blank.
    - A "change_detected"/"first_frame" reading whose text genuinely
      differs from the run's current text is a CANDIDATE new state --
      see `_confirmed_by_next_evidence`. If confirmed, it starts a new
      run. If refuted by a later real reading, it is absorbed into the
      current run as an outlier and still counts toward that run's
      vote, exactly like a periodic-confirmation misread. If there is
      no later evidence at all (a trailing candidate), it is likewise
      absorbed into the current run for provenance, but it is added to
      `non_voting_ids` so it cannot itself decide the run's winning
      text/language. A "change_detected" reading whose text is
      unchanged from the run's current text needed no
      candidate/confirmation step at all: no real state change is even
      being proposed, so it is absorbed immediately, same as any other
      matching reading.
    - Everything else (no trigger evidence, or "periodic_confirmation")
      falls back to character-level similarity voting, the same
      CJK-safe mechanism as before.
    """
    entries: list[tuple[list[Observation], float | None, set[str]]] = []
    current_run: list[Observation] = []
    non_voting_ids: set[str] = set()
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
                entries.append((current_run, pending_blanks[0].start_time, non_voting_ids))
                current_run = []
                non_voting_ids = set()
            pending_blanks = []

        if not current_run:
            current_run = [observation]
            continue

        reference_text = _run_anchor_text(current_run)
        if (
            _state_trigger(observation) in _STATE_CHANGE_TRIGGERS
            and observation.text != reference_text
        ):
            resolution = _confirmed_by_next_evidence(
                ordered, index, observation.text, similarity_threshold
            )
            if resolution is True:
                entries.append((current_run, observation.start_time, non_voting_ids))
                current_run = [observation]
                non_voting_ids = set()
            elif resolution is False:
                current_run.append(observation)  # rejected candidate, absorbed as an outlier
            else:  # None: trailing candidate, no evidence to confirm or refute it
                current_run.append(observation)
                non_voting_ids.add(observation.id)
        elif character_similarity(reference_text, observation.text) >= similarity_threshold:
            current_run.append(observation)
        else:
            entries.append((current_run, observation.start_time, non_voting_ids))
            current_run = [observation]
            non_voting_ids = set()

    if pending_blanks:
        if len(pending_blanks) >= _MIN_TRAILING_BLANK_CONFIRMATION:
            # Sustained trailing blank evidence: confirmed, backdated to
            # the FIRST blank candidate, same as a mid-run confirmed gap.
            if current_run:
                entries.append((current_run, pending_blanks[0].start_time, non_voting_ids))
            current_run = []
            non_voting_ids = set()
        elif current_run:
            # A single trailing blank candidate has nothing to confirm
            # or refute it: inconclusive, absorbed for provenance only,
            # the run continues uninterrupted (it is never a voter --
            # see the blank-exclusion rule above).
            current_run.extend(pending_blanks)
    if current_run:
        entries.append((current_run, None, non_voting_ids))
    return entries


def tie_break_index(candidate_indices: list[int], run: list[Observation]) -> int:
    """Deterministic, explainable tie-break shared by text and language
    voting: the tied candidate's highest-confidence observation wins,
    then earliest occurrence in the run. Returns the winning index into
    `run`."""

    def score(index: int) -> tuple[float, int]:
        confidence = run[index].confidence if run[index].confidence is not None else -1.0
        return (confidence, -index)

    return max(candidate_indices, key=score)


def consensus_value(values: list[str], run: list[Observation]) -> tuple[str, int, int]:
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
    winning_index = tie_break_index(candidate_indices, run)
    return values[winning_index], len(votes), top_count


def _consensus_language(run: list[Observation]) -> str:
    """Majority vote over `run`'s languages, excluding observations with
    no reported language (`None`) from the vote entirely -- falling
    back to `_UNDETERMINED_LANGUAGE` only if NONE of them report one.

    Reads `observation.language` straight off `run` by index rather
    than voting over a separately built, pre-filtered list: a
    pre-filtered list is shorter than `run` whenever any observation
    has no language, which previously caused `consensus_value`'s
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
    winning_index = tie_break_index(tied_indices, run)
    return run[winning_index].language


def resolve_cue_timing(
    run: list[Observation], boundary_time: float | None, processing_end_time: float | None
) -> tuple[float, float]:
    """The shared start/end-time resolution rule for a reconstructed
    run, factored out so a caller reconstructing something other than a
    single-language Cue from the same run structure (see Milestone 6's
    multilingual reconstruction, which reuses `group_into_state_runs`
    directly) times its own Cue identically, not by re-deriving this
    fallback chain a second time.

    `boundary_time` wins when real evidence closed the run; otherwise
    `processing_end_time` if the caller supplied it; otherwise the
    run's own last reading's `end_time` -- an honest, documented
    fallback, not a duration claim (see `reconstruct_cues_with_consensus`).
    """
    start_time = run[0].start_time
    if boundary_time is not None:
        end_time = boundary_time
    elif processing_end_time is not None:
        end_time = processing_end_time
    else:
        end_time = run[-1].end_time
    return start_time, end_time


def _reconstruct_one_cue(
    run: list[Observation],
    boundary_time: float | None,
    processing_end_time: float | None,
    non_voting_ids: set[str],
) -> tuple[Cue, ConsensusDiagnostics]:
    # The text/language vote only ever counts confirmed evidence: blank
    # (OCR-empty) readings can never sensibly win a text vote, and
    # unconfirmed trailing candidates (see `group_into_state_runs`)
    # must not override the run's established reading just because they
    # carry a higher OCR confidence. Both are still kept in `run` --
    # and therefore in `observation_ids` below -- for full provenance.
    voting_run = [
        observation
        for observation in run
        if observation.text and observation.id not in non_voting_ids
    ]
    texts = [observation.text for observation in voting_run]
    winning_text, distinct_text_count, top_count = consensus_value(texts, voting_run)

    winning_language = _consensus_language(voting_run)

    observation_ids = tuple(
        member_id for observation in run for member_id in member_observation_ids(observation)
    )
    layer = LanguageLayer(
        language=winning_language,
        text=winning_text,
        observation_ids=observation_ids,
    )
    start_time, end_time = resolve_cue_timing(run, boundary_time, processing_end_time)
    cue = Cue(
        id=f"cue-{run[0].id}",
        start_time=start_time,
        end_time=end_time,
        language_layers=(layer,),
    )
    diagnostics = ConsensusDiagnostics(
        cue_id=cue.id,
        observation_count=len(run),
        distinct_text_count=distinct_text_count,
        agreement_ratio=top_count / len(voting_run),
        had_disagreement=distinct_text_count > 1,
    )
    return cue, diagnostics


def _consolidate_adjacent_same_text_cues(
    cues: list[Cue],
    diagnostics: list[ConsensusDiagnostics],
) -> tuple[list[Cue], list[ConsensusDiagnostics]]:
    """Merges adjacent reconstructed Cues with identical normalized
    subtitle text across editing cuts/transitions when no credible blank gap exists between them.
    """
    if not cues:
        return [], []

    merged_cues: list[Cue] = [cues[0]]
    merged_diag: list[ConsensusDiagnostics] = [diagnostics[0]]

    for cue, diag in zip(cues[1:], diagnostics[1:]):
        prev_cue = merged_cues[-1]
        prev_diag = merged_diag[-1]

        prev_text = prev_cue.language_layers[0].text if prev_cue.language_layers else ""
        curr_text = cue.language_layers[0].text if cue.language_layers else ""

        # Check if adjacent (within 0.15s tolerance) and identical text
        is_adjacent = cue.start_time <= prev_cue.end_time + 0.15
        same_text = prev_text.strip() == curr_text.strip() and bool(prev_text.strip())

        if is_adjacent and same_text:
            new_end_time = max(prev_cue.end_time, cue.end_time)
            combined_obs_ids = prev_cue.language_layers[0].observation_ids + cue.language_layers[0].observation_ids
            dedup_obs_ids = tuple(dict.fromkeys(combined_obs_ids))

            merged_layer = LanguageLayer(
                language=prev_cue.language_layers[0].language or (cue.language_layers[0].language if cue.language_layers else None),
                text=prev_text,
                observation_ids=dedup_obs_ids,
            )
            merged_cues[-1] = Cue(
                id=prev_cue.id,
                start_time=prev_cue.start_time,
                end_time=new_end_time,
                language_layers=(merged_layer,),
                review_state=prev_cue.review_state,
            )
            combined_votes = list(prev_diag.votes) + list(diag.votes)
            merged_diag[-1] = ConsensusDiagnostics(
                consensus_text=prev_diag.consensus_text,
                consensus_language=prev_diag.consensus_language,
                votes=tuple(combined_votes),
                winning_vote_count=prev_diag.winning_vote_count + diag.winning_vote_count,
                total_vote_count=prev_diag.total_vote_count + diag.total_vote_count,
                majority_ratio=(
                    (prev_diag.winning_vote_count + diag.winning_vote_count)
                    / max(1, prev_diag.total_vote_count + diag.total_vote_count)
                ),
            )
        else:
            merged_cues.append(cue)
            merged_diag.append(diag)

    return merged_cues, merged_diag


def reconstruct_cues_with_consensus(
    observations: list[Observation],
    *,
    similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
    processing_end_time: float | None = None,
) -> tuple[list[Cue], list[ConsensusDiagnostics]]:
    """Path A multi-frame consensus reconstruction: noisy OCR Observations
    -> stable, single-language Cues (ROADMAP.md Milestone 5).
    """
    ordered = sorted(observations, key=lambda observation: observation.start_time)
    aggregated = aggregate_same_frame_observations(ordered)
    # Re-sort: aggregation can reorder within a frame group but
    # start_time ordering across frames must hold for grouping.
    aggregated = sorted(aggregated, key=lambda observation: observation.start_time)
    entries = group_into_state_runs(aggregated, similarity_threshold)

    cues: list[Cue] = []
    diagnostics: list[ConsensusDiagnostics] = []
    for run, boundary_time, non_voting_ids in entries:
        cue, cue_diagnostics = _reconstruct_one_cue(
            run, boundary_time, processing_end_time, non_voting_ids
        )
        cues.append(cue)
        diagnostics.append(cue_diagnostics)

    return _consolidate_adjacent_same_text_cues(cues, diagnostics)
