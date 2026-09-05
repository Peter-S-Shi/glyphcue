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
    Cues are additionally partitioned by their exact language-layer
    signature before ever being handed to the Cleaner together -- see
    `_language_signature` -- so this eligibility check alone does not
    guarantee two eligible Cues may be cleaned together.
    """
    return cue.review_state == ReviewState.PENDING


def _language_signature(cue: Cue) -> tuple[str, ...]:
    """The exact ordered tuple of language codes across `cue`'s layers.

    Current-source incremental OCR can leave PENDING Cues from an
    earlier range sitting alongside PENDING Cues from a later run made
    under a different Track Group language configuration (e.g. an
    earlier single-language `("en",)` run and a later bilingual
    `("en", "zh")` run, or even the same two languages in a different
    order). Two Cues with different signatures must never be merged or
    have their provenance cross-unioned by the Cleaner -- their
    `LanguageLayer` structures aren't comparable. Grouping by this exact
    signature before cleaning, and only ever cleaning within one group,
    is the isolation mechanism; `("en",)`, `("zh",)`, `("en", "zh")`, and
    `("zh", "en")` are all distinct groups by construction.
    """
    return tuple(layer.language for layer in cue.language_layers)


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


def _ambiguously_shared_lines(donor_attribution: list[tuple[str, int]]) -> set[str]:
    """Line texts that appear under more than one distinct layer index
    within one donor Cue -- e.g. a shared name/number/code that happens
    to read identically in two language layers. Ownership of such a
    line cannot be uniquely established from content+order alone."""
    layers_by_line: dict[str, set[int]] = {}
    for line, layer_index in donor_attribution:
        layers_by_line.setdefault(line, set()).add(layer_index)
    return {line for line, layers in layers_by_line.items() if len(layers) > 1}


def _reconstruct_cue(
    frozen_cue: cleaner.Cue,
    contributing: list[Cue],
    donor: Cue,
    donor_attribution: list[tuple[str, int]],
    needs_review: bool,
) -> Cue | None:
    """Builds one cleaned domain Cue from the frozen Cleaner's output,
    using only facts already proven about the frozen algorithm (see
    `clean_eligible_cues_for_source`'s docstring): every output Cue's
    text is a verbatim, order-preserving subsequence of exactly one
    original eligible Cue's own lines (the "donor",
    `Cue.selected_origin_index`) -- dedupe/prune/merge/absorb only ever
    drop or keep whole lines unchanged, never blend two Cues' lines into
    one new line.

    A single-language donor has no cross-layer attribution question at
    all -- the Cleaner's returned text is accepted directly into that
    one layer, even if it differs from every original line verbatim
    (e.g. the rare content-modifying `strip_persistent_overlay_edges`
    post-pass, which the frozen algorithm can genuinely produce for a
    single language just as validly as for multiple).

    A multi-language donor's surviving lines are attributed back to
    their own layer by matching them, in order, against the donor's own
    known (line, layer_index) sequence -- content+order, never script
    detection or any other guess. Returns `None` (caller must fall back
    to leaving `contributing` untouched, never guess) whenever that
    isn't safely possible: an output line that isn't a verbatim donor
    line (in practice, `strip_persistent_overlay_edges` again, this time
    across multiple layers where per-layer attribution actually
    matters); a contributing Cue whose layer shape doesn't match the
    donor's; or a surviving line whose text is genuinely ambiguous
    between two of the donor's own layers (a shared name/number/code
    read identically in both) -- ownership there cannot be uniquely
    established from existing provenance/order, so it is left alone
    rather than guessed.
    """
    layer_count = len(donor.language_layers)
    output_text = frozen_cue.text

    if layer_count == 1:
        original_layer = donor.language_layers[0]
        observation_ids = _dedupe_preserve_order(
            *(cue.language_layers[0].observation_ids for cue in contributing)
        )
        return Cue(
            id=str(uuid.uuid4()),
            start_time=frozen_cue.start,
            end_time=frozen_cue.end,
            language_layers=(
                LanguageLayer(
                    language=original_layer.language,
                    text=output_text,
                    observation_ids=observation_ids,
                ),
            ),
            review_state=ReviewState.NEEDS_REVIEW if needs_review else ReviewState.PENDING,
        )

    if any(len(cue.language_layers) != layer_count for cue in contributing):
        return None

    ambiguous_lines = _ambiguously_shared_lines(donor_attribution)
    output_lines = cleaner._lines(output_text)

    pointer = 0
    matched: list[tuple[str, int]] = []
    for line in output_lines:
        if line in ambiguous_lines:
            return None
        while pointer < len(donor_attribution) and donor_attribution[pointer][0] != line:
            pointer += 1
        if pointer >= len(donor_attribution):
            return None
        matched.append(donor_attribution[pointer])
        pointer += 1

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


def _joined_text_key(cue: Cue) -> tuple[tuple[str, str], ...]:
    """The exact (language, text) pair for every layer of `cue`, in layer
    order -- two Cues sharing this key are byte-for-byte the same
    observed result (same per-layer text), independent of id, timing, or
    observation_ids."""
    return tuple((layer.language, layer.text) for layer in cue.language_layers)


def _observation_provenance(cue: Cue) -> frozenset[str]:
    return frozenset(
        observation_id
        for layer in cue.language_layers
        for observation_id in layer.observation_ids
    )


def _is_edge_corrupted_fragment(fragment: str, caption: str) -> bool:
    """True only for a one-edge OCR corruption of a real caption fragment.

    Removing exactly one leading or trailing character from the shorter
    observation must leave a non-empty proper prefix or suffix of the full
    caption.  This deliberately does not introduce fuzzy similarity or an
    edit-distance threshold: anything less specific remains unresolved.
    """
    fragment_compact = cleaner.compact_text(fragment)
    caption_compact = cleaner.compact_text(caption)
    if len(fragment_compact) < 2 or len(fragment_compact) >= len(caption_compact):
        return False

    trimmed_edges = (fragment_compact[1:], fragment_compact[:-1])
    return any(
        trimmed and (caption_compact.startswith(trimmed) or caption_compact.endswith(trimmed))
        for trimmed in trimmed_edges
    )


def _is_proven_split_burst(
    left: tuple[Cue, tuple[int, ...]],
    middle: tuple[Cue, tuple[int, ...]],
    right: tuple[Cue, tuple[int, ...]],
) -> bool:
    """Whether three Cleaner outputs prove the narrow Case A split shape."""
    left_cue, left_sources = left
    middle_cue, middle_sources = middle
    right_cue, right_sources = right

    if (
        _joined_text_key(left_cue) != _joined_text_key(right_cue)
        or _joined_text_key(left_cue) == _joined_text_key(middle_cue)
        or any(
            cue.review_state != ReviewState.PENDING
            for cue in (left_cue, middle_cue, right_cue)
        )
    ):
        return False

    # Frozen Cleaner source indices are the authoritative ordering link back
    # to the adapter input. The noisy interruption must be exactly one origin,
    # with no missing/reused origins between the two caption sides.
    if not left_sources or len(middle_sources) != 1 or not right_sources:
        return False
    source_chain = left_sources + middle_sources + right_sources
    if (
        len(set(source_chain)) != len(source_chain)
        or source_chain != tuple(range(source_chain[0], source_chain[-1] + 1))
    ):
        return False

    # Reuse the frozen Cleaner's existing micro-fragment temporal contract;
    # this adapter adds no new calibrated window. Ordinary repeats separated
    # by a real gap fail closed and remain independent Cues.
    left_gap = middle_cue.start_time - left_cue.end_time
    right_gap = right_cue.start_time - middle_cue.end_time
    if middle_cue.end_time - middle_cue.start_time > 0.50:
        return False
    if not (0.0 <= left_gap <= 0.10 and 0.0 <= right_gap <= 0.10):
        return False

    provenance = tuple(_observation_provenance(cue) for cue in (left_cue, middle_cue, right_cue))
    if any(not ids for ids in provenance):
        return False
    if any(provenance[i] & provenance[j] for i in range(3) for j in range(i + 1, 3)):
        return False

    return _is_edge_corrupted_fragment(_joined_text(middle_cue), _joined_text(left_cue))


def _collapse_split_duplicate_cues(
    cues_with_sources: list[tuple[Cue, tuple[int, ...]]],
) -> list[Cue]:
    """Collapse only a provenance-proven `caption / garble / caption` split.

    Exact text plus temporal proximity is intentionally insufficient: two
    legitimate utterances may repeat nearby.  The adapter requires the exact
    consecutive-origin, micro-observation, edge-corruption structure of Human
    QA Case A. Any missing or ambiguous evidence preserves every Cue.
    """
    ordered = sorted(
        cues_with_sources,
        key=lambda item: (item[0].start_time, item[0].end_time, item[0].id),
    )
    result: list[Cue] = []
    index = 0
    while index < len(ordered):
        if index + 2 < len(ordered) and _is_proven_split_burst(
            ordered[index], ordered[index + 1], ordered[index + 2]
        ):
            result.append(_merge_duplicate_run([ordered[index][0], ordered[index + 2][0]]))
            result.append(ordered[index + 1][0])
            index += 3
            continue
        result.append(ordered[index][0])
        index += 1

    result.sort(key=lambda cue: (cue.start_time, cue.end_time, cue.id))
    return result


def _merge_duplicate_run(run: list[Cue]) -> Cue:
    if len(run) == 1:
        return run[0]

    first = run[0]
    layer_count = len(first.language_layers)
    new_layers = [
        LanguageLayer(
            language=first.language_layers[layer_index].language,
            text=first.language_layers[layer_index].text,
            observation_ids=_dedupe_preserve_order(
                *(cue.language_layers[layer_index].observation_ids for cue in run)
            ),
        )
        for layer_index in range(layer_count)
    ]
    return Cue(
        id=str(uuid.uuid4()),
        start_time=min(cue.start_time for cue in run),
        end_time=max(cue.end_time for cue in run),
        language_layers=tuple(new_layers),
        review_state=ReviewState.NEEDS_REVIEW,
    )


def _clean_one_signature_group(group: list[Cue]) -> list[Cue]:
    """Runs the frozen Cleaner over one language-signature-homogeneous
    group of eligible Cues (see `_language_signature`) and returns the
    cleaned/passthrough Cues for that group only."""
    eligible = sorted(group, key=lambda cue: (cue.start_time, cue.end_time, cue.id))

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

    # Keep the frozen source-index provenance beside each reconstructed Cue
    # until the narrow split-burst check has run. It remains adapter-local;
    # no domain or persistence schema change is required.
    result: list[tuple[Cue, tuple[int, ...]]] = []
    origin_index_by_id = {cue.id: index for index, cue in enumerate(eligible, start=1)}
    for frozen_cue in cleaned_frozen:
        contributing = [eligible[index - 1] for index in frozen_cue.source_indices]
        frozen_sources = tuple(int(index) for index in frozen_cue.source_indices)
        donor_index = frozen_cue.selected_origin_index

        if donor_index is None:
            # Should not happen given how frozen_input/the frozen
            # algorithm itself always propagate this field -- but if it
            # ever does, there is no safe donor to attribute text to.
            result.extend(
                (cue, (origin_index_by_id[cue.id],)) for cue in contributing
            )
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
                result.append(
                    (replace(donor, review_state=ReviewState.NEEDS_REVIEW), frozen_sources)
                )
            else:
                # Real no-op: keep the exact same Cue (id and
                # review_state included) so an unaffected Cue never
                # appears to "change" across a Clean Cues click --
                # required for idempotence and for not perturbing
                # unrelated human-visible queue state.
                result.append((donor, frozen_sources))
            continue

        reconstructed = _reconstruct_cue(
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
            # -- EXCEPT the donor must still honor the frozen
            # preserve_complementary_evidence_cluster contract: if this
            # specific result was one of the Cues that action selected
            # (genuinely complementary evidence the Cleaner refused to
            # drop), it must still surface as NEEDS_REVIEW rather than
            # silently reverting to PENDING just because the text-level
            # transformation itself had to be abandoned.
            if needs_review and donor.review_state != ReviewState.NEEDS_REVIEW:
                result.append(
                    (replace(donor, review_state=ReviewState.NEEDS_REVIEW), (donor_index,))
                )
                result.extend(
                    (cue, (origin_index_by_id[cue.id],))
                    for cue in contributing
                    if cue.id != donor.id
                )
            else:
                result.extend(
                    (cue, (origin_index_by_id[cue.id],)) for cue in contributing
                )
            continue

        result.append((reconstructed, frozen_sources))

    return _collapse_split_duplicate_cues(result)


def clean_eligible_cues_for_source(cues: list[Cue]) -> list[Cue]:
    """Runs the frozen Cue Cleaner V0.6.1 over the eligible subset of
    `cues` and returns the COMPLETE recombined Cue set for one source.

    `cues` must be the complete current Cue set for one source (per
    `CueRepository.save_cues_for_source`'s atomic replace-all contract --
    see its docstring / M12 Cue Cleaner integration contract). Every
    protected Cue (`APPROVED`/`REJECTED`/`NEEDS_REVIEW`) passes through
    completely unchanged, same id, same object. Only eligible
    (`PENDING`) Cues are ever handed to the Cleaner or replaced.

    Language-signature isolation: eligible Cues are partitioned by their
    exact ordered language-layer signature (`_language_signature`)
    before any cleaning happens, and each group is cleaned entirely
    independently. This matters because current-source incremental OCR
    can leave PENDING Cues from an earlier range (e.g. a single-language
    run) sitting alongside PENDING Cues from a later run made under a
    different Track Group language configuration (a different language
    set, or the same languages in a different order) -- those must never
    be merged or have their evidence cross-unioned by the Cleaner, since
    their `LanguageLayer` structures aren't comparable.

    Multi-language Cues: the frozen Cleaner's data model is one flat
    text string per Cue. Every Cue within one language-signature group
    has 2+ language layers sharing one Cue-level timing (ROADMAP.md
    section 4, frozen), so each eligible Cue's layers are joined into
    one flat text (in layer order) before being handed to the Cleaner --
    exactly the shape (multi-line, mixed-script text in one Cue) the
    frozen algorithm's own line-family/script-profile logic was already
    validated against. Each surviving output line is then attributed
    back to its original language layer by matching it, in order,
    against its donor Cue's own known line sequence (see
    `_reconstruct_cue`) -- never by guessing (no script detection, no
    positional assumption beyond "lines keep their relative order",
    which the frozen algorithm's own line-preserving transformations
    guarantee, and never resolving a line whose text is genuinely
    ambiguous between two of the donor's own layers). If that
    attribution can't be made safely for a particular result, every Cue
    that would have contributed to it is left completely untouched
    instead -- except a Cue the Cleaner specifically selected via
    `preserve_complementary_evidence_cluster` still surfaces as
    `NEEDS_REVIEW`, per that contract, rather than silently reverting to
    `PENDING` just because the text-level transformation had to be
    abandoned.

    A single-language Cue's result has no cross-layer attribution
    question at all, so the Cleaner's returned text is always accepted
    directly -- this includes the rare content-modifying
    `strip_persistent_overlay_edges` post-pass, which would otherwise
    look like an unsafe transformation if judged by the multi-language
    verbatim-subsequence rule.

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

    Split-duplicate safety net (Human QA Case A): the frozen Cleaner's
    adjacency-based clustering can occasionally split one persistent
    caption's burst of near-duplicate observed frames into two separate
    clusters -- e.g. a single non-absorbable garbled frame in the middle
    breaks the similarity link -- each of which independently reduces to
    the exact same per-layer text. Left alone, that is two domain Cues
    that are byte-identical representations of one real observed moment.
    `_collapse_split_duplicate_cues` (applied per language-signature
    group, after per-Cue reconstruction) merges only the provenance-proven
    consecutive-origin `caption / one garbled micro observation / same
    caption` shape, and always flags the merge `NEEDS_REVIEW`. Exact text
    plus temporal proximity alone is never treated as evidence: ordinary
    repeated dialogue remains independent, and any missing or ambiguous
    provenance fails closed.
    """
    eligible = [cue for cue in cues if is_cleaner_eligible_cue(cue)]
    protected = [cue for cue in cues if not is_cleaner_eligible_cue(cue)]

    if not eligible:
        return sorted(protected, key=lambda cue: (cue.start_time, cue.end_time, cue.id))

    groups: dict[tuple[str, ...], list[Cue]] = {}
    for cue in eligible:
        groups.setdefault(_language_signature(cue), []).append(cue)

    cleaned_domain_cues: list[Cue] = []
    for group in groups.values():
        cleaned_domain_cues.extend(_clean_one_signature_group(group))

    combined = cleaned_domain_cues + protected
    combined.sort(key=lambda cue: (cue.start_time, cue.end_time, cue.id))
    return combined
