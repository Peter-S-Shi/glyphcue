from __future__ import annotations

import uuid
from dataclasses import replace

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


def _find_index(cues: list[Cue], cue_id: str) -> int:
    for index, cue in enumerate(cues):
        if cue.id == cue_id:
            return index
    raise ValueError(f"No Cue with id {cue_id!r} in the given list")


def approve_cue(cues: list[Cue], cue_id: str) -> list[Cue]:
    """Marks one Cue APPROVED, the QA pane's single dominant action
    (DESIGN.md section 23) -- leaves every other Cue in `cues`
    untouched. Returns a new list; `cues` itself is never mutated."""
    result = list(cues)
    index = _find_index(result, cue_id)
    result[index] = replace(result[index], review_state=ReviewState.APPROVED)
    return result


def discard_cue(cues: list[Cue], cue_id: str) -> list[Cue]:
    """Marks one Cue REJECTED -- reuses the existing `ReviewState` enum
    value, no schema change needed for Discard (DESIGN.md section 23)."""
    result = list(cues)
    index = _find_index(result, cue_id)
    result[index] = replace(result[index], review_state=ReviewState.REJECTED)
    return result


def edit_cue_language_text(cues: list[Cue], cue_id: str, language: str, new_text: str) -> list[Cue]:
    """Replaces one language layer's reconstructed text with a
    human-edited correction, keeping that layer's `observation_ids` --
    a manual correction does not discard the evidence that led to the
    original reconstruction. Raises `ValueError` if `cue_id` or
    `language` isn't found. Never adds per-layer timing (ROADMAP M6/M7:
    Language Layers always inherit the Cue's own timing)."""
    result = list(cues)
    index = _find_index(result, cue_id)
    cue = result[index]

    layers = list(cue.language_layers)
    for layer_index, layer in enumerate(layers):
        if layer.language == language:
            layers[layer_index] = replace(layer, text=new_text)
            result[index] = replace(cue, language_layers=tuple(layers))
            return result
    raise ValueError(f"Cue {cue_id!r} has no language layer {language!r}")


def nudge_cue_timing(
    cues: list[Cue], cue_id: str, *, start_delta: float = 0.0, end_delta: float = 0.0
) -> list[Cue]:
    """Adjusts one Cue's `start_time`/`end_time` by the given deltas --
    Cue-level only, since Language Layers have no timing of their own
    to nudge (ROADMAP section 4, frozen). Reuses `Cue`'s own
    `__post_init__` invariants (non-negative start, end after start) to
    reject an invalid nudge, rather than re-deriving that validation
    here."""
    result = list(cues)
    index = _find_index(result, cue_id)
    cue = result[index]
    result[index] = replace(
        cue,
        start_time=cue.start_time + start_delta,
        end_time=cue.end_time + end_delta,
    )
    return result


def split_cue(cues: list[Cue], cue_id: str, split_time: float) -> list[Cue]:
    """Replaces one Cue with two, at `split_time` (which must fall
    strictly between the Cue's own start and end). Both halves start
    out with the SAME language-layer text as the original -- GlyphCue
    has no automatic re-segmentation evidence for where each half's
    real text boundary falls, so this is a QA affordance for the human
    to then edit each half, not a claim that the split text is already
    correct. Both halves keep every original observation_id (the
    evidence genuinely does span the whole original range, and there is
    no way to know which half it belongs to without human input) and
    are marked NEEDS_REVIEW, never auto-approved -- a machine split is
    not itself a correct reconstruction.
    """
    result = list(cues)
    index = _find_index(result, cue_id)
    cue = result[index]
    if not (cue.start_time < split_time < cue.end_time):
        raise ValueError(
            f"split_time {split_time!r} must be strictly between "
            f"{cue.start_time!r} and {cue.end_time!r}"
        )

    first = replace(
        cue,
        id=str(uuid.uuid4()),
        end_time=split_time,
        review_state=ReviewState.NEEDS_REVIEW,
    )
    second = replace(
        cue,
        id=str(uuid.uuid4()),
        start_time=split_time,
        review_state=ReviewState.NEEDS_REVIEW,
    )
    result[index : index + 1] = [first, second]
    return result


_MERGED_TEXT_SEPARATOR = "\n"
"""The join between two merged language layers' text: a plain
structural line break, not a space. A space silently assumes a Western
ASCII word-boundary convention (English "Hello" + "world" ->
"Hello world" reads fine; the same join is meaningless for scripts with
no inter-word space at all). A newline makes no assumption about word
boundaries in any script and mirrors how multiple language layers are
already joined on export (`Pysubs2SubtitleFormatAdapter.write`) -- it is
a placeholder for the human reviewer to actually fix (the merged Cue is
marked NEEDS_REVIEW, never auto-approved), not an attempt at real
CJK-aware text-boundary normalization, which is out of scope here (see
Milestone 8)."""


def _deduplicated_ids(first_ids: tuple[str, ...], second_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Concatenates two observation-id tuples, order-preserving, without
    duplicating an id present in both -- e.g. merging two Cues that both
    came from the same prior Split, which gives each half every original
    id (see `split_cue`)."""
    combined = list(first_ids)
    seen = set(combined)
    for observation_id in second_ids:
        if observation_id not in seen:
            combined.append(observation_id)
            seen.add(observation_id)
    return tuple(combined)


def merge_cues(cues: list[Cue], first_cue_id: str, second_cue_id: str) -> tuple[list[Cue], str]:
    """Combines two Cues into one, spanning the full range of both.
    Matching-language layers are combined (text joined by
    `_MERGED_TEXT_SEPARATOR`, evidence ids unioned with stable dedup);
    a language present in only one of the two Cues is kept as-is, still
    counted as real evidence, not a missing layer. Layer order follows
    the first Cue's own language order, then any additional languages
    only the second Cue had. The result is marked NEEDS_REVIEW -- a
    machine merge is not itself a correct reconstruction.
    `first_cue_id` and `second_cue_id` must both exist and be different
    Cues; raises `ValueError` otherwise.

    Returns `(cues, merged_cue_id)` -- the merged Cue's own fresh id, so
    a caller can reliably locate it in the returned list without
    guessing (e.g. "the first Cue whose id isn't one of the two old
    ones" silently picks the wrong Cue whenever a third, unrelated Cue
    happens to sort earlier in the list).
    """
    if first_cue_id == second_cue_id:
        raise ValueError("Cannot merge a Cue with itself")
    result = list(cues)
    first_index = _find_index(result, first_cue_id)
    second_index = _find_index(result, second_cue_id)
    first = result[first_index]
    second = result[second_index]

    first_layers_by_language = {layer.language: layer for layer in first.language_layers}
    second_layers_by_language = {layer.language: layer for layer in second.language_layers}
    languages_in_order = list(first_layers_by_language) + [
        language for language in second_layers_by_language if language not in first_layers_by_language
    ]

    merged_layers: list[LanguageLayer] = []
    for language in languages_in_order:
        first_layer = first_layers_by_language.get(language)
        second_layer = second_layers_by_language.get(language)
        if first_layer is not None and second_layer is not None:
            merged_layers.append(
                LanguageLayer(
                    language=language,
                    text=f"{first_layer.text}{_MERGED_TEXT_SEPARATOR}{second_layer.text}",
                    observation_ids=_deduplicated_ids(
                        first_layer.observation_ids, second_layer.observation_ids
                    ),
                )
            )
        else:
            merged_layers.append(first_layer or second_layer)  # type: ignore[arg-type]

    merged = Cue(
        id=str(uuid.uuid4()),
        start_time=min(first.start_time, second.start_time),
        end_time=max(first.end_time, second.end_time),
        language_layers=tuple(merged_layers),
        review_state=ReviewState.NEEDS_REVIEW,
    )

    lower_index, higher_index = sorted((first_index, second_index))
    result.pop(higher_index)
    result.pop(lower_index)
    result.insert(lower_index, merged)
    return result, merged.id
