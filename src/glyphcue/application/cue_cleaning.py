from __future__ import annotations

import uuid

from glyphcue.adapters import cue_cleaner_v0_6_1 as cleaner
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


def is_cleaner_eligible_cue(cue: Cue) -> bool:
    """A Cue may be handed to the Cue Cleaner only if it is still an
    untouched, single-language machine result.

    - `PENDING` only: `APPROVED`/`REJECTED`/`NEEDS_REVIEW` are protected
      human (or prior-cleaning) work and must never be re-cleaned.
    - Exactly one language layer only: the frozen V0.6.1 Cleaner's data
      model is a single flat text string per Cue. A Track Group with 2+
      selected languages produces every Cue with 2+ language layers
      sharing one Cue-level timing (ROADMAP.md section 4, frozen); there
      is no evidence-backed way to let the Cleaner's clustering decision
      (which can change a Cue's start/end time) apply independently per
      language layer without risking two layers of the "same" Cue ending
      up on different timings, which the domain model forbids. Rather
      than guess at a cross-language reconciliation rule, multi-language
      Cues are out of scope for this integration and are left untouched
      -- a deliberate, documented scope boundary, not a bug.
    """
    return cue.review_state == ReviewState.PENDING and len(cue.language_layers) == 1


def _dedupe_preserve_order(*id_groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for ids in id_groups:
        for observation_id in ids:
            if observation_id not in seen:
                seen.add(observation_id)
                result.append(observation_id)
    return tuple(result)


def clean_eligible_cues_for_source(cues: list[Cue]) -> list[Cue]:
    """Runs the frozen Cue Cleaner V0.6.1 over the eligible subset of
    `cues` and returns the COMPLETE recombined Cue set for one source.

    `cues` must be the complete current Cue set for one source (per
    `CueRepository.save_cues_for_source`'s atomic replace-all contract --
    see its docstring / M12 Cue Cleaner integration contract). Every
    protected Cue (`APPROVED`/`REJECTED`/`NEEDS_REVIEW`, or any
    multi-language Cue -- see `is_cleaner_eligible_cue`) passes through
    completely unchanged, same id, same object. Only eligible Cues are
    ever handed to the Cleaner or replaced.

    Ordinary cleaned/merged results keep `ReviewState.PENDING` (the
    Cleaner's normal machine output is not itself a human decision, same
    as a fresh OCR/reconstruction result). Any result the Cleaner could
    only produce via `preserve_complementary_evidence_cluster` (it found
    genuinely complementary recurring evidence no single observed Cue
    covers, and refused to synthesize or silently drop any of it) is
    marked `ReviewState.NEEDS_REVIEW` instead, per the frozen integration
    contract.

    Never synthesizes cue text: every output Cue's text is either an
    unchanged eligible Cue's original text, or text the frozen Cleaner
    itself selected/pruned from one or more real eligible Cues.
    """
    eligible = sorted(
        (cue for cue in cues if is_cleaner_eligible_cue(cue)),
        key=lambda cue: (cue.start_time, cue.end_time, cue.id),
    )
    protected = [cue for cue in cues if not is_cleaner_eligible_cue(cue)]

    if not eligible:
        return sorted(protected, key=lambda cue: (cue.start_time, cue.end_time, cue.id))

    # 1-based indices into `eligible`, matching the frozen Cleaner's own
    # `Cue.index`/`source_indices`/`selected_origin_index` bookkeeping --
    # this is the sole provenance link back to our own domain Cues.
    frozen_input = [
        cleaner.Cue(
            index=position,
            start=cue.start_time,
            end=cue.end_time,
            text=cue.language_layers[0].text,
            source_indices=(position,),
            selected_origin_index=position,
        )
        for position, cue in enumerate(eligible, start=1)
    ]

    cleaned_frozen, report = cleaner.clean_cues(frozen_input)

    needs_review_origin_indices: set[int] = set()
    for action in report.get("actions", []):
        if action.get("action") == "preserve_complementary_evidence_cluster":
            for origin_index in action.get("selected_source_cues", []):
                if origin_index is not None:
                    needs_review_origin_indices.add(int(origin_index))

    language = eligible[0].language_layers[0].language

    cleaned_domain_cues: list[Cue] = []
    for frozen_cue in cleaned_frozen:
        contributing = [eligible[index - 1] for index in frozen_cue.source_indices]
        observation_ids = _dedupe_preserve_order(
            *(cue.language_layers[0].observation_ids for cue in contributing)
        )

        is_unchanged_passthrough = (
            len(contributing) == 1
            and frozen_cue.text == contributing[0].language_layers[0].text
            and frozen_cue.start == contributing[0].start_time
            and frozen_cue.end == contributing[0].end_time
        )

        needs_review = (
            frozen_cue.selected_origin_index is not None
            and frozen_cue.selected_origin_index in needs_review_origin_indices
        )

        if is_unchanged_passthrough:
            # Real no-op: keep the exact same Cue (id and review_state
            # included) so an unaffected Cue never appears to "change"
            # across a Clean Cues click -- required for idempotence and
            # for not perturbing unrelated human-visible queue state.
            cleaned_domain_cues.append(contributing[0])
            continue

        cleaned_domain_cues.append(
            Cue(
                id=str(uuid.uuid4()),
                start_time=frozen_cue.start,
                end_time=frozen_cue.end,
                language_layers=(
                    LanguageLayer(
                        language=language,
                        text=frozen_cue.text,
                        observation_ids=observation_ids,
                    ),
                ),
                review_state=ReviewState.NEEDS_REVIEW if needs_review else ReviewState.PENDING,
            )
        )

    combined = cleaned_domain_cues + protected
    combined.sort(key=lambda cue: (cue.start_time, cue.end_time, cue.id))
    return combined
