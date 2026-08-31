from __future__ import annotations

from dataclasses import dataclass

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation

_UNDETERMINED_LANGUAGE = "und"

_MIN_MEANINGFUL_OVERLAP = 2
"""A character-overlap of exactly 1 is not itself evidence of a real
rolling continuation -- it is exactly as likely to be a coincidental
shared character between two textually unrelated captions (e.g. "...a
lot" / "totally different topic" share a single "t"). Below this floor,
two temporally-overlapping captions are reported as
`segmentation_ambiguous`, not silently merged (ROADMAP M8: conservative
transformation -- when reconstruction cannot be confident, it keeps the
evidence and explains why, rather than guessing). This is a length
threshold on the character overlap itself, not a whitespace-token or
Latin-punctuation heuristic, so it applies identically to CJK and
Western text.

EXCEPTION: an overlap that consumes the run's ENTIRE accumulated text as
its own prefix (`overlap == len(accumulated_text)`) is real evidence of
growth no matter how short -- a one-character caption ("你") growing
into a longer one ("你好，世界") is a genuine rolling caption, not a
coincidence, because the WHOLE prior reading survives as a prefix. The
floor exists to guard against a coincidental PARTIAL match on a much
LONGER text (only the boundary character happens to line up), not to
penalize a short caption that grows in full. This exception is
evaluated identically for every script -- it is a length/containment
relationship, not a CJK-specific carve-out."""

_MAX_REPETITION_GAP_SECONDS = 1.0
"""Real growth/sliding continuation always requires genuine temporal
overlap (see `_classify_transition`) -- text overlap alone must never
merge two Cues, or two temporally unrelated captions that happen to
share text (or even be textually IDENTICAL) would be wrongly treated as
one rolling caption. The one narrow exception: an EXACT duplicate/
backtrack reading (no new content at all) that lands within this small,
fixed gap after the previous reading is still collapsed as a repeated
reading -- mirroring how a repeated caption can land in the next SRT
entry with a small gap rather than genuine time overlap. This is a
small, explicit, fixture-justified bound, not an unlimited window: two
identical captions minutes apart (see the far-distant-duplicate
regression) are NEVER collapsed."""


@dataclass(frozen=True)
class PathBDiagnostics:
    """Explainability record for one Path B reconstructed Cue (ROADMAP
    M8): which of the six named phenomena this Cue's reconstruction
    involved, each independently checkable against the source
    Observations. Never a probability -- a plain fact about what
    reconstruction decision was made and why, the same discipline as
    M5's `ConsensusDiagnostics` / M6's `MultilingualDiagnostics`.

    `source_order_issue`, `timing_collision`, and `segmentation_ambiguous`
    are exactly the "conservative, keep the evidence, explain why it's
    suspicious" cases; `rolling_growth`, `sliding_overlap`, and
    `repetition_collapsed` are the "confidently resolved, no review
    needed" cases (ROADMAP M8's framing: reliably restore what can be
    determined as rolling/noise, preserve and explain what can't).

    There is no separate "malformed_preserved" flag: `Observation`'s own
    domain invariants (`__post_init__`) already reject truly invalid
    records (negative/inverted timing) before reconstruction ever sees
    them, and `Pysubs2SubtitleFormatAdapter.parse` already drops
    blank/whitespace-only captions at the parse boundary. The realistic
    "malformed but recoverable" cases within this domain model --
    out-of-order source position, overlapping-but-unrelated entries,
    duplicate/backtracking readings -- are exactly what
    `source_order_issue`, `timing_collision`, and `repetition_collapsed`
    already name; inventing a distinct flag with no real fixture behind
    it would be diagnostic theater, not diagnostic truth.
    """

    cue_id: str
    source_order_issue: bool
    rolling_growth: bool
    sliding_overlap: bool
    repetition_collapsed: bool
    timing_collision: bool
    segmentation_ambiguous: bool


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


def _classify_transition(
    previous_observation: Observation, accumulated_text: str, next_observation: Observation
) -> tuple[str, int]:
    """Classifies the relationship between the current run and
    `next_observation` into one of four outcomes, returning
    `(classification, overlap_length)`:

    - `"continue"` -- real evidence of continuation: EITHER genuine
      temporal overlap plus a meaningful character overlap (>=
      `_MIN_MEANINGFUL_OVERLAP`, or a full-prefix match of any length --
      see that constant), OR an exact-duplicate/backtrack reading
      within `_MAX_REPETITION_GAP_SECONDS` of the previous one ending.
      Text overlap ALONE, with neither genuine temporal overlap nor a
      small bounded gap, is never sufficient -- two temporally unrelated
      captions never merge just because their text happens to line up,
      no matter how strong that textual match is (ROADMAP M8's
      "conservative, don't guess" principle applied to its most
      dangerous failure mode: actively merging two genuinely unrelated
      normal captions).
    - `"ambiguous"` -- temporal overlap AND a coincidental length-1
      character match on a text that is NOT a full-prefix match: not
      enough evidence to merge, but not clearly unrelated either.
    - `"collision"` -- temporal overlap with NO textual relationship at
      all: two genuinely different captions that happen to overlap in
      time (e.g. simultaneous dialogue).
    - `"separate"` -- no temporal overlap and no bounded-gap exact
      repeat; ordinary, unrelated captions (this is also the outcome
      for a real, non-trivial textual overlap that has NO temporal
      evidence at all -- e.g. two consecutive but non-overlapping
      sentences that coincidentally share a boundary word).
    """
    gap = next_observation.start_time - previous_observation.end_time
    temporal_overlap = gap < 0
    overlap = _character_overlap_length(accumulated_text, next_observation.text)

    if overlap == 0:
        return ("collision" if temporal_overlap else "separate"), overlap

    full_prefix_match = overlap == len(accumulated_text)
    exact_repeat_of_next = overlap == len(next_observation.text)

    if temporal_overlap and (overlap >= _MIN_MEANINGFUL_OVERLAP or full_prefix_match):
        return "continue", overlap
    if not temporal_overlap and exact_repeat_of_next and 0 <= gap <= _MAX_REPETITION_GAP_SECONDS:
        return "continue", overlap
    if temporal_overlap and overlap == 1:
        return "ambiguous", overlap
    if temporal_overlap:
        return "collision", overlap
    return "separate", overlap


def _continuation_kind(accumulated_text: str, next_text: str, overlap: int) -> str:
    """Given a `"continue"` classification, distinguishes:

    - `"repetition"` -- `next_text` adds no new content (it is fully
      contained within, or an exact repeat of, what's already
      accumulated) -- a duplicate or backtracking reading.
    - `"growth"` -- `next_text` retains the ENTIRE accumulated text as
      its own prefix and extends it further -- a classic growing-window
      rolling caption.
    - `"sliding"` -- a PARTIAL overlap where both sides extend beyond
      the shared region -- old content drops off the front while new
      content appends at the end.
    """
    if overlap == len(next_text):
        return "repetition"
    if overlap == len(accumulated_text) and len(next_text) > overlap:
        return "growth"
    return "sliding"


def _close_run(observations: list[Observation], merged_text: str) -> Cue:
    layer = LanguageLayer(
        language=observations[0].language or _UNDETERMINED_LANGUAGE,
        text=merged_text,
        observation_ids=tuple(observation.id for observation in observations),
    )
    return Cue(
        id=f"cue-{observations[0].id}",
        start_time=observations[0].start_time,
        # The LATEST end_time among every supporting Observation, not
        # just the last one in the run's (start_time-sorted) order --
        # a run's own end_times are not guaranteed to be monotonic with
        # start_time (e.g. a long first reading containing a shorter
        # later one), and truncating to the last member's end would
        # silently drop real evidence.
        end_time=max(observation.end_time for observation in observations),
        language_layers=(layer,),
    )


def reconstruct_cues_with_diagnostics(
    observations: list[Observation],
) -> tuple[list[Cue], list[PathBDiagnostics]]:
    """Path B reconstruction: Observation(s) -> Cue(s) + `PathBDiagnostics`
    (ROADMAP.md Milestone 8).

    Observations are processed in start_time order, but that order is
    NEVER silently substituted for the source's real order without a
    trace: `source_order_issue` is set on any Cue whose supporting
    Observations were not already in their original (file) order --
    diagnosis before fix, per ROADMAP M8's explicit requirement not to
    silent-sort away out-of-order evidence.

    A run requires real character-level textual continuation between
    each consecutive pair (`_classify_transition`); a coincidental
    length-1 character match or bare temporal overlap with no textual
    relationship never merges Cues, but is recorded
    (`segmentation_ambiguous` / `timing_collision`) rather than silently
    discarded -- conservative transformation, ROADMAP M8's other
    explicit requirement: normal/ambiguous input is never guessed at.
    """
    original_order_index = {observation.id: index for index, observation in enumerate(observations)}
    ordered = sorted(observations, key=lambda observation: observation.start_time)
    if not ordered:
        return [], []

    # Tracks the highest original (file) position emitted so far, across
    # ALL previously-closed runs -- not just the current one. A run
    # whose observations appeared, in the source file, BEFORE something
    # already emitted (despite sorting chronologically after it by
    # start_time) is real evidence the source file's cue order and its
    # timing order disagree -- exactly the case ROADMAP M8 requires be
    # diagnosed, not silently sorted away. A single-observation run can
    # never show internal disorder on its own, so this must be a
    # cross-run, running comparison, not a per-run-only check.
    max_original_index_emitted = -1

    cues: list[Cue] = []
    diagnostics: list[PathBDiagnostics] = []
    run = [ordered[0]]
    run_text = ordered[0].text
    rolling_growth = False
    sliding_overlap = False
    repetition_collapsed = False
    timing_collision = False
    segmentation_ambiguous = False

    def _emit_current_run() -> None:
        nonlocal max_original_index_emitted
        run_indices = [original_order_index[observation.id] for observation in run]
        source_order_issue = (
            run_indices != sorted(run_indices) or min(run_indices) < max_original_index_emitted
        )
        max_original_index_emitted = max(max_original_index_emitted, max(run_indices))
        diagnostics.append(
            PathBDiagnostics(
                cue_id=f"cue-{run[0].id}",
                source_order_issue=source_order_issue,
                rolling_growth=rolling_growth,
                sliding_overlap=sliding_overlap,
                repetition_collapsed=repetition_collapsed,
                timing_collision=timing_collision,
                segmentation_ambiguous=segmentation_ambiguous,
            )
        )
        cues.append(_close_run(run, run_text))

    for observation in ordered[1:]:
        classification, overlap = _classify_transition(run[-1], run_text, observation)
        if classification == "continue":
            kind = _continuation_kind(run_text, observation.text, overlap)
            if kind == "repetition":
                repetition_collapsed = True
            elif kind == "growth":
                rolling_growth = True
            else:
                sliding_overlap = True
            run.append(observation)
            run_text += observation.text[overlap:]
            continue

        _emit_current_run()
        run = [observation]
        run_text = observation.text
        rolling_growth = False
        sliding_overlap = False
        repetition_collapsed = False
        timing_collision = classification == "collision"
        segmentation_ambiguous = classification == "ambiguous"

    _emit_current_run()
    return cues, diagnostics


def reconstruct_cues(observations: list[Observation]) -> list[Cue]:
    """Thin wrapper over `reconstruct_cues_with_diagnostics` for callers
    that only need the reconstructed Cues (e.g. `run_thin_path_b`)."""
    cues, _diagnostics = reconstruct_cues_with_diagnostics(observations)
    return cues
