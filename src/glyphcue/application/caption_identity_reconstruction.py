"""Fail-closed projection of versioned Hybrid evidence into editable Cues.

Only actual probes carry text, using the existing instant-marker convention.
Every other interval is an empty pending review Cue, including intervals between
adjacent detector observations: exhaustive sparse probes do not prove video
continuity. Alternatives remain in the persisted companion and diagnostics.
"""
from __future__ import annotations

from glyphcue.application.ocr_evidence_job import INSTANT_SPAN_SECONDS
from glyphcue.domain.caption_identity import (
    CONTRACT_KEY, ENVELOPE_KEY, caption_identity_evidence,
)
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation


def reconstruct_caption_identity(observations: list[Observation], processing_end_time: float | None):
    # Local import avoids making the typed domain contract depend on consensus.
    from glyphcue.application.consensus_reconstruction import ConsensusDiagnostics

    groups: dict[str, list[Observation]] = {}
    for observation in observations:
        if CONTRACT_KEY in observation.provenance.detail:
            groups.setdefault(observation.provenance.detail[ENVELOPE_KEY], []).append(observation)
    cues, diagnostics = [], []
    for envelope_id, raw in groups.items():
        by_id = {r.id: r for r in raw}
        companions = [(o, caption_identity_evidence(o)) for o in raw]
        companions = [(o, e) for o, e in companions if e is not None]
        if len(companions) > 1:
            raise ValueError("Duplicate caption envelope companion")

        def emit(start, end, text, ids, alternatives, reason, evidence=None):
            if processing_end_time is not None:
                end = min(end, processing_end_time)
            if end <= start:
                return
            cue_id = f"cue-identity-{envelope_id}-{len(cues)}"
            languages = {by_id[i].language for i in ids if i in by_id and by_id[i].language}
            language = next(iter(languages)) if len(languages) == 1 else "und"
            cue = Cue(cue_id, start, end, (LanguageLayer(language, text or "", tuple(ids)),))
            cues.append(cue)
            diagnostics.append(ConsensusDiagnostics(
                cue_id, len(ids), len(set(alternatives)), 0.0 if reason else 1.0,
                bool(reason), caption_alternatives=alternatives,
                disagreement_detail=reason, caption_identity=evidence,
            ))

        if not companions:
            # Interrupted/failed write: raw OCR survives, but no completed
            # verification authorizes selection or span extrapolation.
            for observation in raw:
                emit(observation.start_time, observation.end_time, None, (observation.id,),
                     (observation.text,), ("caption_identity_incomplete", "Incomplete caption verification; inspect raw evidence."))
            continue
        marker, evidence = companions[0]
        envelope = evidence.envelope
        cursor = envelope.observed_start
        all_ids = tuple(by_id)
        all_alternatives = tuple(dict.fromkeys(b.text for p in evidence.probes for b in p.alternatives))
        gap_reason = ("caption_identity_unverified", "Unverified time between OCR probes; no caption selected.")
        for probe in evidence.probes:
            for region_id in probe.raw_region_ids:
                if region_id not in by_id or by_id[region_id].start_time != probe.pts:
                    raise ValueError("Caption probe has missing or mismatched raw evidence")
            for block in probe.blocks + probe.alternatives:
                if block.text != "\n".join(by_id[i].text for i in block.region_ids):
                    raise ValueError("Caption block text does not match its raw evidence")
            emit(cursor, probe.pts, None, all_ids, all_alternatives, gap_reason, evidence)
            alternatives = tuple(b.text for b in probe.alternatives)
            reason = None
            if probe.selected_text is None:
                reason = ("caption_identity_ambiguity", "No unique caption block. Alternatives: " + " | ".join(alternatives))
            ids = (marker.id,) + probe.raw_region_ids
            end = probe.pts + INSTANT_SPAN_SECONDS
            emit(probe.pts, end, probe.selected_text, ids, alternatives, reason, evidence)
            cursor = end
        emit(cursor, envelope.observed_end + INSTANT_SPAN_SECONDS, None, all_ids,
             all_alternatives, gap_reason, evidence)
    # Distinct visual envelopes do not establish the transition between their
    # last/first observations either. Preserve that time in the existing review
    # queue, including the requested range tail, rather than silently dropping it.
    ordered = sorted(zip(cues, diagnostics), key=lambda item: item[0].start_time)
    for index, (left, left_diagnostic) in enumerate(ordered):
        right = ordered[index + 1][0] if index + 1 < len(ordered) else None
        end = right.start_time if right is not None else processing_end_time
        if end is None or end <= left.end_time:
            continue
        ids = left.language_layers[0].observation_ids
        alternatives = left_diagnostic.caption_alternatives
        if right is not None:
            ids = tuple(dict.fromkeys(ids + right.language_layers[0].observation_ids))
            alternatives = tuple(dict.fromkeys(alternatives + ordered[index + 1][1].caption_alternatives))
        gap = Cue(f"gap-{left.id}", left.end_time, end,
                  (LanguageLayer(left.language_layers[0].language, "", ids),))
        cues.append(gap)
        diagnostics.append(ConsensusDiagnostics(
            gap.id, len(ids), len(set(alternatives)), 0.0, True,
            alternatives, ("caption_identity_unverified", "Unverified time between visual envelopes or at the range tail."),
        ))
    return cues, diagnostics
