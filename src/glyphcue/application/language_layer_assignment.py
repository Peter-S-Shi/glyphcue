from __future__ import annotations

from collections import Counter

from glyphcue.domain.observation import Observation

_SCRIPT_CANDIDATE_LANGUAGES: dict[str, set[str]] = {
    "kana": {"ja"},
    "han": {"zh", "ja"},
    "latin": {"en"},
}
"""Cheap Unicode-range script classification -> the expected-language
codes that script could plausibly belong to. Not a language-ID model:
Han characters appear in both Chinese and Japanese text, so "han" maps
to both and is only resolved by a hint majority within the visual-line
cluster (see `_classify_cluster`); Hiragana/Katakana ("kana") is
unambiguously Japanese, so it disambiguates zh vs ja on its own."""


def _dominant_script(text: str) -> str | None:
    """The first recognized script found in `text`'s characters, in
    priority order (kana beats han: pure-kanji Japanese exists, but a
    single kana character firmly rules out Chinese). None if nothing in
    `text` matches a known range -- not a supported signal for that
    region, callers fall through to another signal."""
    has_han = False
    for character in text:
        code = ord(character)
        if 0x3040 <= code <= 0x30FF:  # Hiragana + Katakana
            return "kana"
        if 0x4E00 <= code <= 0x9FFF:  # CJK Unified Ideographs
            has_han = True
    if has_han:
        return "han"
    for character in text:
        if character.isascii() and character.isalpha():
            return "latin"
    return None


def _reading_order_key(observation: Observation) -> tuple[float, float]:
    if observation.geometry:
        xs = [point[0] for point in observation.geometry]
        ys = [point[1] for point in observation.geometry]
        return (min(ys), min(xs))
    return (0.0, 0.0)


def _y_range(observation: Observation) -> tuple[float, float] | None:
    if not observation.geometry:
        return None
    ys = [point[1] for point in observation.geometry]
    return (min(ys), max(ys))


def _cluster_by_visual_line(observations: list[Observation]) -> list[list[Observation]]:
    """Groups `observations` into one cluster per real physical text
    line, using vertical geometry overlap -- the same "same visual
    thing, multiple boxes" signal `aggregate_same_frame_observations`
    already uses, but here it exists to group MULTIPLE ENGINES'
    independent readings of the identical real line (real multi-engine
    verification showed every configured-language engine detects and
    transcribes every line in a shared visual block, not just the one
    it was configured for -- see the module docstring), not to join
    genuinely different lines. Observations with no geometry can't be
    matched this way and always become their own singleton cluster --
    there is no evidence they're duplicates of anything."""
    ordered = sorted(observations, key=_reading_order_key)
    clusters: list[list[Observation]] = []
    cluster_ranges: list[tuple[float, float] | None] = []
    for observation in ordered:
        current_range = _y_range(observation)
        if clusters and current_range is not None and cluster_ranges[-1] is not None:
            previous_range = cluster_ranges[-1]
            overlap = min(previous_range[1], current_range[1]) - max(
                previous_range[0], current_range[0]
            )
            if overlap > 0:
                clusters[-1].append(observation)
                cluster_ranges[-1] = (
                    min(previous_range[0], current_range[0]),
                    max(previous_range[1], current_range[1]),
                )
                continue
        clusters.append([observation])
        cluster_ranges.append(current_range)
    return clusters


def _classify_cluster(cluster: list[Observation], expected_languages: tuple[str, ...]) -> str | None:
    """The single expected language one visual-line cluster (all of it
    real or claimed readings of the SAME physical line) belongs to, or
    None if neither the cluster's own text nor its engine hints give
    any usable signal at all (left for the geometry/leftover fallback).

    Script is checked first, member by member: the first member whose
    script decisively maps to exactly one `expected_languages` code
    wins for the whole cluster (repeated OCR samples of one real line
    should agree on script even when they disagree on exact text).
    Only when NO member's script is individually decisive (e.g. every
    member reads as Han, ambiguous between zh/ja) does the cluster fall
    back to a majority vote over the members' own engine-tag hints
    among the surviving script candidates -- both signals share the
    unclaimed-bucket state that `assign_observations_to_languages`
    would otherwise need, but scoped to what's plausible for THIS
    cluster's own text, never letting a duplicate reading in another
    cluster interfere.
    """
    ambiguous_candidates: set[str] = set()
    for observation in cluster:
        script = _dominant_script(observation.text)
        if script is None:
            continue
        candidates = _SCRIPT_CANDIDATE_LANGUAGES.get(script, set()) & set(expected_languages)
        if len(candidates) == 1:
            return next(iter(candidates))
        if candidates:
            ambiguous_candidates |= candidates

    if ambiguous_candidates:
        hint_votes = Counter(
            observation.language
            for observation in cluster
            if observation.language in ambiguous_candidates
        )
        if hint_votes:
            return hint_votes.most_common(1)[0][0]

    hint_votes = Counter(
        observation.language for observation in cluster if observation.language in expected_languages
    )
    if hint_votes:
        return hint_votes.most_common(1)[0][0]

    return None


def assign_observations_to_languages(
    observations: list[Observation], expected_languages: tuple[str, ...]
) -> dict[str, list[Observation]]:
    """Splits a group of same-run OCR region Observations (normally all
    the raw regions belonging to one M5 state run) into one bucket per
    Track Group-expected language.

    Milestone 6's layer-separation seam: given real per-region evidence
    (never M5's already-joined single string -- see
    `multilingual_reconstruction.py`), decide which expected language
    each region belongs to. The algorithm, in order:

    1. **Cluster by visual line** (`_cluster_by_visual_line`): group
       same-frame regions whose vertical geometry overlaps -- this is
       what makes repeated readings of the SAME physical line from
       multiple engines (or multiple OCR calls) collapse into one
       decision instead of being classified independently and possibly
       disagreeing with each other.
    2. **Classify each cluster** (`_classify_cluster`): script detection
       over the cluster's own text is the primary signal -- a real
       multi-engine benchmark (`benchmarks/multilingual_reconstruction/`)
       found that `Observation.language` reflects which configured
       engine INSTANCE produced a reading, not evidence about what
       language that specific region actually contains (PaddleOCR's
       detector is not language-scoped: an "en"-configured engine still
       detects and transcribes a Chinese region and tags it "en"
       regardless). The engine hint is used only to break a genuine
       script-level tie (Han alone can't distinguish Chinese from
       Japanese).
    3. **Reading-order / vertical layout** for whatever's left: any
       cluster that still can't be classified, and any expected
       language with no cluster at all, are paired off by geometry
       reading order (top-to-bottom, falling back to original order
       with no geometry) against `expected_languages`' own configured
       order -- the same "visual layout" signal used elsewhere,
       generalized here to ordering *across* languages instead of
       being hard-coded to a two-language case.

    A cluster that classifies to a language some OTHER cluster already
    claimed (e.g. a genuine two-line same-language caption) simply adds
    its members to that language's existing bucket -- majority voting
    at the caller resolves the final text, same as any other repeated
    reading. A cluster that can't be classified into any remaining slot
    at all is folded into whichever already-assigned bucket is
    geometrically nearest to it.

    Returns one bucket (list, possibly empty -- an empty bucket for an
    expected language is the "missing layer" signal callers use to
    build a degraded/diagnostic LanguageLayer, see
    `multilingual_reconstruction.py`) per language in
    `expected_languages`, in that exact order -- callers build
    `LanguageLayer`s by iterating this dict in insertion order, which is
    always `expected_languages`' own configured order, giving every
    reconstructed Cue the same layer ordering regardless of what order
    OCR happened to return regions in for any given frame.
    """
    buckets: dict[str, list[Observation]] = {language: [] for language in expected_languages}

    clusters = _cluster_by_visual_line(observations)
    unresolved_clusters: list[list[Observation]] = []
    for cluster in clusters:
        language = _classify_cluster(cluster, expected_languages)
        if language is not None:
            buckets[language].extend(cluster)
        else:
            unresolved_clusters.append(cluster)

    empty_languages = [language for language in expected_languages if not buckets[language]]
    unresolved_clusters.sort(key=lambda cluster: _reading_order_key(cluster[0]))
    for language, cluster in zip(empty_languages, unresolved_clusters):
        buckets[language].extend(cluster)
    leftover_clusters = unresolved_clusters[len(empty_languages) :]

    assigned_in_order = [
        observation for language in expected_languages for observation in buckets[language]
    ]
    for cluster in leftover_clusters:
        if not assigned_in_order:
            break
        anchor = cluster[0]
        nearest = min(
            assigned_in_order,
            key=lambda candidate: abs(
                _reading_order_key(candidate)[0] - _reading_order_key(anchor)[0]
            ),
        )
        for language in expected_languages:
            if nearest in buckets[language]:
                buckets[language].extend(cluster)
                break

    return buckets
