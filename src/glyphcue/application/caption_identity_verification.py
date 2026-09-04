"""Bounded text verification downstream of frozen visual grouping.

The caller owns OCR, raw persistence, cancellation and the resource cap. No
visual distances, calibrated cutoffs, or font/location-based caption rules.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

from glyphcue.domain.caption_identity import (
    CAPTION_IDENTITY_VERSION, CaptionBlock, CaptionIdentityEvidence, CaptionProbe,
    CoarseEnvelope, FrameObservationRef, TranscriptionIdentity,
)
from glyphcue.domain.observation import Observation


class CaptionProbeReadError(RuntimeError):
    """An OCR call failed; previously persisted probes must remain usable."""


def _bounds(region: Observation):
    if not region.geometry:
        return None
    xs, ys = zip(*region.geometry)
    return min(xs), min(ys), max(xs), max(ys)


def _spatial_blocks(regions: tuple[Observation, ...]) -> tuple[tuple[CaptionBlock, ...], bool]:
    boxes = [_bounds(r) for r in regions]
    neighbours: list[set[int]] = []
    for i, a in enumerate(boxes):
        eligible = []
        if a is not None:
            for j, b in enumerate(boxes):
                if i == j or b is None:
                    continue
                if min(a[2], b[2]) <= max(a[0], b[0]):
                    continue
                if min(a[3], b[3]) > max(a[1], b[1]):
                    continue
                eligible.append((max(a[1], b[1]) - min(a[3], b[3]), j))
        nearest = min((gap for gap, _ in eligible), default=None)
        neighbours.append({j for gap, j in eligible if gap == nearest})
    def components(edges: list[set[int]]) -> list[set[int]]:
        remaining = set(range(len(regions)))
        result = []
        while remaining:
            stack, component = [min(remaining)], set()
            while stack:
                index = stack.pop()
                if index in component:
                    continue
                component.add(index)
                stack.extend(edges[index] - component)
            remaining -= component
            result.append(component)
        return result

    reciprocal = [{j for j in adjacent if i in neighbours[j]}
                  for i, adjacent in enumerate(neighbours)]
    # One-sided nearest links are not proof of a split. They preserve a wider
    # chain hypothesis (e.g. three caption lines with unequal line spacing).
    coherent = [set(adjacent) for adjacent in neighbours]
    for i, adjacent in enumerate(neighbours):
        for j in adjacent:
            coherent[j].add(i)
    tight_components = components(reciprocal)
    chain_components = components(coherent)

    def block(component: set[int]) -> CaptionBlock:
        order = sorted(component, key=lambda i: (boxes[i][1], boxes[i][0], i) if boxes[i] else (0, 0, i))
        known = [boxes[i] for i in order if boxes[i] is not None]
        bounds = (min(a[0] for a in known), min(a[1] for a in known),
                  max(a[2] for a in known), max(a[3] for a in known)) if len(known) == len(order) else None
        return CaptionBlock("\n".join(regions[i].text for i in order), bounds,
                            tuple(regions[i].id for i in order))

    blocks = [block(component) for component in tight_components]
    partition_ambiguous = len(regions) > 1 and (
        len(blocks) == 1 or any(len(nearest) > 1 for nearest in neighbours)
        or chain_components != tight_components
    )
    if partition_ambiguous:
        existing = {b.region_ids for b in blocks}
        # Preserve intact chains AND singleton alternatives. These are explicit
        # layout hypotheses, never an instruction to concatenate them into a Cue.
        for component in chain_components + [{i} for i in range(len(regions))]:
            candidate = block(component)
            if candidate.region_ids not in existing:
                blocks.append(candidate)
                existing.add(candidate.region_ids)
    return tuple(blocks), partition_ambiguous


def _intersects(a, b) -> bool:
    return (a is not None and b is not None
            and min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]))


def _select_blocks(probes: tuple[CaptionProbe, ...]):
    if not probes:
        return (), False, "no_probes"
    reference = probes[0].blocks
    assignments = []
    ambiguous = any(p.partition_ambiguous for p in probes)
    for probe in probes:
        matches = [tuple(j for j, ref in enumerate(reference) if _intersects(b.bounds, ref.bounds))
                   for b in probe.blocks]
        unique = [m[0] for m in matches if len(m) == 1]
        if (len(unique) != len(probe.blocks) or len(set(unique)) != len(reference)
                or len(unique) != len(reference)):
            ambiguous = True
        assignments.append(matches)
    varying = set()
    if not ambiguous:
        for j in range(len(reference)):
            texts = {b.text for p, matches in zip(probes, assignments)
                     for b, match in zip(p.blocks, matches) if match == (j,)}
            if len(texts) > 1:
                varying.add(j)
    selected = []
    for probe, matches in zip(probes, assignments):
        # Variation is transcription evidence, not semantic caption-role proof.
        # A changing dashboard beside a static subtitle is a counterexample.
        # Keep every coherent candidate, including temporally static blocks.
        candidates = probe.blocks
        text = candidates[0].text if len(candidates) == 1 and not ambiguous else None
        # A blank probe is a reading, not a missing payload.
        if not candidates and not ambiguous:
            text = ""
        selected.append(replace(probe, alternatives=candidates, selected_text=text))
    rationale = "non_unique_partition_or_correspondence" if ambiguous else (
        "temporal_variation_not_role_proof" if varying else "retain_all_plausible_blocks")
    return tuple(selected), ambiguous, rationale


def verify_caption_identity(
    envelope: CoarseEnvelope,
    recognize: Callable[[FrameObservationRef, str], tuple[Observation, ...]],
    *,
    probe_budget: int,
    is_cancel_requested: Callable[[], bool],
) -> CaptionIdentityEvidence:
    """First/medoid/last, then deterministic largest-gap refinement.

    The budget bounds calls, not confidence. Matching endpoints still need
    interior probes; any leftover interval stays unverified. The caller must
    persist returned raw regions before returning from recognize.
    """
    samples = envelope.observations
    if isinstance(probe_budget, bool) or not isinstance(probe_budget, int) or probe_budget < 3:
        raise ValueError("probe_budget must be an integer >= 3")
    representative = next(i for i, s in enumerate(samples) if s.pts == envelope.representative_pts)
    mandatory = sorted({0, representative, len(samples) - 1})
    readings: dict[int, CaptionProbe] = {}
    stop_reason = "all_observations_probed"

    def read(index: int, reason: str) -> bool:
        nonlocal stop_reason
        if is_cancel_requested():
            stop_reason = "cancelled"
            return False
        sample = samples[index]
        try:
            regions = recognize(sample, reason)
        except CaptionProbeReadError:
            stop_reason = "ocr_failed"
            return False
        blocks, partition_ambiguous = _spatial_blocks(tuple(r for r in regions if r.text))
        readings[index] = CaptionProbe(sample.index, sample.pts, reason,
                                       tuple(r.id for r in regions), blocks, (), None, partition_ambiguous)
        return True

    for i in mandatory:
        if not read(i, "mandatory_first_representative_last"):
            break
    while len(readings) < probe_budget and stop_reason not in ("cancelled", "ocr_failed"):
        keys = sorted(readings)
        gaps = [(a, b) for a, b in zip(keys, keys[1:]) if b - a > 1]
        if not gaps:
            break
        def rank(pair):
            a, b = pair
            left = tuple(sorted(block.text for block in readings[a].blocks))
            right = tuple(sorted(block.text for block in readings[b].blocks))
            return left != right, b - a, -a
        a, b = max(gaps, key=rank)
        if not read((a + b) // 2, "bounded_interior_refinement"):
            break
    keys = sorted(readings)
    if stop_reason == "ocr_failed":
        pass
    elif is_cancel_requested():
        stop_reason = "cancelled"
    elif len(keys) < len(samples):
        stop_reason = "budget_exhausted"
    probes, ambiguous, rationale = _select_blocks(tuple(readings[i] for i in keys))
    if stop_reason in ("cancelled", "ocr_failed"):
        probes = tuple(replace(p, selected_text=None, alternatives=p.blocks) for p in probes)
        rationale = "interrupted_verification"
    identities: list[TranscriptionIdentity] = []
    for probe in probes:
        alternatives = tuple(b.text for b in probe.alternatives)
        if identities and identities[-1].alternatives == alternatives and identities[-1].selected_text == probe.selected_text:
            previous = identities.pop()
            identities.append(replace(previous, support_pts=previous.support_pts + (probe.pts,)))
        else:
            identities.append(TranscriptionIdentity(probe.selected_text, (probe.pts,), alternatives))
    unqueried = []
    if not keys:
        unqueried.append((envelope.observed_start, envelope.observed_end))
    else:
        if keys[0] > 0:
            unqueried.append((samples[0].pts, samples[keys[0]].pts))
        unqueried.extend((samples[a].pts, samples[b].pts) for a, b in zip(keys, keys[1:]) if b - a > 1)
        if keys[-1] < len(samples) - 1:
            unqueried.append((samples[keys[-1]].pts, samples[-1].pts))
    brackets = tuple((a.pts, b.pts) for a, b in zip(probes, probes[1:])
                     if tuple(x.text for x in a.alternatives) != tuple(x.text for x in b.alternatives))
    return CaptionIdentityEvidence(
        CAPTION_IDENTITY_VERSION, envelope, probes, tuple(identities), brackets, tuple(unqueried),
        len(keys) == len(samples), ambiguous, any(p.selected_text is None for p in probes),
        stop_reason, probe_budget, rationale,
    )
