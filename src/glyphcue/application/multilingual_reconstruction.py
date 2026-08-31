from __future__ import annotations

from dataclasses import dataclass

from glyphcue.application.consensus_reconstruction import (
    ConsensusDiagnostics,
    consensus_value,
    group_into_state_runs,
    reconstruct_cues_with_consensus,
    resolve_cue_timing,
)
from glyphcue.application.frame_reading_aggregation import (
    aggregate_same_frame_observations,
    member_observation_ids,
)
from glyphcue.application.language_layer_assignment import assign_observations_to_languages
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation
from glyphcue.domain.track_group import TrackGroup

_DEFAULT_SIMILARITY_THRESHOLD = 0.5


@dataclass(frozen=True)
class MultilingualDiagnostics:
    """Explainability record for one reconstructed multilingual Cue,
    the M6 counterpart to M5's `ConsensusDiagnostics` -- not persisted,
    a same-call companion to the Cue list for tests, logging, and
    evaluation tooling (ROADMAP M6 acceptance gate 6: "multilingual
    separation quality is evaluated").
    """

    cue_id: str
    languages_expected: tuple[str, ...]
    languages_present: tuple[str, ...]
    missing_languages: tuple[str, ...]
    ambiguous_languages: tuple[str, ...]
    """Languages whose text came from `assign_observations_to_languages`'s
    geometry fallback rather than a decisive script/elimination/strict-
    hint classification -- real, surfaced uncertainty (ROADMAP M6
    scope: "if still no evidence, an explicit ambiguity/degraded
    diagnostic, not a guess") rather than a confident-looking result
    that was actually a coin flip."""


def _canonicalize_frame_order(
    ordered: list[Observation], expected_languages: tuple[str, ...]
) -> list[Observation]:
    """Reorders each frame's same-frame OCR regions into a stable,
    language-based canonical order (`expected_languages`' own order)
    before M5's same-frame aggregation runs.

    `group_into_state_runs`' fallback boundary signal (used whenever
    real `state_trigger` evidence isn't available) is character
    similarity between consecutive frames' *joined* multi-region text.
    Without this canonicalization, two frames of the exact same stable
    bilingual subtitle could have their regions returned by OCR in a
    different order (region detection order is not a guaranteed-stable
    signal) and join into two differently-ordered strings that look
    like two unrelated states -- wrongly splitting one stable Cue into
    two. Reusing `assign_observations_to_languages` here (the same
    layer-separation logic used for the final per-language vote) keeps
    that ordering decision in exactly one place.
    """
    frame_groups: dict[str, list[Observation]] = {}
    order: list[str] = []
    for observation in ordered:
        key = observation.frame_reference or f"__no_frame__{observation.id}"
        if key not in frame_groups:
            frame_groups[key] = []
            order.append(key)
        frame_groups[key].append(observation)

    canonical: list[Observation] = []
    for key in order:
        group = frame_groups[key]
        if len(group) == 1:
            canonical.append(group[0])
            continue
        buckets, _ambiguous = assign_observations_to_languages(group, expected_languages)
        classified_ids: set[str] = set()
        for language in expected_languages:
            for cluster in buckets[language]:
                canonical.extend(cluster)
                classified_ids.update(observation.id for observation in cluster)
        # Anything assign_observations_to_languages didn't place (should
        # not normally happen -- it folds leftovers into the nearest
        # bucket) is still appended, so no original evidence is dropped.
        canonical.extend(observation for observation in group if observation.id not in classified_ids)
    return canonical


def reconstruct_multilingual_cues_for_track_group(
    observations: list[Observation],
    track_group: TrackGroup,
    *,
    similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
    processing_end_time: float | None = None,
) -> tuple[list[Cue], list[ConsensusDiagnostics] | list[MultilingualDiagnostics]]:
    """Milestone 6: reconstructs `observations` (real per-region M4
    evidence for one Track Group's ROI, scoped to one evidence run) into
    Cues whose `language_layers` follow `track_group.languages`.

    A single-language Track Group (`len(track_group.languages) == 1`,
    the M5 case) is a direct pass-through to
    `reconstruct_cues_with_consensus` -- not a reimplementation that
    happens to agree with it, an actual call to the same function, so M5
    behavior and its regression suite are preserved exactly, not just
    approximately.

    A multi-language Track Group reuses M5's own run-grouping
    (`group_into_state_runs`) UNCHANGED to decide *when* state
    boundaries happen -- the same shared frame timestamps and
    `state_trigger` evidence apply to every language layer equally,
    since one physical video frame is one OCR-triggering event
    regardless of how many languages are read from it. What's new is
    *what* each run's text is: instead of M5's single joined-string
    vote, each run's real, un-joined per-region Observations (recovered
    via `member_observation_ids`, never the joined string
    `aggregate_same_frame_observations` produces) are split into one
    bucket per expected language (`assign_observations_to_languages`)
    and each bucket gets its own majority-vote text
    (`consensus_value`) -- so multi-region same-frame aggregation still
    happens, just per language instead of across all of them at once.

    Layer order in every Cue is always `track_group.languages`' own
    configured order -- never whatever order OCR happened to detect
    regions in for a given frame -- so ordering is stable across every
    Cue and every frame (ROADMAP M6 acceptance gate 4).

    A language with zero contributing observations in a run is a
    missing/asymmetric layer (ROADMAP M6 acceptance gate 5): it gets an
    explicit, empty-text `LanguageLayer` plus a `MultilingualDiagnostics`
    entry naming it -- never fabricated text, never a schema change.
    """
    if len(track_group.languages) == 1:
        return reconstruct_cues_with_consensus(
            observations,
            similarity_threshold=similarity_threshold,
            processing_end_time=processing_end_time,
        )

    raw_by_id = {observation.id: observation for observation in observations}
    ordered = sorted(observations, key=lambda observation: observation.start_time)
    canonical = _canonicalize_frame_order(ordered, track_group.languages)
    aggregated = sorted(
        aggregate_same_frame_observations(canonical), key=lambda observation: observation.start_time
    )
    entries = group_into_state_runs(aggregated, similarity_threshold)

    cues: list[Cue] = []
    diagnostics: list[MultilingualDiagnostics] = []
    for run, boundary_time, non_voting_ids in entries:
        cue, cue_diagnostics = _reconstruct_one_multilingual_cue(
            run, boundary_time, processing_end_time, non_voting_ids, track_group.languages, raw_by_id
        )
        cues.append(cue)
        diagnostics.append(cue_diagnostics)
    return cues, diagnostics


def _reconstruct_one_multilingual_cue(
    run: list[Observation],
    boundary_time: float | None,
    processing_end_time: float | None,
    non_voting_ids: set[str],
    expected_languages: tuple[str, ...],
    raw_by_id: dict[str, Observation],
) -> tuple[Cue, MultilingualDiagnostics]:
    voting_raw: list[Observation] = []
    for aggregated_observation in run:
        if not aggregated_observation.text or aggregated_observation.id in non_voting_ids:
            continue  # blank / unconfirmed-trailing candidate -- never a voter, see M5
        for member_id in member_observation_ids(aggregated_observation):
            member = raw_by_id.get(member_id)
            # A blank marker can still be one of several raw members
            # aggregated into a non-blank combined reading (e.g. one
            # language's engine found real text on a frame where
            # another language's engine found nothing) -- its own text
            # is never real region content, so it must never become a
            # language-bucket candidate itself, only the missing-layer
            # signal that an empty bucket already provides.
            if member is not None and member.text:
                voting_raw.append(member)

    buckets, ambiguous_languages = assign_observations_to_languages(voting_raw, expected_languages)

    layers: list[LanguageLayer] = []
    languages_present: list[str] = []
    missing_languages: list[str] = []
    for language in expected_languages:
        clusters = buckets[language]
        if not clusters:
            layers.append(LanguageLayer(language=language, text="", observation_ids=()))
            missing_languages.append(language)
            continue
        # Each visual-line cluster is its own physical line, not a
        # competing OCR sample of every other cluster in this bucket --
        # a genuine two-line same-language caption must not have its
        # two lines thrown into one flat vote (that would pick ONE
        # line's text and silently drop the other). Each cluster gets
        # its own consensus vote (multiple engines/frames reading the
        # SAME real line), and the resulting per-line texts are joined
        # top-to-bottom (clusters already geometry-sorted, see
        # `assign_observations_to_languages`) with a real newline.
        line_texts: list[str] = []
        observation_ids: list[str] = []
        for cluster in clusters:
            texts = [observation.text for observation in cluster]
            winning_text, _distinct_count, _top_count = consensus_value(texts, cluster)
            line_texts.append(winning_text)
            observation_ids.extend(observation.id for observation in cluster)
        layers.append(
            LanguageLayer(
                language=language,
                text="\n".join(line_texts),
                observation_ids=tuple(observation_ids),
            )
        )
        languages_present.append(language)

    start_time, end_time = resolve_cue_timing(run, boundary_time, processing_end_time)
    cue = Cue(
        id=f"cue-{run[0].id}",
        start_time=start_time,
        end_time=end_time,
        language_layers=tuple(layers),
    )
    diagnostics = MultilingualDiagnostics(
        cue_id=cue.id,
        languages_expected=expected_languages,
        languages_present=tuple(languages_present),
        missing_languages=tuple(missing_languages),
        ambiguous_languages=tuple(
            language for language in expected_languages if language in ambiguous_languages
        ),
    )
    return cue, diagnostics
