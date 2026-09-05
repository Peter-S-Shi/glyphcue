from __future__ import annotations

import uuid
from dataclasses import replace

from glyphcue.adapters import cue_cleaner_v0_6_1 as cleaner
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


def is_cleaner_eligible_cue(cue: Cue) -> bool:
    """A Cue may be handed to the Cue Cleaner only if it is still an
    untouched machine result: `PENDING` only. `APPROVED`/`REJECTED`/
    `NEEDS_REVIEW` are protected human (or prior-cleaning) work and must
    never be re-cleaned.

    Cues with any number of language layers are eligible -- see
    `clean_eligible_cues_for_source`'s module-level docstring for how a
    multi-language Cue's several layers are losslessly reconstructed
    from the frozen Cleaner's single flat-text output without guessing.
    """
    return cue.review_state == ReviewState.PENDING


def _dedupe_preserve_order(*id_groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for ids in id_groups:
        for observation_id in ids:
            if observation_id not in seen:
                seen.add(observation_id)
                result.append(observation_id)
    return tuple(result)


def _joined_lines_with_layer_index(cue: Cue) -> list[tuple[str, int]]:
    """Every real line of `cue`, across all its language layers in layer
    order, tagged with which layer it came from -- the exact sequence
    the frozen Cleaner sees once we join `cue`'s layers into one flat
    text. This tagged sequence, matched by content and order (never by
    guessing at script/language), is the sole basis for later
    attributing a surviving output line back to its original layer."""
    result: list[tuple[str, int]] = []
    for layer_index, layer in enumerate(cue.language_layers):
        for line in cleaner._lines(layer.text):
            result.append((line, layer_index))
    return result


def _joined_text(cue: Cue) -> str:
    return "\n".join(line for line, _ in _joined_lines_with_layer_index(cue))


def _reconstruct_multilayer_cue(
    frozen_cue: cleaner.Cue,
    contributing: list[Cue],
    donor: Cue,
    donor_attribution: list[tuple[str, int]],
    needs_review: bool,
) -> Cue | None:
    """Splits one cleaned frozen Cue's flat text back into GlyphCue
    LanguageLayers, using only facts already proven about the frozen
    algorithm (see its module docstring): every output Cue's text is a
    verbatim, order-preserving subsequence of exactly one original
    eligible Cue's own lines (the "donor", `Cue.selected_origin_index`)
    -- dedupe/prune/merge/absorb only ever drop or keep whole lines
    unchanged, never blend two Cues' lines into one new line. So each
    surviving output line can be matched, in order, against the donor's
    own known (line, layer_index) sequence -- content+order, not script
    detection or any other guess.

    Returns `None` if that assumption doesn't hold for this particular
    result (in practice: the rare `strip_persistent_overlay_edges`
    post-pass, which is the one frozen transformation that can modify a
    line's text rather than only keep or drop it whole, or a
    contributing Cue whose layer shape doesn't match the donor's). The
    caller must then fall back to leaving `contributing` untouched --
    never guess an attribution.
    """
    output_lines = cleaner._lines(frozen_cue.text)

    pointer = 0
    matched: list[tuple[str, int]] = []
    for line in output_lines:
        while pointer < len(donor_attribution) and donor_attribution[pointer][0] != line:
            pointer += 1
        if pointer >= len(donor_attribution):
            return None
        matched.append(donor_attribution[pointer])
        pointer += 1

    layer_count = len(donor.language_layers)
    if any(len(cue.language_layers) != layer_count for cue in contributing):
        return None

    lines_by_layer: list[list[str]] = [[] for _ in range(layer_count)]
    for line, layer_index in matched:
        lines_by_layer[layer_index].append(line)

    layer_emptied = False
    new_layers: list[LanguageLayer] = []
    for layer_index in range(layer_count):
        original_layer = donor.language_layers[layer_index]
        new_text = "\n".join(lines_by_layer[layer_index])
        if original_layer.text.strip() and not new_text.strip():
            # A whole language's captioning disappearing is a
            # meaningfully different outcome from ordinary pruning --
            # conservatively surface it for a human look rather than
            # silently accept it as routine.
            layer_emptied = True
        observation_ids = _dedupe_preserve_order(
            *(cue.language_layers[layer_index].observation_ids for cue in contributing)
        )
        new_layers.append(
            LanguageLayer(
                language=original_layer.language,
                text=new_text,
                observation_ids=observation_ids,
            )
        )

    final_needs_review = needs_review or layer_emptied
    return Cue(
        id=str(uuid.uuid4()),
        start_time=frozen_cue.start,
        end_time=frozen_cue.end,
        language_layers=tuple(new_layers),
        review_state=ReviewState.NEEDS_REVIEW if final_needs_review else ReviewState.PENDING,
    )


def clean_eligible_cues_for_source(cues: list[Cue]) -> list[Cue]:
    """Runs the frozen Cue Cleaner V0.6.1 over the eligible subset of
    `cues` and returns the COMPLETE recombined Cue set for one source.

    `cues` must be the complete current Cue set for one source (per
    `CueRepository.save_cues_for_source`'s atomic replace-all contract --
    see its docstring / M12 Cue Cleaner integration contract). Every
    protected Cue (`APPROVED`/`REJECTED`/`NEEDS_REVIEW`) passes through
    completely unchanged, same id, same object. Only eligible
    (`PENDING`) Cues are ever handed to the Cleaner or replaced.

    Multi-language Cues: the frozen Cleaner's data model is one flat
    text string per Cue. A Track Group with 2+ selected languages
    produces every Cue with 2+ language layers sharing one Cue-level
    timing (ROADMAP.md section 4, frozen), so each eligible Cue's layers
    are joined into one flat text (in layer order) before being handed
    to the Cleaner -- exactly the shape (multi-line, mixed-script text
    in one Cue) the frozen algorithm's own line-family/script-profile
    logic was already validated against. Each surviving output line is
    then attributed back to its original language layer by matching it,
    in order, against its donor Cue's own known line sequence (see
    `_reconstruct_multilayer_cue`) -- never by guessing (no script
    detection, no positional assumption beyond "lines keep their
    relative order", which the frozen algorithm's own line-preserving
    transformations guarantee). If that attribution can't be made safely
    for a particular result (the rare `strip_persistent_overlay_edges`
    post-pass, which can modify a line's text rather than only keep or
    drop it whole), every Cue that would have contributed to that result
    is left completely untouched instead -- a conservative fallback,
    never a guess.

    Ordinary cleaned/merged results keep `ReviewState.PENDING` (the
    Cleaner's normal machine output is not itself a human decision, same
    as a fresh OCR/reconstruction result). A result is marked
    `ReviewState.NEEDS_REVIEW` instead whenever: the Cleaner could only
    produce it via `preserve_complementary_evidence_cluster` (genuinely
    complementary recurring evidence no single observed Cue covers, kept
    rather than synthesized or dropped) -- including when that member's
    own text/timing needed no change at all, since the *reason* it
    survived is exactly this uncertainty, not because nothing happened;
    or a whole language layer that had real text lost all of it during
    cleaning.

    Never synthesizes cue text: every output Cue's text is either an
    unchanged eligible Cue's original text, or text/lines the frozen
    Cleaner itself selected/pruned/kept from one or more real eligible
    Cues.
    """
    eligible = sorted(
        (cue for cue in cues if is_cleaner_eligible_cue(cue)),
        key=lambda cue: (cue.start_time, cue.end_time, cue.id),
    )
    protected = [cue for cue in cues if not is_cleaner_eligible_cue(cue)]

    if not eligible:
        return sorted(protected, key=lambda cue: (cue.start_time, cue.end_time, cue.id))

    joined_texts = [_joined_text(cue) for cue in eligible]
    line_attributions = [_joined_lines_with_layer_index(cue) for cue in eligible]

    # 1-based indices into `eligible`, matching the frozen Cleaner's own
    # `Cue.index`/`source_indices`/`selected_origin_index` bookkeeping --
    # this is the sole provenance link back to our own domain Cues.
    frozen_input = [
        cleaner.Cue(
            index=position,
            start=cue.start_time,
            end=cue.end_time,
            text=text,
            source_indices=(position,),
            selected_origin_index=position,
        )
        for position, (cue, text) in enumerate(zip(eligible, joined_texts), start=1)
    ]

    cleaned_frozen, report = cleaner.clean_cues(frozen_input)

    needs_review_origin_indices: set[int] = set()
    for action in report.get("actions", []):
        if action.get("action") == "preserve_complementary_evidence_cluster":
            for origin_index in action.get("selected_source_cues", []):
                if origin_index is not None:
                    needs_review_origin_indices.add(int(origin_index))

    cleaned_domain_cues: list[Cue] = []
    for frozen_cue in cleaned_frozen:
        contributing = [eligible[index - 1] for index in frozen_cue.source_indices]
        donor_index = frozen_cue.selected_origin_index

        if donor_index is None:
            # Should not happen given how frozen_input/the frozen
            # algorithm itself always propagate this field -- but if it
            # ever does, there is no safe donor to attribute text to.
            cleaned_domain_cues.extend(contributing)
            continue

        donor = eligible[donor_index - 1]
        needs_review = donor_index in needs_review_origin_indices

        is_unchanged_single_source = (
            len(contributing) == 1
            and frozen_cue.text == joined_texts[donor_index - 1]
            and frozen_cue.start == donor.start_time
            and frozen_cue.end == donor.end_time
        )

        if is_unchanged_single_source:
            if needs_review and donor.review_state != ReviewState.NEEDS_REVIEW:
                # Real, observed complementary evidence the Cleaner
                # refused to silently drop -- must surface for human
                # review even though this member's own text/timing
                # needed no change. Same id/provenance preserved; only
                # the review state flips.
                cleaned_domain_cues.append(replace(donor, review_state=ReviewState.NEEDS_REVIEW))
            else:
                # Real no-op: keep the exact same Cue (id and
                # review_state included) so an unaffected Cue never
                # appears to "change" across a Clean Cues click --
                # required for idempotence and for not perturbing
                # unrelated human-visible queue state.
                cleaned_domain_cues.append(donor)
            continue

        reconstructed = _reconstruct_multilayer_cue(
            frozen_cue,
            contributing,
            donor,
            line_attributions[donor_index - 1],
            needs_review,
        )
        if reconstructed is None:
            # Genuinely unsafe to attribute this transformation back to
            # per-language layers without guessing. Conservative
            # fallback: leave every contributing Cue exactly as it was
            # rather than risk misattributing or losing evidence.
            cleaned_domain_cues.extend(contributing)
            continue

        cleaned_domain_cues.append(reconstructed)

    combined = cleaned_domain_cues + protected
    combined.sort(key=lambda cue: (cue.start_time, cue.end_time, cue.id))
    return combined
