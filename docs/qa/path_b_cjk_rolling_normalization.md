# Path B Deepening: CJK / Rolling Normalization — Milestone 8

This document answers ROADMAP.md section 15's acceptance gate: what the deepened Path B reconstruction does, why it's built this way, and what the evaluation shows.

## What M8 actually is

M1's thin Path B slice proved `Observation -> Cue`, non-destructive export, and one CJK fixture. M8 deepens that into a conservative, explainable, CJK-safe timed-caption normalizer, without touching Path A's OCR/M5/M6 algorithms or M7's shared QA shell. The governing rule, stated by the milestone's own framing: **content GlyphCue can reliably identify as rolling/noise is restored; content it cannot confidently classify is preserved with evidence, never guessed at.**

## Diagnosis before fix

`reconstruct_cues_with_diagnostics` (`src/glyphcue/application/reconstruction.py`) sorts Observations by `start_time` for processing (unavoidable -- reconstruction needs chronological order), but that sort is never allowed to silently erase evidence that the SOURCE file's own order disagreed with it. Before sorting, every Observation's original (file) position is recorded; after reconstruction, any Cue whose supporting Observations were not already in that original order gets `source_order_issue=True` -- a real, checkable fact, not a guess. `reconstruct_cues()` (the pre-M8 signature, used by `run_thin_path_b`) is now a thin wrapper that discards the diagnostics half; nothing about its own behavior changed.

## Conservative transformation, driven by a hand-authored fixture matrix

`tests/application/test_path_b_diagnostics.py` is the ground-truth fixture matrix this milestone was built against (TDD, red before green): clean English/CJK 1:1 preservation, growing-window rolling, sliding overlap, exact-duplicate and backtracking repetition, a coincidental single-character false-merge guard, unrelated-but-overlapping-timing captions, and out-of-order source input. Every case's expected Cue text/timing AND expected diagnostic classification were written down before the implementation was touched.

The core mechanism is unchanged from M1 in spirit -- character-level overlap between the accumulated run text and the next Observation's text, never whitespace tokens, never English terminal punctuation, never a fixed character width, never a `>>` speaker marker (the seed cleaner's Latin-centric assumptions GLYPHCUE_PRODUCT_ARCHITECTURE.md section 8.4 explicitly calls out as NOT to be preserved as product truth -- M1 already avoided all of them, and M8 does not reintroduce any). What M8 adds:

- **A minimum meaningful overlap floor (`_MIN_MEANINGFUL_OVERLAP = 2`).** A length-1 character match is exactly as likely to be coincidental (e.g. "...a lot" / "totally different topic" share one "t") as it is to be real continuation. Below this floor, two temporally-overlapping captions are never merged -- they are kept separate and flagged `segmentation_ambiguous`, the conservative default. This is a length threshold on the overlap itself, not a script-specific heuristic, so it applies identically to CJK and Western text (verified by both an English and a CJK sliding-overlap fixture at overlap lengths well above the floor, and an English fixture exactly at the floor's boundary).
- **A three-way continuation classification** (`_continuation_kind`): `growth` (the new reading retains the ENTIRE accumulated text as its own prefix and extends it -- classic growing-window rolling), `sliding` (a partial overlap, both sides extend beyond the shared region -- old content drops off the front while new content appends at the end), and `repetition` (the new reading adds no new content at all -- an exact duplicate reading, or a backtrack that repeats a tail already present). These are reported as three DISTINCT diagnostics (`rolling_growth`, `sliding_overlap`, `repetition_collapsed`), not folded into one generic "merged" flag, because a reviewer's confidence in each is different and DESIGN.md section 14.1 asks the evidence stream to show the real overlap/rolling relationship, not just "something changed."
- **`timing_collision`**: temporal overlap with NO textual relationship at all (e.g. two genuinely different simultaneous captions) -- kept separate, exactly as M1 already did, now named and surfaced as a real diagnostic rather than an implicit non-merge.

### Why there is no separate "malformed_preserved" flag

`Observation.__post_init__` already rejects negative/inverted timing before reconstruction ever sees it, and `Pysubs2SubtitleFormatAdapter.parse` already drops blank/whitespace-only captions at the parse boundary. The realistic "malformed but recoverable" cases inside this domain model -- out-of-order source position, overlapping-but-unrelated entries, duplicate/backtracking readings -- are exactly what `source_order_issue`, `timing_collision`, and `repetition_collapsed` already name. A distinct "malformed" flag with no real fixture behind it would be diagnostic theater, not diagnostic truth; this is stated explicitly in the `PathBDiagnostics` docstring rather than left as a silent omission.

## Diagnostics -> Review Priority (minimal, truthful wiring)

`review_signals_from_path_b_diagnostics` (`src/glyphcue/application/review_priority.py`) maps ONLY the three "reconstruction was not confident" phenomena -- `source_order_issue`, `timing_collision`, `segmentation_ambiguous` -- onto `ReviewSignals.had_disagreement`. `rolling_growth` / `sliding_overlap` / `repetition_collapsed` -- the confidently-resolved cases -- never contribute a component on their own; a Cue where GlyphCue successfully collapsed a rolling caption gets `level="None"` ("No Review Flags"), exactly matching the milestone's framing that confidently-restored content does not need a human to re-check it.

**Reusing `had_disagreement`'s wording would have been dishonest**, though: M5's hardcoded explanation text ("the winning text was chosen by majority vote") describes an OCR cross-frame vote that does not exist in Path B at all. Rather than force a false explanation to get a "free" score out of the existing machinery, `ReviewSignals` gained one small, backward-compatible field -- `disagreement_detail: tuple[str, str] | None` -- an optional `(component_name, explanation)` override, used verbatim when present and falling back to the original Path A wording when absent (M5/M6 callers are unaffected; verified by a regression). `review_signals_from_path_b_diagnostics` builds a real, specific explanation naming exactly which phenomenon (or phenomena) fired. This is the "minimal, transparent wiring" the milestone asked for, not a forced score: diagnostic truth over a clean architecture diagram.

`parse_and_reconstruct` (`src/glyphcue/application/thin_path_b.py`) now returns `(cues, observations_by_id, diagnostics_by_cue_id)`; `PathBWorkspace` takes an optional `diagnostics_by_cue_id` and builds real `ReviewPriority`s from it via `compute_review_priority` -- the SAME shared scoring machinery Path A uses, inspected through the SAME `ReconstructionQaWorkspace` (no second QA UI was built). A caller that doesn't pass diagnostics (or a Cue with no diagnostics entry) still gets the honest pre-M8 `level="None"` fallback.

## Evaluation

`benchmarks/path_b_normalization/run_evaluation.py` -- 10 hand-authored, copyright-safe cases (a superset of the fixture matrix's categories), each with ground truth (expected Cue text/count and required diagnostic flags) defined independently of the reconstruction function's own output, reported broken out by category and language rather than a single pass/fail count.

| Category | English | CJK |
|---|---|---|
| Clean preservation | 1/1 | 1/1 |
| Rolling reconstruction (growth / sliding / repetition) | 3/3 | 2/2 |
| Over-merge guard (must NOT merge) | 2/2 | -- |
| Malformed-safe (out-of-order source) | 1/1 | -- |

**10/10 cases pass.** Raw output: `benchmarks/path_b_normalization/evaluation_results.json`. A 100% pass rate here is expected, not suspicious: these are the same hand-authored ground-truth fixtures the implementation was built against via red-before-green TDD (`tests/application/test_path_b_diagnostics.py`), not a held-out validation set -- the evaluation's value is the reproducible, categorized breakdown (so a future change that regresses, say, CJK sliding-overlap specifically is visible at a glance), not a claim of generalization beyond this fixture corpus. No scraped subtitle/transcript data is used anywhere.

**Under-merge risk** (a genuine rolling caption failing to merge) is exactly what the `rolling_reconstruction` category's pass rate measures; **over-merge risk** (two unrelated captions wrongly merged) is exactly what `over_merge_guard` measures. Both report 0 failures in this corpus.

## Clean-caption preservation and non-destructive export (unchanged contracts)

Normal, non-overlapping captions produce 1:1 Cues with unchanged text/timing and no diagnostic flags at all (verified for both English and CJK). Export continues through the existing `Pysubs2SubtitleFormatAdapter` (atomic temp-file-then-rename, source-overwrite refusal, `REJECTED`-Cue exclusion from M7) -- nothing about the non-destructive contract changed.

## Acceptance gate closure

1. Representative English rolling cases pass -- growing-window, sliding-overlap, exact-duplicate/backtrack repetition, all covered by both the fixture matrix and the evaluation.
2. Representative CJK rolling cases pass -- growing-window and sliding-overlap, via the same character-overlap mechanism, no separate CJK code path.
3. Malformed/out-of-order input has explicit safe behavior -- `source_order_issue` diagnosis (never silent-sorted away), `timing_collision`/`segmentation_ambiguous` for unrelated/ambiguous overlapping input, both kept separate rather than guessed at.
4. Original input remains preserved -- unchanged non-destructive export contract; source file is never overwritten.
5. Clean captions remain unchanged -- verified for English and CJK, no diagnostic flags, 1:1 Cue mapping.
6. Reconstructed output is inspectable through the shared QA shell -- `PathBWorkspace` feeds real `PathBDiagnostics` into the SAME `ReconstructionQaWorkspace` Path A uses, via `compute_review_priority`; no second QA UI was built.
7. Normalization quality is evaluated against ground-truth fixtures -- `benchmarks/path_b_normalization/run_evaluation.py`, reported per-category and per-language, not just "tests passed."

## Deliberately out of scope

M9 (V1 Product Completion & Feature Freeze) is not started. Path A OCR/M5/M6 reconstruction algorithms and the shared M7 QA shell are unchanged. No heavyweight tokenizer, sentence-segmentation model, or CJK-specific NLP library was introduced -- the character-overlap mechanism (already Unicode-safe from M1) was deepened with classification and a conservative minimum-overlap floor, not replaced with something more "clever." A production Path B GUI entrypoint (analogous to Path A's `create_path_a_app`) does not exist yet; `parse_and_reconstruct` + `PathBWorkspace` remain the internal application seam, exercised end-to-end by `tests/application/test_end_to_end_vertical_slice.py` -- wiring a real entrypoint is V1 product-completion scope (ROADMAP M9), not this milestone's.
