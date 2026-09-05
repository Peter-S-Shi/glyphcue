"""GlyphCue Cue Cleaner V0.6.1 -- frozen, vendored transformation algorithm.

This module is a verbatim copy of the externally-developed and -validated
V0.6.1 Cleaner algorithm (see `docs/adr/` / PROJECT_STATUS.md for the M12
Cue Cleaner integration record). It is frozen: per its own freeze report,
further behavior changes require a new cleaner version re-validated
against the full Sample A-H corpus, not an edit here.

Only the pure transformation algorithm is vendored (the `Cue` dataclass
and `clean_cues` plus its internal helpers). The original lab script's
VTT file I/O and CLI entrypoint are lab-only conveniences, not part of
GlyphCue's product integration, and are intentionally not carried over --
`glyphcue.application.cue_cleaning` adapts GlyphCue's own domain `Cue`
model to/from the `Cue` dataclass below; nothing here has been rewritten.
"""

from __future__ import annotations

import statistics
import unicodedata
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from functools import lru_cache
import difflib


@dataclass(frozen=True)
class Cue:
    index: int
    start: float
    end: float
    text: str
    source_indices: tuple[int, ...] = ()
    selected_origin_index: int | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start


@lru_cache(maxsize=None)
def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = text.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", text)


@lru_cache(maxsize=None)
def compact_text(text: str) -> str:
    text = normalize_text(text)
    return "".join(
        char for char in text
        if char.isalnum() or "一" <= char <= "鿿"
    )


@lru_cache(maxsize=None)
def sequence_similarity(left: str, right: str) -> float:
    left_c = compact_text(left)
    right_c = compact_text(right)
    if not left_c and not right_c:
        return 1.0
    if not left_c or not right_c:
        return 0.0
    return difflib.SequenceMatcher(None, left_c, right_c, autojunk=False).ratio()


@lru_cache(maxsize=None)
def bigram_dice(left: str, right: str) -> float:
    left_c = compact_text(left)
    right_c = compact_text(right)
    if len(left_c) < 2 or len(right_c) < 2:
        return sequence_similarity(left, right)

    left_bigrams = Counter(left_c[i:i + 2] for i in range(len(left_c) - 1))
    right_bigrams = Counter(right_c[i:i + 2] for i in range(len(right_c) - 1))
    overlap = sum((left_bigrams & right_bigrams).values())
    return 2.0 * overlap / (sum(left_bigrams.values()) + sum(right_bigrams.values()))


@lru_cache(maxsize=None)
def character_multiset_similarity(left: str, right: str) -> float:
    left_c = compact_text(left)
    right_c = compact_text(right)
    if not left_c and not right_c:
        return 1.0
    if not left_c or not right_c:
        return 0.0
    left_counter = Counter(left_c)
    right_counter = Counter(right_c)
    overlap = sum((left_counter & right_counter).values())
    return 2.0 * overlap / (len(left_c) + len(right_c))


def robust_text_similarity(left: str, right: str) -> float:
    return max(
        sequence_similarity(left, right),
        bigram_dice(left, right) * 0.99,
    )


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _script_profile(text: str) -> tuple[bool, bool]:
    compact = compact_text(text)
    has_cjk = any("一" <= char <= "鿿" for char in compact)
    has_latin = any("a" <= char <= "z" for char in compact)
    return has_cjk, has_latin


def dedupe_exact_lines(text: str) -> tuple[str, list[str]]:
    kept: list[str] = []
    removed: list[str] = []
    seen: set[str] = set()
    for line in _lines(text):
        key = normalize_text(line)
        if key in seen:
            removed.append(line)
            continue
        seen.add(key)
        kept.append(line)
    return "\n".join(kept), removed


def _directional_line_score(source_lines: list[str], target_lines: list[str]) -> float:
    weighted: list[tuple[float, int]] = []
    for source in source_lines:
        best = max(robust_text_similarity(source, target) for target in target_lines)
        weight = max(1, min(len(compact_text(source)), 40))
        weighted.append((best, weight))
    return sum(score * weight for score, weight in weighted) / sum(weight for _, weight in weighted)


def line_matching_similarity(left: str, right: str) -> float:
    left_lines = _lines(left)
    right_lines = _lines(right)
    if not left_lines or not right_lines:
        return robust_text_similarity(left, right)
    return (
        _directional_line_score(left_lines, right_lines)
        + _directional_line_score(right_lines, left_lines)
    ) / 2.0


def containment_ratio(left: str, right: str) -> float:
    left_c = compact_text(left)
    right_c = compact_text(right)
    if not left_c or not right_c:
        return 0.0
    if left_c in right_c or right_c in left_c:
        return min(len(left_c), len(right_c)) / max(len(left_c), len(right_c))
    return 0.0


def state_similarity(left: str, right: str) -> float:
    whole = robust_text_similarity(left, right)
    line_score = line_matching_similarity(left, right)
    containment = containment_ratio(left, right)
    return max(
        whole,
        0.55 * whole + 0.45 * line_score,
        containment * 0.98,
    )


def _line_support_fraction(line: str, cluster: list[Cue], threshold: float = 0.88) -> float:
    hits = 0
    for cue in cluster:
        if any(robust_text_similarity(line, other) >= threshold for other in _lines(cue.text)):
            hits += 1
    return hits / max(1, len(cluster))


def _line_family_match(left: str, right: str) -> bool:
    left_c = compact_text(left)
    right_c = compact_text(right)
    if not left_c or not right_c:
        return False
    if robust_text_similarity(left, right) >= 0.88:
        return True
    if left_c in right_c or right_c in left_c:
        shorter = left if len(left_c) <= len(right_c) else right
        shorter_c = left_c if len(left_c) <= len(right_c) else right_c
        ratio = min(len(left_c), len(right_c)) / max(len(left_c), len(right_c))
        has_cjk, has_latin = _script_profile(shorter)

        # A substantial recurring phrase is still the same evidence family when
        # one observed Cue contains that whole phrase plus an adjacent fragment.
        # This was the missed V0.5 case in sample C: one source Cue contained
        # both recurring Chinese fragments in a single longer line.
        if has_cjk and len(shorter_c) >= 4:
            return True
        if has_latin and len(shorter_c) >= 6:
            return True
        return ratio >= 0.45
    return False


def _line_families(cluster: list[Cue]) -> list[dict[str, object]]:
    """Build evidence-backed line families inside one candidate state.

    A family represents one recurring subtitle/overlay line variant. Support is
    counted by Cue, never raw duplicate line count, so one noisy Cue cannot
    inflate itself. This is used only for representative selection and risk
    diagnosis; it does not synthesize text.
    """
    families: list[dict[str, object]] = []

    for cue in cluster:
        seen_family_indices: set[int] = set()
        for line in _lines(cue.text):
            match_index = None
            best_score = -1.0
            for index, family in enumerate(families):
                representative = str(family["representative"])
                if not _line_family_match(line, representative):
                    continue
                score = robust_text_similarity(line, representative)
                if score > best_score:
                    best_score = score
                    match_index = index

            if match_index is None:
                families.append(
                    {
                        "representative": line,
                        "variants": [line],
                        "cue_ids": {cue.index},
                        "max_length": len(compact_text(line)),
                    }
                )
                seen_family_indices.add(len(families) - 1)
                continue

            family = families[match_index]
            family["variants"].append(line)
            family["max_length"] = max(
                int(family["max_length"]), len(compact_text(line))
            )
            if cue.index not in family["cue_ids"]:
                family["cue_ids"].add(cue.index)
            seen_family_indices.add(match_index)

            # Prefer the longest observed variant as the family descriptor.
            if len(compact_text(line)) > len(compact_text(str(family["representative"]))):
                family["representative"] = line

    for family in families:
        family["support_count"] = len(family["cue_ids"])
        family["support_fraction"] = len(family["cue_ids"]) / max(1, len(cluster))
        family["cue_ids"] = sorted(family["cue_ids"])
    return families


def _candidate_covers_family(candidate: Cue, family: dict[str, object]) -> bool:
    for line in _lines(candidate.text):
        if _line_family_match(line, str(family["representative"])):
            return True
    return False


def _canonical_supported_families(cluster: list[Cue]) -> list[dict[str, object]]:
    """Recurring evidence families after removing strict fragment families.

    A short recurring fragment such as `now` is not a separate information
    obligation when another recurring family in the same cluster contains it
    as a proper substring (`now you have a potential issue here`). This keeps
    true complementary evidence such as `... life of` + `abundance.` distinct,
    while preventing fragment-only families from creating false
    information-loss alarms.
    """
    families = _line_families(cluster)
    supported = [
        family
        for family in families
        if int(family["support_count"]) >= 2
        and float(family["support_fraction"]) >= 0.20
    ]

    canonical: list[dict[str, object]] = []
    for family in supported:
        text = str(family["representative"])
        text_c = compact_text(text)
        profile = _script_profile(text)
        dominated = False

        for other in supported:
            if other is family:
                continue
            other_text = str(other["representative"])
            other_c = compact_text(other_text)
            if not text_c or not other_c or len(text_c) >= len(other_c):
                continue
            if profile != _script_profile(other_text):
                continue
            if text_c in other_c and int(other["support_count"]) >= 2:
                dominated = True
                break

        if not dominated:
            canonical.append(family)

    return canonical


def representative_diagnostics(cluster: list[Cue], representative: Cue) -> dict[str, object]:
    supported = _canonical_supported_families(cluster)
    uncovered = [
        family for family in supported
        if not _candidate_covers_family(representative, family)
    ]
    return {
        "supported_family_count": len(supported),
        "uncovered_supported_family_count": len(uncovered),
        "uncovered_supported_families": [
            {
                "representative": family["representative"],
                "support_count": family["support_count"],
                "support_fraction": round(float(family["support_fraction"]), 3),
            }
            for family in uncovered
        ],
        "information_loss_risk": bool(uncovered),
    }


def _candidate_supported_coverage(
    cue: Cue,
    supported: list[dict[str, object]],
) -> tuple[float, float]:
    weighted = 0.0
    chars = 0.0
    for family in supported:
        if not _candidate_covers_family(cue, family):
            continue
        length = min(int(family["max_length"]), 60)
        fraction = float(family["support_fraction"])
        weighted += max(0.20, fraction) * length
        chars += length
    return weighted, chars


def _candidate_unsupported_chars(
    cue: Cue,
    supported: list[dict[str, object]],
) -> int:
    """Penalize only a line that covers no recurring supported family.

    This fixes the concrete V0.5.1 error where a longer observed Chinese line
    covered two recurring fragment families but was still penalized as a
    one-off line merely because the exact long form appeared once.
    """
    unsupported = 0
    for line in _lines(cue.text):
        line_is_supported = any(
            _line_family_match(line, str(family["representative"]))
            for family in supported
        )
        if not line_is_supported and _line_support_fraction(line, [cue]) < 1.01:
            unsupported += min(len(compact_text(line)), 40)
    return unsupported


def choose_representative(cluster: list[Cue]) -> Cue:
    """Choose the most evidence-complete observed Cue; never synthesize text."""
    supported = _canonical_supported_families(cluster)

    def quality(cue: Cue) -> tuple[float, float, float, float, int]:
        weighted, supported_chars = _candidate_supported_coverage(cue, supported)
        unsupported_chars = _candidate_unsupported_chars(cue, supported)
        centrality = statistics.mean(
            state_similarity(cue.text, other.text) for other in cluster
        )
        return (
            weighted,
            supported_chars,
            -unsupported_chars,
            centrality + min(cue.duration, 2.0) * 0.01,
            -cue.index,
        )

    return max(cluster, key=quality)


def choose_evidence_cover(cluster: list[Cue]) -> list[Cue]:
    """Greedy observed-Cue set cover for complementary recurring evidence.

    If no single observed Cue covers all recurring line families, V0.6 refuses
    to collapse the state into one lossy Cue. Instead it keeps the smallest
    practical set of observed Cues needed to cover that evidence. This is the
    conservative fallback that should map to `Needs Review` in GlyphCue.
    """
    supported = _canonical_supported_families(cluster)
    if not supported:
        return [choose_representative(cluster)]

    representative = choose_representative(cluster)
    selected = [representative]

    def covered_family_indices(cue: Cue) -> set[int]:
        return {
            index for index, family in enumerate(supported)
            if _candidate_covers_family(cue, family)
        }

    covered = covered_family_indices(representative)
    all_indices = set(range(len(supported)))

    while covered != all_indices and len(selected) < min(4, len(cluster)):
        uncovered = all_indices - covered
        candidates = [cue for cue in cluster if cue not in selected]
        if not candidates:
            break

        def score(cue: Cue) -> tuple[float, float, float, int]:
            cue_coverage = covered_family_indices(cue)
            new = cue_coverage & uncovered
            new_weight = sum(
                min(int(supported[index]["max_length"]), 60)
                * max(0.20, float(supported[index]["support_fraction"]))
                for index in new
            )
            centrality = statistics.mean(
                state_similarity(cue.text, other.text) for other in cluster
            )
            unsupported = _candidate_unsupported_chars(cue, supported)
            return (new_weight, -unsupported, centrality, -cue.index)

        best = max(candidates, key=score)
        new_coverage = covered_family_indices(best) - covered
        if not new_coverage:
            break
        selected.append(best)
        covered |= new_coverage

    return sorted(selected, key=lambda cue: (cue.start, cue.end, cue.index))


def prune_transient_lines(representative: Cue, cluster: list[Cue]) -> tuple[str, list[str]]:
    """Prune only lines unsupported by the cluster's canonical recurring evidence.

    V0.6.1 freeze repair: the same evidence-family semantics used to choose the
    representative must also govern pruning. Otherwise the cleaner can select
    an information-complete observed Cue and then immediately delete its
    longest supported line.
    """
    if len(cluster) < 4:
        return representative.text, []

    supported = _canonical_supported_families(cluster)
    if not supported:
        return representative.text, []

    kept: list[str] = []
    removed: list[str] = []

    for line in _lines(representative.text):
        covers_supported_family = any(
            _line_family_match(line, str(family["representative"]))
            for family in supported
        )
        if covers_supported_family:
            kept.append(line)
            continue

        # Only remove a line that is both outside every supported family and
        # very weakly repeated across the cluster. This keeps the operation
        # conservative and evidence-backed.
        if _line_support_fraction(line, cluster) < 0.30:
            removed.append(line)
        else:
            kept.append(line)

    if not kept:
        return representative.text, []
    return "\n".join(kept), removed


def _fuzzy_overlay_families(cues: list[Cue]) -> list[dict[str, object]]:
    data: dict[str, dict[str, object]] = {}
    for cue in cues:
        seen: set[str] = set()
        for line in _lines(cue.text):
            key = normalize_text(line)
            if not key or key in seen:
                continue
            seen.add(key)
            if key not in data:
                data[key] = {"display": line, "cues": []}
            data[key]["cues"].append(cue)

    keys = list(data)
    parent = list(range(len(keys)))

    def find(index: int) -> int:
        if parent[index] != index:
            parent[index] = find(parent[index])
        return parent[index]

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index, left_key in enumerate(keys):
        left = str(data[left_key]["display"])
        left_compact = compact_text(left)
        if len(left_compact) < 5:
            continue

        for right_index in range(left_index + 1, len(keys)):
            right_key = keys[right_index]
            right = str(data[right_key]["display"])
            right_compact = compact_text(right)

            if len(right_compact) < 5:
                continue
            if _script_profile(left) != _script_profile(right):
                continue

            length_ratio = min(len(left_compact), len(right_compact)) / max(
                len(left_compact), len(right_compact)
            )
            if length_ratio < 0.82:
                continue
            if robust_text_similarity(left, right) >= 0.82:
                union(left_index, right_index)

    groups: dict[int, list[str]] = defaultdict(list)
    for index, key in enumerate(keys):
        groups[find(index)].append(key)

    families: list[dict[str, object]] = []
    for members in groups.values():
        unique_cues: dict[int, Cue] = {}
        for member in members:
            for cue in data[member]["cues"]:
                unique_cues[cue.index] = cue

        occurrences = list(unique_cues.values())
        if not occurrences:
            continue

        span = max(cue.end for cue in occurrences) - min(cue.start for cue in occurrences)
        if len(occurrences) >= 4 and span >= 12.0:
            families.append(
                {
                    "members": members,
                    "occurrence_count": len(occurrences),
                    "temporal_span_seconds": round(span, 3),
                }
            )

    # Once a persistent family is established conservatively, allow a more
    # permissive whole-line expansion to catch short OCR variants of that same
    # overlay. Expansion NEVER strips a substring from a longer sentence.
    family_members = [member for family in families for member in family["members"]]
    for key in keys:
        if key in family_members:
            continue
        display = str(data[key]["display"])
        if len(compact_text(display)) < 4:
            continue
        for family in families:
            members = list(family["members"])
            if any(
                _script_profile(display) == _script_profile(member)
                and robust_text_similarity(display, member) >= 0.78
                for member in members
            ):
                family["members"].append(key)
                break

    return families


def remove_persistent_overlays(
    cues: list[Cue],
) -> tuple[list[Cue], list[dict[str, object]], list[dict[str, object]]]:
    families = _fuzzy_overlay_families(cues)
    overlay_keys = {
        member
        for family in families
        for member in family["members"]
    }

    output: list[Cue] = []
    actions: list[dict[str, object]] = []

    for cue in cues:
        kept: list[str] = []
        removed: list[str] = []
        for line in _lines(cue.text):
            if normalize_text(line) in overlay_keys:
                removed.append(line)
            else:
                kept.append(line)

        if removed:
            actions.append(
                {
                    "action": "remove_persistent_overlay_line",
                    "source_cues": list(cue.source_indices or (cue.index,)),
                    "removed_lines": removed,
                }
            )

        if kept:
            output.append(replace(cue, text="\n".join(kept)))

    return output, actions, families


def _shared_line_coverage(left: str, right: str, threshold: float = 0.90) -> float:
    left_lines = _lines(left)
    right_lines = _lines(right)
    if not left_lines or not right_lines:
        return 0.0

    def coverage(source: list[str], target: list[str]) -> float:
        total = 0
        matched = 0
        for line in source:
            weight = max(1, len(compact_text(line)))
            total += weight
            if max(robust_text_similarity(line, other) for other in target) >= threshold:
                matched += weight
        return matched / max(1, total)

    return max(coverage(left_lines, right_lines), coverage(right_lines, left_lines))


def _has_shared_anchor(left: Cue, right: Cue) -> bool:
    for left_line in _lines(left.text):
        if len(compact_text(left_line)) < 6:
            continue
        for right_line in _lines(right.text):
            if len(compact_text(right_line)) < 6:
                continue
            if robust_text_similarity(left_line, right_line) >= 0.97:
                return True
    return False


def _fragment_link(left: Cue, right: Cue, gap: float) -> bool:
    if gap > 0.15:
        return False

    if _shared_line_coverage(left.text, right.text) >= 0.72:
        return True

    containment = containment_ratio(left.text, right.text)
    if containment >= 0.45 and min(left.duration, right.duration) <= 0.8:
        return True

    return False


def _order_scramble_link(left: Cue, right: Cue, gap: float) -> bool:
    if gap > 0.35:
        return False

    left_compact = compact_text(left.text)
    right_compact = compact_text(right.text)
    if min(len(left_compact), len(right_compact)) < 20:
        return False

    length_ratio = min(len(left_compact), len(right_compact)) / max(
        len(left_compact), len(right_compact)
    )
    return (
        length_ratio >= 0.82
        and character_multiset_similarity(left.text, right.text) >= 0.94
    )


def _semantic_signature(cues: list[Cue]) -> list[tuple[float, float, str]]:
    return [(round(cue.start, 6), round(cue.end, 6), cue.text) for cue in cues]


def clean_one_pass(
    cues: list[Cue],
    *,
    similarity_threshold: float,
    max_gap_seconds: float,
    max_cluster_span_seconds: float,
) -> tuple[list[Cue], list[dict[str, object]], list[dict[str, object]]]:
    prepared, actions, overlay_families = remove_persistent_overlays(cues)

    deduped_prepared: list[Cue] = []
    for cue in prepared:
        deduped_text, removed = dedupe_exact_lines(cue.text)
        deduped_prepared.append(replace(cue, text=deduped_text))
        if removed:
            actions.append(
                {
                    "action": "dedupe_exact_lines",
                    "source_cues": list(cue.source_indices or (cue.index,)),
                    "removed_lines": removed,
                }
            )

    if not deduped_prepared:
        return [], actions, overlay_families

    clusters: list[list[Cue]] = []
    cluster_link_reasons: list[list[str]] = []
    current = [deduped_prepared[0]]
    current_reasons: list[str] = []

    for cue in deduped_prepared[1:]:
        previous = current[-1]
        gap = cue.start - previous.end
        pair_similarity = state_similarity(previous.text, cue.text)
        reason: str | None = None

        if gap <= max_gap_seconds and pair_similarity >= similarity_threshold:
            reason = "robust_similarity"
        elif _fragment_link(previous, cue, gap):
            reason = "fragment_or_line_coverage"
        elif _order_scramble_link(previous, cue, gap):
            reason = "character_order_scramble"
        elif gap <= 0.20 and _has_shared_anchor(previous, cue):
            reason = "shared_stable_line"

        if reason is not None:
            proposed_span = cue.end - current[0].start
            if proposed_span > max_cluster_span_seconds:
                reason = None

        if reason is not None and len(current) >= 3:
            representative = choose_representative(current)
            anchor_similarity = state_similarity(representative.text, cue.text)
            if (
                anchor_similarity < similarity_threshold - 0.08
                and not _has_shared_anchor(representative, cue)
                and not _order_scramble_link(representative, cue, 0.0)
                and pair_similarity < similarity_threshold + 0.04
            ):
                reason = None

        if reason is not None:
            current.append(cue)
            current_reasons.append(reason)
        else:
            clusters.append(current)
            cluster_link_reasons.append(current_reasons)
            current = [cue]
            current_reasons = []

    clusters.append(current)
    cluster_link_reasons.append(current_reasons)

    cleaned: list[Cue] = []

    for cluster, reasons in zip(clusters, cluster_link_reasons):
        representative = choose_representative(cluster)
        rep_diagnostics = representative_diagnostics(cluster, representative)

        source_indices = tuple(
            source_index
            for cue in cluster
            for source_index in (cue.source_indices or (cue.index,))
        )

        if len(cluster) > 1 and bool(rep_diagnostics["information_loss_risk"]):
            # Never silently collapse complementary recurring evidence into a
            # single lossy Cue. Keep a minimal observed evidence cover instead.
            cover = choose_evidence_cover(cluster)
            selected_sources: list[int | None] = []
            for member in cover:
                deduped_text, removed_lines = dedupe_exact_lines(member.text)
                result = Cue(
                    index=len(cleaned) + 1,
                    start=member.start,
                    end=member.end,
                    text=deduped_text,
                    source_indices=tuple(member.source_indices or (member.index,)),
                    selected_origin_index=member.selected_origin_index,
                )
                cleaned.append(result)
                selected_sources.append(member.selected_origin_index)

                if removed_lines:
                    actions.append(
                        {
                            "action": "dedupe_exact_lines",
                            "source_cues": list(member.source_indices or (member.index,)),
                            "removed_lines": removed_lines,
                        }
                    )

            actions.append(
                {
                    "action": "preserve_complementary_evidence_cluster",
                    "source_cues": list(source_indices),
                    "selected_source_cues": selected_sources,
                    "start": round(cluster[0].start, 3),
                    "end": round(max(cue.end for cue in cluster), 3),
                    "cluster_size": len(source_indices),
                    "link_reasons": sorted(set(reasons)),
                    **rep_diagnostics,
                }
            )
            continue

        selected_text, pruned_lines = prune_transient_lines(representative, cluster)
        result = Cue(
            index=len(cleaned) + 1,
            start=cluster[0].start,
            end=max(cue.end for cue in cluster),
            text=selected_text,
            source_indices=source_indices,
            selected_origin_index=representative.selected_origin_index,
        )
        cleaned.append(result)

        if len(cluster) > 1:
            actions.append(
                {
                    "action": "merge_state_cluster",
                    "source_cues": list(source_indices),
                    "selected_source_cue": representative.selected_origin_index,
                    "start": round(result.start, 3),
                    "end": round(result.end, 3),
                    "cluster_size": len(source_indices),
                    "link_reasons": sorted(set(reasons)),
                    "selected_text": result.text,
                    **rep_diagnostics,
                }
            )

        if pruned_lines:
            actions.append(
                {
                    "action": "prune_transient_lines",
                    "source_cues": list(source_indices),
                    "selected_source_cue": representative.selected_origin_index,
                    "removed_lines": pruned_lines,
                }
            )

    return cleaned, actions, overlay_families


def _covered_by_neighbor(fragment_text: str, neighbor_text: str) -> bool:
    """True only when every fragment line is strongly explainable as part of
    one neighboring Cue. This is deliberately asymmetric: the fragment may be
    a short prefix/suffix of a fuller line, but unrelated short Latin tokens
    such as "the"/"if" are not treated as sufficient evidence by themselves."""
    fragment_lines = _lines(fragment_text)
    neighbor_lines = _lines(neighbor_text)
    if not fragment_lines or not neighbor_lines:
        return False

    for fragment_line in fragment_lines:
        fragment_compact = compact_text(fragment_line)
        matched = False
        for neighbor_line in neighbor_lines:
            neighbor_compact = compact_text(neighbor_line)
            if robust_text_similarity(fragment_line, neighbor_line) >= 0.88:
                matched = True
                break
            if not fragment_compact or not neighbor_compact:
                continue
            if fragment_compact in neighbor_compact:
                has_cjk, has_latin = _script_profile(fragment_line)
                if has_cjk and len(fragment_compact) >= 2:
                    matched = True
                    break
                if has_latin and len(fragment_compact) >= 4:
                    matched = True
                    break
            if neighbor_compact in fragment_compact:
                ratio = len(neighbor_compact) / max(1, len(fragment_compact))
                if ratio >= 0.45:
                    matched = True
                    break
        if not matched:
            return False
    return True


def absorb_redundant_micro_fragments(
    cues: list[Cue],
) -> tuple[list[Cue], list[dict[str, object]]]:
    """Absorb a very short Cue into an immediately adjacent fuller Cue when
    every line in the short Cue is already represented by that neighbor.
    Text is never synthesized: the fuller neighbor's observed text wins."""
    if len(cues) < 2:
        return cues, []

    working = list(cues)
    actions: list[dict[str, object]] = []
    changed = True

    while changed:
        changed = False
        output: list[Cue] = []
        i = 0

        while i < len(working):
            cue = working[i]
            if cue.duration > 0.50:
                output.append(cue)
                i += 1
                continue

            candidates: list[tuple[float, str, int]] = []

            if output:
                previous = output[-1]
                gap = cue.start - previous.end
                if gap <= 0.10 and _covered_by_neighbor(cue.text, previous.text):
                    score = state_similarity(cue.text, previous.text) - max(0.0, gap)
                    candidates.append((score, "previous", -1))

            if i + 1 < len(working):
                following = working[i + 1]
                gap = following.start - cue.end
                if gap <= 0.10 and _covered_by_neighbor(cue.text, following.text):
                    score = state_similarity(cue.text, following.text) - max(0.0, gap)
                    candidates.append((score, "next", i + 1))

            if not candidates:
                output.append(cue)
                i += 1
                continue

            _, direction, neighbor_index = max(candidates, key=lambda item: item[0])
            cue_sources = list(cue.source_indices or (cue.index,))

            if direction == "previous":
                previous = output[-1]
                previous_sources = tuple(previous.source_indices or (previous.index,))
                output[-1] = replace(
                    previous,
                    end=max(previous.end, cue.end),
                    source_indices=previous_sources + tuple(cue_sources),
                )
                target_source = previous.selected_origin_index
                i += 1
            else:
                following = working[neighbor_index]
                following_sources = tuple(following.source_indices or (following.index,))
                working[neighbor_index] = replace(
                    following,
                    start=min(cue.start, following.start),
                    source_indices=tuple(cue_sources) + following_sources,
                )
                target_source = following.selected_origin_index
                i += 1

            actions.append(
                {
                    "action": "absorb_redundant_micro_fragment",
                    "source_cues": cue_sources,
                    "direction": direction,
                    "target_source_cue": target_source,
                    "text": cue.text,
                }
            )
            changed = True

        working = output + working[i:] if i < len(working) else output

    # Renumber only the transient lab index. Real source ids stay in source_indices.
    return [
        replace(cue, index=index)
        for index, cue in enumerate(working, start=1)
    ], actions


def remove_high_confidence_machine_tokens(
    cues: list[Cue],
) -> tuple[list[Cue], list[dict[str, object]]]:
    """Drop only ultra-short mixed alpha-numeric detector garbage such as
    'R90'. Plain words, single CJK characters, and pure numbers are preserved."""
    output: list[Cue] = []
    actions: list[dict[str, object]] = []

    for cue in cues:
        compact = compact_text(cue.text)
        has_alpha = any(char.isalpha() for char in compact)
        has_digit = any(char.isdigit() for char in compact)

        if (
            cue.duration <= 0.20
            and 2 <= len(compact) <= 4
            and has_alpha
            and has_digit
            and len(_lines(cue.text)) == 1
        ):
            actions.append(
                {
                    "action": "drop_high_confidence_machine_token",
                    "source_cues": list(cue.source_indices or (cue.index,)),
                    "text": cue.text,
                    "duration": round(cue.duration, 3),
                }
            )
            continue

        output.append(cue)

    return [
        replace(cue, index=index)
        for index, cue in enumerate(output, start=1)
    ], actions


def prune_short_latin_extra_lines(
    cues: list[Cue],
) -> tuple[list[Cue], list[dict[str, object]]]:
    """Remove a short Latin-only extra line when the same Cue already contains
    a substantial Latin subtitle line and a substantial CJK subtitle line.
    This targets OCR graphic fragments such as 'Fuent' / 'NIn' without
    deleting wrapped CJK subtitle lines."""
    output: list[Cue] = []
    actions: list[dict[str, object]] = []

    for cue in cues:
        lines = _lines(cue.text)
        if len(lines) < 3:
            output.append(cue)
            continue

        substantial_latin = [
            line
            for line in lines
            if _script_profile(line)[1]
            and not _script_profile(line)[0]
            and len(compact_text(line)) >= 12
        ]
        substantial_cjk = [
            line
            for line in lines
            if _script_profile(line)[0] and len(compact_text(line)) >= 6
        ]

        if not substantial_latin or not substantial_cjk:
            output.append(cue)
            continue

        kept: list[str] = []
        removed: list[str] = []
        for line in lines:
            has_cjk, has_latin = _script_profile(line)
            compact = compact_text(line)
            if (
                has_latin
                and not has_cjk
                and len(compact) <= 10
                and all(robust_text_similarity(line, anchor) < 0.70 for anchor in substantial_latin)
            ):
                removed.append(line)
            else:
                kept.append(line)

        if removed and kept:
            output.append(replace(cue, text="\n".join(kept)))
            actions.append(
                {
                    "action": "prune_short_latin_extra_line",
                    "source_cues": list(cue.source_indices or (cue.index,)),
                    "removed_lines": removed,
                }
            )
        else:
            output.append(cue)

    return output, actions


def strip_persistent_overlay_edges(
    cues: list[Cue],
    overlay_families: list[dict[str, object]],
) -> tuple[list[Cue], list[dict[str, object]]]:
    """Strip a LONG, repeatedly observed overlay phrase only when it appears
    as an exact prefix/suffix of a longer line. Arbitrary substring deletion
    remains forbidden. This safely handles cases such as a repeated
    'Speaker: Mel Robbins' label appended to a real English subtitle."""
    eligible_members: list[str] = []
    for family in overlay_families:
        if int(family.get("occurrence_count", 0)) < 6:
            continue
        if float(family.get("temporal_span_seconds", 0.0)) < 15.0:
            continue
        for member in family.get("members", []):
            member = str(member).strip()
            if len(compact_text(member)) >= 10:
                eligible_members.append(member)

    if not eligible_members:
        return cues, []

    output: list[Cue] = []
    actions: list[dict[str, object]] = []

    for cue in cues:
        new_lines: list[str] = []
        stripped_records: list[dict[str, str]] = []

        for line in _lines(cue.text):
            updated = line
            for member in eligible_members:
                pattern = re.escape(member)
                prefix = re.compile(rf"^\s*{pattern}\s*[:\-–—|]*\s+", flags=re.IGNORECASE)
                suffix = re.compile(rf"\s+[:\-–—|]*\s*{pattern}\s*$", flags=re.IGNORECASE)

                candidate = prefix.sub("", updated)
                if candidate != updated and candidate.strip():
                    stripped_records.append({"overlay": member, "from": updated, "to": candidate.strip()})
                    updated = candidate.strip()
                    continue

                candidate = suffix.sub("", updated)
                if candidate != updated and candidate.strip():
                    stripped_records.append({"overlay": member, "from": updated, "to": candidate.strip()})
                    updated = candidate.strip()

            if updated.strip():
                new_lines.append(updated.strip())

        if stripped_records:
            output.append(replace(cue, text="\n".join(new_lines)))
            actions.append(
                {
                    "action": "strip_persistent_overlay_edge",
                    "source_cues": list(cue.source_indices or (cue.index,)),
                    "changes": stripped_records,
                }
            )
        else:
            output.append(cue)

    return output, actions


def build_risk_report(actions: list[dict[str, object]]) -> dict[str, object]:
    """Separate conservative transformations from the ones worth a final human
    spot check. This is an audit surface, not a product UI contract."""
    low_types = {
        "dedupe_exact_lines",
        "remove_persistent_overlay_line",
        "strip_persistent_overlay_edge",
        "drop_high_confidence_machine_token",
    }
    medium_types = {
        "absorb_redundant_micro_fragment",
        "prune_short_latin_extra_line",
        "prune_transient_lines",
    }

    low: list[dict[str, object]] = []
    medium: list[dict[str, object]] = []
    review: list[dict[str, object]] = []

    for action in actions:
        action_type = str(action.get("action", ""))
        if action_type in low_types:
            low.append(action)
            continue
        if action_type in medium_types:
            medium.append(action)
            continue
        if action_type == "preserve_complementary_evidence_cluster":
            review.append(action)
            continue
        if action_type == "merge_state_cluster":
            reasons = set(action.get("link_reasons", []))
            cluster_size = int(action.get("cluster_size", 1))
            if bool(action.get("information_loss_risk")):
                review.append(action)
            elif reasons <= {"robust_similarity"} and cluster_size <= 4:
                low.append(action)
            elif "character_order_scramble" in reasons:
                medium.append(action)
            elif reasons <= {"robust_similarity", "fragment_or_line_coverage"} and cluster_size <= 8:
                medium.append(action)
            else:
                review.append(action)
            continue
        review.append(action)

    return {
        "low_risk_count": len(low),
        "medium_risk_count": len(medium),
        "human_spotcheck_count": len(review),
        "medium_risk_actions": medium,
        "human_spotcheck_actions": review,
    }


def _clean_cues_cycle(
    cues: list[Cue],
    *,
    similarity_threshold: float = 0.88,
    max_gap_seconds: float = 0.35,
    max_cluster_span_seconds: float = 8.0,
    max_passes: int = 6,
) -> tuple[list[Cue], dict[str, object]]:
    current = cues
    all_actions: list[dict[str, object]] = []
    all_overlay_families: list[dict[str, object]] = []
    pass_sizes: list[list[int]] = []

    for pass_number in range(1, max_passes + 1):
        cleaned, actions, overlay_families = clean_one_pass(
            current,
            similarity_threshold=similarity_threshold,
            max_gap_seconds=max_gap_seconds,
            max_cluster_span_seconds=max_cluster_span_seconds,
        )

        pass_sizes.append([len(current), len(cleaned)])
        for action in actions:
            action["pass"] = pass_number
        all_actions.extend(actions)

        if pass_number == 1:
            all_overlay_families = overlay_families

        if _semantic_signature(cleaned) == _semantic_signature(current):
            current = cleaned
            break
        current = cleaned

    # V0.4 conservative post-processing runs to a fixed point. V0.3 exposed
    # one real idempotence regression on sample C because a first post-pass
    # made a second safe micro-fragment absorption possible only after
    # serialization/re-entry. Running the same conservative transforms until
    # semantic stability makes clean(clean(x)) == clean(x) by construction.
    post_pass_sizes: list[list[int]] = []
    for post_pass_number in range(1, 7):
        before_signature = _semantic_signature(current)
        before_size = len(current)

        current, edge_actions = strip_persistent_overlay_edges(current, all_overlay_families)
        current, short_line_actions = prune_short_latin_extra_lines(current)
        current, micro_actions = absorb_redundant_micro_fragments(current)
        current, token_actions = remove_high_confidence_machine_tokens(current)

        post_actions = edge_actions + short_line_actions + micro_actions + token_actions
        for action in post_actions:
            action["post_pass"] = post_pass_number
        all_actions.extend(post_actions)

        post_pass_sizes.append([before_size, len(current)])
        if _semantic_signature(current) == before_signature:
            break

    risk_report = build_risk_report(all_actions)

    report = {
        "version": "0.6.1",
        "input_cue_count": len(cues),
        "output_cue_count": len(current),
        "cue_reduction": len(cues) - len(current),
        "cue_reduction_pct": round(
            (1.0 - len(current) / max(1, len(cues))) * 100.0, 2
        ),
        "similarity_threshold": similarity_threshold,
        "max_gap_seconds": max_gap_seconds,
        "max_cluster_span_seconds": max_cluster_span_seconds,
        "pass_sizes": pass_sizes,
        "post_pass_sizes": post_pass_sizes,
        "overlay_families": all_overlay_families,
        "risk_report": risk_report,
        "actions": all_actions,
    }
    return current, report


def clean_cues(
    cues: list[Cue],
    *,
    similarity_threshold: float = 0.88,
    max_gap_seconds: float = 0.35,
    max_cluster_span_seconds: float = 8.0,
    max_passes: int = 6,
    max_outer_cycles: int = 6,
) -> tuple[list[Cue], dict[str, object]]:
    """V0.4.1 whole-cleaner fixed point.

    V0.4 proved that post-processing itself could be stable while still
    exposing a new safe adjacency for the *main* clustering stage on a second
    invocation. The finalized semantics therefore need fixed-point execution
    around the entire cleaner, not merely around one layer of it.
    """
    current = cues
    cycle_reports: list[dict[str, object]] = []
    all_actions: list[dict[str, object]] = []
    outer_cycle_sizes: list[list[int]] = []
    first_overlay_families: list[dict[str, object]] = []

    for outer_cycle in range(1, max_outer_cycles + 1):
        before_signature = _semantic_signature(current)
        before_size = len(current)

        cleaned, cycle_report = _clean_cues_cycle(
            current,
            similarity_threshold=similarity_threshold,
            max_gap_seconds=max_gap_seconds,
            max_cluster_span_seconds=max_cluster_span_seconds,
            max_passes=max_passes,
        )

        if outer_cycle == 1:
            first_overlay_families = list(cycle_report.get("overlay_families", []))

        for action in cycle_report.get("actions", []):
            copied = dict(action)
            copied["outer_cycle"] = outer_cycle
            all_actions.append(copied)

        cycle_reports.append(
            {
                "outer_cycle": outer_cycle,
                "input_cue_count": before_size,
                "output_cue_count": len(cleaned),
                "pass_sizes": cycle_report.get("pass_sizes", []),
                "post_pass_sizes": cycle_report.get("post_pass_sizes", []),
            }
        )
        outer_cycle_sizes.append([before_size, len(cleaned)])
        current = cleaned

        if _semantic_signature(current) == before_signature:
            break

    risk_report = build_risk_report(all_actions)

    report = {
        "version": "0.6.1",
        "input_cue_count": len(cues),
        "output_cue_count": len(current),
        "cue_reduction": len(cues) - len(current),
        "cue_reduction_pct": round(
            (1.0 - len(current) / max(1, len(cues))) * 100.0, 2
        ),
        "similarity_threshold": similarity_threshold,
        "max_gap_seconds": max_gap_seconds,
        "max_cluster_span_seconds": max_cluster_span_seconds,
        "outer_cycle_sizes": outer_cycle_sizes,
        "cycle_reports": cycle_reports,
        "overlay_families": first_overlay_families,
        "risk_report": risk_report,
        "actions": all_actions,
    }
    return current, report
