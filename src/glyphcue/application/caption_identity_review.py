"""Rehydrate Hybrid review from immutable evidence, including after restart."""
from glyphcue.application.review_priority import ReviewPriority, ReviewSignals, compute_review_priority
from glyphcue.domain.caption_identity import CONTRACT_KEY, caption_identity_evidence
from glyphcue.domain.cue import Cue
from glyphcue.domain.observation import Observation


def restored_caption_review_priority(cue: Cue, observations: dict[str, Observation]) -> ReviewPriority:
    """Keep legacy restart behavior, but never erase new identity uncertainty."""
    members = [observations[i] for layer in cue.language_layers for i in layer.observation_ids if i in observations]
    if not any(CONTRACT_KEY in o.provenance.detail for o in members):
        return ReviewPriority(cue.id, 0.0, "None", ())
    alternatives = tuple(dict.fromkeys(
        block.text for o in members if (e := caption_identity_evidence(o)) is not None
        for p in e.probes for block in p.alternatives
    ))
    # Persisted edits can change Cue timing/text. Do not re-run reconstruction
    # over them or claim approval; retain the evidence's review obligation.
    return compute_review_priority(ReviewSignals(
        cue.id, None, True, 0, 0,
        ("caption_identity_review", "Caption identity / timing requires review. Alternatives: " + " | ".join(alternatives)),
    ))


def caption_evidence_summary(observation: Observation) -> str | None:
    evidence = caption_identity_evidence(observation)
    if evidence is None:
        return None
    envelope = evidence.envelope
    lines = [
        f"CoarseEnvelope {envelope.observed_start:.3f}–{envelope.observed_end:.3f}s; representative {envelope.representative_pts:.3f}s",
        f"Verification: {evidence.stop_reason}; {evidence.selection_rationale}",
        f"Boundary brackets: {evidence.boundary_brackets}",
        f"Unqueried observation intervals: {evidence.unqueried_intervals}",
        "Time between probes remains unverified; no continuous caption is inferred.",
    ]
    for probe in evidence.probes:
        lines.append(f"{probe.pts:.3f}s selected: {probe.selected_text!r}; Alternatives:")
        lines.extend(f"  [{i}] {block.text}" for i, block in enumerate(probe.alternatives, 1))
    return "\n".join(lines)
