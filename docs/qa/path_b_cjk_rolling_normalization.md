# Path B Deepening: CJK / Rolling Normalization — Milestone 8

This document answers ROADMAP.md section 15's acceptance gate: what the deepened Path B reconstruction does, why it's built this way, and what the evaluation shows. This revision is a corrective pass over the initial M8 implementation: it closes a real, dangerous conservative-safety gap (text overlap alone could merge two temporally unrelated captions), an irregular-timing-span bug, a CJK-specific blind spot in the overlap floor, an inaccurate "malformed-safe" claim, and adds visibility for confidently-resolved normalization in the QA shell.

## What M8 actually is

M1's thin Path B slice proved `Observation -> Cue`, non-destructive export, and one CJK fixture. M8 deepens that into a conservative, explainable, CJK-safe timed-caption normalizer, without touching Path A's OCR/M5/M6 algorithms or M7's shared QA shell. The governing rule, stated by the milestone's own framing: **content GlyphCue can reliably identify as rolling/noise is restored; content it cannot confidently classify is preserved with evidence, never guessed at.**

## The most important fix: temporal eligibility

The initial implementation had a real, dangerous gap: its continuation check accepted a strong character-overlap match as sufficient evidence on its own, with NO requirement that the two captions actually overlap in time. Two genuinely unrelated, temporally distant captions that happened to share text -- even IDENTICAL text -- could be actively merged into one garbled Cue. This directly contradicts GlyphCue's own frozen principle: prefer to preserve and flag over confidently guessing wrong.

`_classify_transition` (`src/glyphcue/application/reconstruction.py`) now requires genuine temporal evidence for `"continue"`:

- **Growth and sliding overlap** require real temporal overlap (`previous_observation.end_time > next_observation.start_time`) PLUS a meaningful character overlap. Text overlap, however strong, is never sufficient by itself.
- **Repetition/backtrack collapsing** gets ONE narrow, explicit exception: an EXACT duplicate/backtrack reading (the next Observation adds no new content at all) within a small, fixed, fixture-justified gap (`_MAX_REPETITION_GAP_SECONDS = 1.0`) after the previous reading ends -- mirroring how a repeated caption can land in the next SRT entry with a small gap rather than genuine time overlap. This is a bounded window, not an unlimited one: two identical captions minutes apart are never collapsed (`test_far_distant_identical_captions_are_not_collapsed`).
- Two ordinary, non-overlapping, unrelated sentences that happen to share a real (2+ character) boundary word are never merged, because there is no temporal evidence of a rolling relationship at all (`test_non_overlapping_adjacent_sentences_with_a_coincidental_boundary_match_are_not_merged`).

## Irregular timing span fix

A merged Cue's `end_time` is now `max(observation.end_time for observation in the run)`, not the last-in-order Observation's own `end_time`. A run whose members' end_times are not monotonic with their start_times (a long first reading containing a shorter, later one) previously truncated the Cue's span to whichever Observation happened to be last, silently dropping real evidence (`test_merged_cue_span_covers_the_latest_end_time_not_just_the_last_observation`).

## The overlap floor, reconsidered for CJK

`_MIN_MEANINGFUL_OVERLAP = 2` still guards against a coincidental single-character match on a longer text. But a strict length floor was itself a blind spot: a one-character caption ("你") growing into a longer one ("你好，世界") is genuine rolling growth, not a coincidence -- the ENTIRE prior reading survives as a prefix, which is exactly what growth means, regardless of how short that prefix is. The floor now has one exception: an overlap that consumes the run's entire accumulated text as its own prefix (`overlap == len(accumulated_text)`) is treated as real growth no matter the length. A longer CJK caption whose LAST character coincidentally matches a temporally-overlapping but textually unrelated next caption's FIRST character is still correctly rejected as `segmentation_ambiguous` -- the accumulated text is NOT fully retained as a prefix, only its last character happens to match. Both directions are covered by paired fixtures (`test_cjk_single_character_whole_prefix_growth_is_real_rolling_growth` / `test_cjk_single_character_coincidental_boundary_match_is_not_growth`), and the rule is evaluated identically for every script -- it is a length/containment relationship, not a CJK-specific carve-out.

## Diagnosis before fix

`reconstruct_cues_with_diagnostics` sorts Observations by `start_time` for processing (unavoidable -- reconstruction needs chronological order), but that sort is never allowed to silently erase evidence that the SOURCE file's own order disagreed with it. Before sorting, every Observation's original (file) position is recorded; after reconstruction, any Cue whose supporting Observations were not already in that original order gets `source_order_issue=True`. `reconstruct_cues()` (used by `run_thin_path_b`) is a thin wrapper that discards the diagnostics half.

## Six named diagnostics, ground-truth fixture driven

`tests/application/test_path_b_diagnostics.py` is the fixture matrix this milestone was built and corrected against (TDD, red before green): clean English/CJK preservation, growing-window rolling, sliding overlap, exact-duplicate/backtrack repetition (bounded-gap), the coincidental-overlap over-merge guard (English and CJK, temporal AND non-temporal variants), far-distant-identical non-collapse, irregular timing span, and out-of-order source input.

- **`rolling_growth`** -- the ENTIRE accumulated text survives as next reading's prefix, extended further.
- **`sliding_overlap`** -- a partial overlap, both sides extend beyond the shared region (karaoke-style scroll).
- **`repetition_collapsed`** -- the next reading adds no new content (exact duplicate or backtrack), collapsed only under real temporal overlap or the bounded gap above.
- **`timing_collision`** -- temporal overlap with no textual relationship at all -- kept separate.
- **`segmentation_ambiguous`** -- a coincidental single-character match (not a full-prefix match) -- kept separate.
- **`source_order_issue`** -- the source file's own cue order disagreed with chronological order.

### Why there is no separate "malformed_preserved" reconstruction-level flag

`Observation.__post_init__` already rejects negative/inverted timing before reconstruction ever sees it. The realistic "malformed but recoverable" cases at the RECONSTRUCTION level -- out-of-order source position, overlapping-but-unrelated entries, duplicate/backtracking readings -- are exactly what `source_order_issue`, `timing_collision`, and `repetition_collapsed` already name. A distinct flag with no real fixture behind it would be diagnostic theater. (Malformed handling BELOW reconstruction -- at the import/parse boundary -- is real and separate; see the next section.)

## Malformed/recoverable import: a real, distinct parser defensive seam

A corrective finding: the first evaluation draft's "malformed_safe" category only ever exercised out-of-order source -- it should not have been described as general malformed-input robustness. This is now two separate, honestly-named things:

1. **`out_of_order_safe`** -- diagnosed at the reconstruction level (above).
2. **A real per-event defensive seam in `Pysubs2SubtitleFormatAdapter`.** Before this fix, ANY single domain-invalid event (e.g. an SRT entry with inverted timing, `end < start`) raised inside `Observation.__post_init__` and propagated uncaught, discarding the ENTIRE file -- including every legitimate caption around it. `parse_with_warnings(path)` now catches the per-event `ValueError`, skips only that event, and returns an explicit `ImportWarning(source_index, reason)` for it -- never a silent drop. `parse()` keeps its original signature (`list[Observation]`) for backward compatibility, as a thin wrapper that discards the warnings; `parse_and_reconstruct` (the real Path B application flow) does NOT discard them -- it now returns `(cues, observations_by_id, diagnostics_by_cue_id, import_warnings)`. A genuinely unparseable file (pysubs2 itself cannot read the structure at all) still fails fast -- no SRT/VTT parser rewrite was attempted, per this round's explicit minimal-scope instruction.

Verified end-to-end with a "valid + invalid + valid" fixture at both the adapter level and the `parse_and_reconstruct` application-flow level: two legitimate captions are recovered, the bad one is visible as a warning naming its source index.

## Diagnostics -> Review Priority (minimal, truthful wiring)

`review_signals_from_path_b_diagnostics` maps ONLY the three "reconstruction was not confident" phenomena -- `source_order_issue`, `timing_collision`, `segmentation_ambiguous` -- onto `ReviewSignals.had_disagreement`. The three confidently-resolved phenomena (`rolling_growth`, `sliding_overlap`, `repetition_collapsed`) never raise Review Priority on their own -- a Cue GlyphCue could reliably restore gets `level="None"` ("No Review Flags"), matching the milestone's framing.

Reusing `had_disagreement`'s default wording would have been dishonest (it describes an OCR majority vote that doesn't exist in Path B), so `ReviewSignals` gained a small, backward-compatible `disagreement_detail: tuple[str, str] | None` override, used verbatim when present; M5/M6 callers are unaffected.

### Confidently-resolved normalization is still visible, without raising priority

A corrective addition: a rolling/sliding/repetition Cue staying "No Review Flags" must not mean the reviewer sees a blank center pane with no explanation at all. `PathBWorkspace`'s existing DESIGN.md section 14.2 consolidation-explanation text (the SAME shared widget, no new UI) now appends a plain-language `Normalization: ...` line naming exactly which of the six diagnostics fired for the active Cue -- e.g. "Normalization: Rolling growth consolidated." -- independent of whether that phenomenon raised a Review Priority flag. Verified: a confidently-resolved rolling Cue shows BOTH "No Review Flags" in the priority label AND "Rolling growth consolidated" in the consolidation view (`test_confidently_resolved_rolling_cue_shows_normalization_kind_but_no_review_flags`).

## Evaluation

`benchmarks/path_b_normalization/run_evaluation.py` -- 17 hand-authored, copyright-safe cases (16 reconstruction-level cases plus 1 real adapter-level malformed-import case), ground truth defined independently of the functions' own output, reported per-category and per-language:

| Category | English | CJK |
|---|---|---|
| Clean preservation | 1/1 | 1/1 |
| Rolling reconstruction (growth / sliding / repetition / irregular span) | 5/5 | 3/3 |
| Over-merge guard (must NOT merge) | 4/4 | 1/1 |
| Out-of-order safe | 1/1 | -- |
| Malformed recoverable import (adapter-level, language-agnostic) | 1/1 | -- |

**17/17 cases pass.** Raw output: `benchmarks/path_b_normalization/evaluation_results.json`, which also carries an explicit `scope_note`: this is the same hand-authored ground-truth corpus the implementation was built and corrected against via TDD, not a held-out validation set -- the value is the reproducible, categorized breakdown of specific, deliberately adversarial edge cases (over-merge risk, irregular timing spans, CJK single-character growth vs. coincidence, malformed per-event import recovery), not a claim of generalization beyond this corpus.

**Over-merge risk** (the most dangerous failure mode -- actively merging two genuinely unrelated captions) is exactly what the `over_merge_guard` category measures, now covering both English and CJK, both temporally-overlapping-but-textually-thin and non-overlapping-but-textually-coincidental variants, plus the far-distant-identical-text case. **Under-merge risk** (a genuine rolling caption failing to merge) is what `rolling_reconstruction`'s pass rate measures. **Out-of-order** and **malformed/recoverable import** are reported as two separate, honestly-scoped categories, not conflated under one "malformed_safe" label.

## Clean-caption preservation and non-destructive export (unchanged contracts)

Normal, non-overlapping captions produce 1:1 Cues with unchanged text/timing and no diagnostic flags at all (verified for English and CJK). Export continues through `Pysubs2SubtitleFormatAdapter` (atomic temp-file-then-rename, source-overwrite refusal, `REJECTED`-Cue exclusion from M7) -- nothing about the non-destructive contract changed.

## Acceptance gate closure

1. Representative English rolling cases pass -- growing-window, sliding-overlap, bounded-gap repetition, irregular timing span, all requiring genuine temporal evidence.
2. Representative CJK rolling cases pass -- growing-window, sliding-overlap, and the single-character whole-prefix growth case, via the same character-overlap mechanism, no separate CJK code path.
3. Malformed/out-of-order input has explicit safe behavior -- `source_order_issue` diagnosis (never silent-sorted away); `timing_collision`/`segmentation_ambiguous` kept separate rather than guessed at; a real per-event import defensive seam recovers legitimate captions around one domain-invalid event, with an explicit warning, never a silent drop or whole-file failure.
4. Original input remains preserved -- unchanged non-destructive export contract; source file is never overwritten.
5. Clean captions remain unchanged -- verified for English and CJK, no diagnostic flags, 1:1 Cue mapping.
6. Reconstructed output is inspectable through the shared QA shell -- real `PathBDiagnostics` feed `ReviewPriority` via the SAME `ReconstructionQaWorkspace` Path A uses; confidently-resolved normalization is visible in the existing consolidation-explanation text even when it doesn't raise a review flag; no second QA UI was built.
7. Normalization quality is evaluated against ground-truth fixtures -- see table above; the evaluation explicitly separates out-of-order from malformed-import, and states its own scope (verified edge cases, not generalization).

## Deliberately out of scope

M9 (V1 Product Completion & Feature Freeze) is not started. Path A OCR/M5/M6 reconstruction algorithms and the shared M7 QA shell are unchanged. No heavyweight tokenizer, sentence-segmentation model, or CJK-specific NLP library was introduced. No SRT/VTT parser rewrite was attempted -- the defensive seam is a minimal per-event try/except in the existing adapter; a file pysubs2 itself cannot structurally parse still fails fast. Richer UI surfacing of import warnings (beyond being returned by `parse_and_reconstruct` and not silently dropped) is deferred. A production Path B GUI entrypoint (analogous to Path A's `create_path_a_app`) does not exist yet -- `parse_and_reconstruct` + `PathBWorkspace` remain the internal application seam, exercised end-to-end by `tests/application/test_end_to_end_vertical_slice.py`; wiring a real entrypoint is V1 product-completion scope (ROADMAP M9), not this milestone's.
