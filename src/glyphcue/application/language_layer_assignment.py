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
to both and is only resolved by elimination (a language already
decisively claimed by another cluster) or, failing that, a STRICT
unique-winner hint vote (see `_classify_clusters`); Hiragana/Katakana
("kana") is unambiguously Japanese, so it disambiguates zh vs ja on its
own."""


def _dominant_script(text: str) -> str | None:
    """The recognized script `text`'s characters decisively belong to,
    in priority order (kana beats han: pure-kanji Japanese exists, but a
    single kana character firmly rules out Chinese -- real Japanese
    text routinely mixes kana with han, and occasionally with latin
    loanwords, so kana presence alone stays decisive regardless of what
    else is in the string). None if nothing in `text` matches a known
    range, OR if `text` mixes han and latin with no kana present: real
    single-language OCR output doesn't interleave CJK ideographs with
    Latin letters that way, so that specific combination is a signal of
    OCR corruption (garbled mixed-script misread), not evidence for
    either script -- callers must treat it as no decisive signal, never
    silently pick the more "exotic" script found."""
    has_kana = False
    has_han = False
    has_latin = False
    for character in text:
        code = ord(character)
        if 0x3040 <= code <= 0x30FF:  # Hiragana + Katakana
            has_kana = True
        elif 0x4E00 <= code <= 0x9FFF:  # CJK Unified Ideographs
            has_han = True
        elif character.isascii() and character.isalpha():
            has_latin = True
    if has_kana:
        return "kana"
    if has_han and has_latin:
        return None
    if has_han:
        return "han"
    if has_latin:
        return "latin"
    return None


def _reading_order_key(observation: Observation) -> tuple[float, float]:
    if observation.geometry:
        xs = [point[0] for point in observation.geometry]
        ys = [point[1] for point in observation.geometry]
        return (min(ys), min(xs))
    return (0.0, 0.0)


def _cluster_anchor_key(cluster: list[Observation]) -> tuple[float, float]:
    return _reading_order_key(cluster[0])


def _y_range(observation: Observation) -> tuple[float, float] | None:
    if not observation.geometry:
        return None
    ys = [point[1] for point in observation.geometry]
    return (min(ys), max(ys))


def _decisive_language(text: str, expected_languages: tuple[str, ...]) -> str | None:
    """`text`'s own script, resolved to a single expected language --
    None if its script carries no signal at all, or is genuinely
    ambiguous between more than one expected language (e.g. Han between
    zh/ja). Used only as a veto signal for `_cluster_by_visual_line`:
    ambiguous/no-signal text is never treated as evidence AGAINST a
    merge, only a text whose own script decisively picks one language
    can veto merging with a decisively DIFFERENT one."""
    script = _dominant_script(text)
    if script is None:
        return None
    matches = _SCRIPT_CANDIDATE_LANGUAGES.get(script, set()) & set(expected_languages)
    return next(iter(matches)) if len(matches) == 1 else None


def _cluster_by_visual_line(
    observations: list[Observation], expected_languages: tuple[str, ...]
) -> list[list[Observation]]:
    """Groups `observations` into one cluster per real physical text
    line, using vertical geometry overlap -- the same "same visual
    thing, multiple boxes" signal `aggregate_same_frame_observations`
    already uses, but here it exists to group MULTIPLE ENGINES' (or
    multiple frames') independent readings of the identical real line
    (real multi-engine verification showed every configured-language
    engine detects and transcribes every line in a shared visual block,
    not just the one it was configured for -- see
    `assign_observations_to_languages`), not to join genuinely
    different lines. Observations with no geometry can't be matched
    this way and always become their own singleton cluster -- there is
    no evidence they're duplicates of anything.

    Real detector geometry (DirectML's own box_thresh included) is not
    pixel-perfect: two visually and linguistically DIFFERENT physical
    lines stacked close together can report Y-ranges that overlap by a
    few pixels of detection/rounding noise, which pure Y-overlap alone
    would merge into one cluster -- silently mixing one language's real
    text into another's vote (see docs/multilingual/track_group_reconstruction.md's
    Milestone 11 Architecture B corrective addendum). A DECISIVE script
    veto closes this without adding any new numeric overlap threshold:
    an incoming observation whose own script decisively picks one
    expected language never merges into a cluster whose already-accumulated
    decisive language is a DIFFERENT one, even when their Y-ranges
    technically overlap -- it starts a new cluster instead. Real
    same-line horizontal fragments (word-level boxes of one sentence)
    share one script and are unaffected; ambiguous-or-no-signal text
    (candidate count != 1, e.g. pure Han between zh/ja, or non-text
    noise) never vetoes anything, since it isn't decisive evidence of
    incompatibility either way -- it merges by geometry exactly as
    before, and downstream classification handles the ambiguity."""
    ordered = sorted(observations, key=_reading_order_key)
    clusters: list[list[Observation]] = []
    cluster_ranges: list[tuple[float, float] | None] = []
    cluster_decisive_languages: list[str | None] = []
    for observation in ordered:
        current_range = _y_range(observation)
        current_decisive = _decisive_language(observation.text, expected_languages)
        if clusters and current_range is not None and cluster_ranges[-1] is not None:
            previous_range = cluster_ranges[-1]
            overlap = min(previous_range[1], current_range[1]) - max(
                previous_range[0], current_range[0]
            )
            previous_decisive = cluster_decisive_languages[-1]
            script_incompatible = (
                previous_decisive is not None
                and current_decisive is not None
                and previous_decisive != current_decisive
            )
            if overlap > 0 and not script_incompatible:
                clusters[-1].append(observation)
                cluster_ranges[-1] = (
                    min(previous_range[0], current_range[0]),
                    max(previous_range[1], current_range[1]),
                )
                cluster_decisive_languages[-1] = previous_decisive or current_decisive
                continue
        clusters.append([observation])
        cluster_ranges.append(current_range)
        cluster_decisive_languages.append(current_decisive)
    return clusters


def _cluster_script_candidates(
    cluster: list[Observation], expected_languages: tuple[str, ...]
) -> set[str]:
    """Script-only candidate set for one visual-line cluster. If any
    member's own script is independently decisive (maps to exactly one
    expected language), that member's evidence dominates the whole
    cluster -- repeated OCR samples of one real line should agree on
    script even when they disagree on exact text -- and its single
    candidate is returned immediately. Otherwise, the union of every
    ambiguous-but-plausible script match across members (e.g. Han ->
    {zh, ja}) is returned, or an empty set if nothing in the cluster
    carries a recognized script at all."""
    ambiguous: set[str] = set()
    for observation in cluster:
        script = _dominant_script(observation.text)
        if script is None:
            continue
        matches = _SCRIPT_CANDIDATE_LANGUAGES.get(script, set()) & set(expected_languages)
        if len(matches) == 1:
            return matches
        ambiguous |= matches
    return ambiguous


def _strict_hint_winner(cluster: list[Observation], candidates: set[str]) -> str | None:
    """The unique language among `candidates` whose engine-tag hint is
    STRICTLY the most common in `cluster` -- None if there's no hint
    evidence among `candidates` at all, or if the top vote count is
    tied between two or more candidates. A tie must never be silently
    broken by `Counter`/insertion order: it stays unresolved for the
    geometry fallback in `assign_observations_to_languages` instead of
    guessing."""
    votes = Counter(
        observation.language for observation in cluster if observation.language in candidates
    )
    if not votes:
        return None
    top_count = max(votes.values())
    winners = [language for language, count in votes.items() if count == top_count]
    return winners[0] if len(winners) == 1 else None


def _classify_clusters(
    clusters: list[list[Observation]], expected_languages: tuple[str, ...]
) -> tuple[dict[str, list[list[Observation]]], list[tuple[list[Observation], set[str]]]]:
    """Resolves each visual-line cluster to one expected language, as a
    single fixed-point process across ALL clusters together -- not
    independently per cluster. This is what lets a cluster whose own
    script is ambiguous (Han: zh or ja) resolve decisively once ANOTHER
    cluster's own decisive script assignment has already claimed one of
    the ambiguous candidates (e.g. a Kana cluster claiming "ja" leaves a
    plain-Han cluster with only "zh" possible) -- elimination using real
    evidence from elsewhere in the same run, not a guess. Looping to a
    fixed point (repeating until a full pass makes no further progress)
    makes the result independent of the order clusters happen to be in.

    A cluster's engine-tag hint only breaks a REMAINING tie via
    `_strict_hint_winner` -- when elimination alone doesn't narrow
    things to exactly one candidate, and the hint has a strict unique
    winner among what elimination left. A cluster that still can't be
    resolved after all of that is returned unresolved (paired with its
    last-computed script candidates), for `assign_observations_to_languages`
    to decide between two DIFFERENT fallbacks -- never silently guessed
    here.

    A cluster whose script candidates are the EMPTY set (no recognized
    script at all -- e.g. bare digits/punctuation) is never narrowed by
    elimination: substituting "every expected language" for "no evidence"
    would let elimination alone (every OTHER language slot filling up)
    silently hand it a language it has zero actual textual evidence for.
    It always stays unresolved here; `assign_observations_to_languages`'s
    geometry fallback is the only path that may place it, and always
    marks the result ambiguous.
    """
    resolved: dict[str, list[list[Observation]]] = {language: [] for language in expected_languages}
    remaining: list[list[Observation]] = list(clusters)
    last_candidates: dict[int, set[str]] = {}
    made_progress = True
    while made_progress and remaining:
        made_progress = False
        claimed = {language for language, members in resolved.items() if members}
        still_remaining: list[list[Observation]] = []
        newly_resolved: list[tuple[str, list[Observation]]] = []
        for cluster in remaining:
            candidates = _cluster_script_candidates(cluster, expected_languages)
            last_candidates[id(cluster)] = candidates
            language: str | None = None
            if len(candidates) == 1:
                language = next(iter(candidates))
            elif candidates:
                narrowed = candidates - claimed
                if len(narrowed) == 1:
                    language = next(iter(narrowed))
                elif len(narrowed) > 1:
                    language = _strict_hint_winner(cluster, narrowed)
            if language is not None:
                newly_resolved.append((language, cluster))
                made_progress = True
            else:
                still_remaining.append(cluster)
        for language, cluster in newly_resolved:
            resolved[language].append(cluster)
        remaining = still_remaining
    return resolved, [(cluster, last_candidates[id(cluster)]) for cluster in remaining]


def assign_observations_to_languages(
    observations: list[Observation], expected_languages: tuple[str, ...]
) -> tuple[dict[str, list[list[Observation]]], set[str]]:
    """Splits a group of same-run OCR region Observations (normally all
    the raw regions belonging to one M5 state run, across every frame
    and every language's engine in that run) into one or more
    visual-line CLUSTERS per Track Group-expected language.

    Milestone 6's layer-separation seam: given real per-region evidence
    (never M5's already-joined single string -- see
    `multilingual_reconstruction.py`), decide which expected language
    each physical text line belongs to. The algorithm, in order:

    1. **Cluster by visual line** (`_cluster_by_visual_line`): group
       same-frame regions whose vertical geometry overlaps -- this is
       what makes repeated readings of the SAME physical line from
       multiple engines/frames collapse into one classification
       decision, AND what keeps two genuinely different physical lines
       of the same language (e.g. a real two-line English caption) from
       being flattened into one undifferentiated pool of "samples" that
       compete with each other in a single vote -- each stays its own
       cluster, to be consensus-voted and then line-joined separately
       by the caller (`multilingual_reconstruction.py`).
    2. **Classify each cluster** (`_classify_clusters`): script
       detection over the cluster's own text is the primary signal --
       real multi-engine verification found `Observation.language`
       reflects which configured engine INSTANCE produced a reading,
       not evidence about what language that specific region actually
       contains. Ambiguous script (Han: zh or ja) is resolved first by
       ELIMINATION against languages other clusters have already
       decisively claimed, and only then by a hint vote that requires a
       STRICT unique winner -- a tie is never silently broken.
    3. **Reading-order / vertical layout** for whatever's left: any
       cluster that still can't be classified, and any expected
       language with no cluster at all, are paired off by geometry
       reading order (top-to-bottom, falling back to original order
       with no geometry) against `expected_languages`' own configured
       order.

    A cluster that classifies to a language some OTHER cluster already
    claimed (e.g. a genuine two-line same-language caption) simply joins
    that language's existing cluster list -- each cluster is still
    consensus-voted independently by the caller. A cluster that can't
    be classified into any remaining slot at all is folded into
    whichever already-assigned cluster is geometrically nearest to it.

    Returns `(buckets, ambiguous_languages)`:
    - `buckets`: one list of visual-line clusters (each itself a list
      of Observations, geometry-sorted top-to-bottom within a language)
      per language in `expected_languages`, in that exact order -- an
      empty list is the "missing layer" signal callers use to build a
      degraded/diagnostic `LanguageLayer` (see
      `multilingual_reconstruction.py`). Layer order stays stable
      because callers iterate this dict in its own (always
      `expected_languages`') order, never re-derived from OCR detection
      order.
    - `ambiguous_languages`: the set of languages that received at
      least one cluster only through step 3's geometry fallback rather
      than a decisive script/elimination/strict-hint classification --
      real ambiguity/degraded evidence for callers to surface as a
      diagnostic, not silently hidden inside a confident-looking result.
    """
    clusters = _cluster_by_visual_line(observations, expected_languages)
    resolved, unresolved = _classify_clusters(clusters, expected_languages)

    ambiguous_languages: set[str] = set()

    # A cluster left unresolved WITH real (but undecidable) script
    # candidates -- e.g. pure Han with no elimination/hint evidence to
    # pick zh vs ja -- is genuine ambiguity between those specific
    # languages, not a missing-layer gap a geometry guess may fill: every
    # candidate language is marked ambiguous and the cluster is placed
    # nowhere (fail-closed: no fabricated winner beats a wrong one). Only
    # a cluster with NO script evidence at all (empty candidates) is
    # eligible for the geometry fallback below.
    geometry_eligible: list[list[Observation]] = []
    for cluster, candidates in unresolved:
        if candidates:
            ambiguous_languages |= candidates
        else:
            geometry_eligible.append(cluster)
    unresolved_clusters = geometry_eligible

    empty_languages = [language for language in expected_languages if not resolved[language]]
    unresolved_clusters.sort(key=_cluster_anchor_key)
    for language, cluster in zip(empty_languages, unresolved_clusters):
        resolved[language].append(cluster)
        ambiguous_languages.add(language)
    leftover_clusters = unresolved_clusters[len(empty_languages) :]

    assigned_clusters_in_order = [
        cluster for language in expected_languages for cluster in resolved[language]
    ]
    for cluster in leftover_clusters:
        if not assigned_clusters_in_order:
            break
        anchor_y = _cluster_anchor_key(cluster)[0]
        nearest = min(
            assigned_clusters_in_order,
            key=lambda candidate: abs(_cluster_anchor_key(candidate)[0] - anchor_y),
        )
        for language in expected_languages:
            if nearest in resolved[language]:
                resolved[language].append(cluster)
                ambiguous_languages.add(language)
                break

    for language in expected_languages:
        resolved[language].sort(key=_cluster_anchor_key)

    return resolved, ambiguous_languages
