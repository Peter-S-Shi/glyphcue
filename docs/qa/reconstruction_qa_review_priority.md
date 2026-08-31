# Reconstruction QA & Review Priority — Milestone 7

This document answers ROADMAP.md section 14's explainability requirement: what the shared QA seam and Review Priority ranking are, why they're built this way, where they knowingly fall short, and what the evaluation shows.

This revision is a corrective pass over the initial M7 implementation: it fixes a non-monotonic scoring bug, a label-leaking evaluation methodology, several real QA-session correctness bugs (lost edits, wrong "next" Cue on Merge, a curated-evidence cross-language false positive, an edit lost on immediate export), a Discard/export contract gap, and closes two small UI-affordance gaps (a fake Replay button, missing DESIGN.md section 23 action-hierarchy styling). None of it touches the shared shell, Path A/B integration, or M5/M6 reconstruction algorithms.

## What M7 actually is

M5 and M6 answered "how does GlyphCue reconstruct a Cue?" M7 answers a different question: "how does a human reviewer find and fix the reconstructions worth checking, quickly and traceably?" Nothing in this milestone touches M1/M5/M6's reconstruction algorithms — `reconstruct_cues`, `reconstruct_cues_with_consensus`, and `reconstruct_multilingual_cues_for_track_group` are unchanged. M7 is the human-in-the-loop half of the same closed loop: Evidence → Observation → Cue → Human Review → Export.

## The shared QA seam

`ReconstructionQaWorkspace` (`src/glyphcue/ui/reconstruction_qa_workspace.py`) is the single QA implementation both Path A (`PathAMediaPane`) and Path B (`PathBWorkspace`) embed — not two parallel QA implementations that happen to look similar. Only the CENTER pane content differs per path (DESIGN.md section 7.2 explicitly allows this: video/ROI for Path A's Visual Evidence Workspace, a consolidation explanation for Path B's Timed Text Evidence Workspace); the left queue and right QA pane are the identical widget tree, wired to the identical `cue_review_actions.py` pure functions, for both paths.

This directly closes ROADMAP M7 acceptance gate 1 ("Path A and Path B both fit the frozen shell") and gate 8 ("no full subtitle-editor scope has leaked in") by construction — there is only one QA implementation to keep in scope, not two to keep in sync.

### QA state is in-memory, not yet durable across restarts

`ReconstructionQaWorkspace` operates on a `list[Cue]` held in memory, exactly like the pre-M7 `PathBWorkspace` already did — it does not round-trip Approve/Split/Merge/Discard/edits through `CueRepository`. Two real reasons, not laziness:

1. `CueRepository` (`src/glyphcue/persistence/repository.py`) is insert-only (`add`, `get`, `list_all` — no `save`/`update`/`delete`) and cues aren't scoped by `evidence_run_id` in its schema at all. Making QA state durable properly would need real migration work.
2. ROADMAP M7 explicitly asks to reuse existing invariants and add migration only when a real QA persistence invariant demands it. Nothing in this milestone's acceptance gate requires QA progress to survive an app restart — Export is the actual durability boundary, and it already works (both paths write through `Pysubs2SubtitleFormatAdapter`, non-destructively).

This is a documented scope boundary, not a silent gap: a real product would likely want durable QA state before shipping, and that work is a natural, minimal-migration candidate for a future pass (add `evidence_run_id` + real `update`/`delete` to `CueRepository`), not attempted speculatively here.

### Pending-edit commit seam (corrective)

Every action that can switch the active Cue, rebuild the panel, or change a Cue — Approve, Discard, timing nudge, Split, Merge, Previous/Next, and a direct click on a different queue row — now commits whatever is currently typed into the language-layer text edits into `self._cues` FIRST, via `_commit_displayed_edits()`. Originally only Approve did this (`_apply_pending_text_edits`, only called from `approve_and_advance`); every other action silently discarded an in-progress hand edit. `_commit_displayed_edits` is keyed off `self._displayed_cue_id` (the Cue that was actually on screen just before the call), not `self.active_cue` — by the time a queue-row-change signal fires, `self.active_cue` already reflects the NEW row, so committing against it would silently no-op instead of saving the edit that was actually on screen. Regression coverage: `tests/ui/test_reconstruction_qa_workspace.py`'s `test_editing_text_then_{nudging,navigating_away_and_back,clicking_a_different_queue_row,splitting,merging_with_next,discarding}_retains_the_edit`.

**Immediate export also commits pending edits.** `ReconstructionQaWorkspace.commit_pending_edits()` is a minimal public persistence seam: it commits the displayed Cue's live editor content into the in-memory Cue list, and nothing else -- it never touches `review_state`, so calling it is not an implicit Approve. `PathBWorkspace.export()` calls it before reading `self.qa.cues`, so a hand-edit still sitting in the active text edit is not silently lost when the user exports immediately, without Approving or navigating away first. Regression: `test_editing_text_then_exporting_immediately_without_approving_exports_the_edit`.

### Keyboard focus correctness (corrective)

`Space`/`R`/`[`/`]` must never fire while a language-layer `QTextEdit` has real keyboard focus — Qt already does this correctly by default (a focused `QTextEdit` claims plain typed characters for itself via its own ShortcutOverride handling, before the window-level `QShortcut`s ever see them), verified with real `QTest.keyClick` events targeted at a focused text edit, not just `.activated.emit()` (which cannot prove this at all, since it bypasses Qt's own event/focus delivery entirely).

`Ctrl+Enter` (Approve) needed real, deliberate wiring to keep working while a text edit has focus, for two separate reasons, both found only by testing with real key events:

1. A focused `QTextEdit` can claim plain Return (and Ctrl+Return) for itself before the window-level `QShortcut` gets a chance, the same ShortcutOverride mechanism described above.
2. If more than one window in the process happens to have an active Ctrl+Return `QShortcut` at once, Qt's global shortcut map treats the key sequence as AMBIGUOUS and silently fires neither shortcut — no exception, no warning.

`_CtrlEnterApproveFilter` (installed directly on each editable text edit) closes both: it accepts `QEvent.ShortcutOverride` for Ctrl+Return so the key is claimed locally before it can ever reach the (possibly ambiguous) global map, then handles the resulting `QEvent.KeyPress` itself. Regression coverage: `test_ctrl_enter_still_approves_while_the_text_edit_has_real_keyboard_focus`, `test_space_shortcut_does_not_fire_...`, `test_bracket_shortcuts_do_not_fire_...`, `test_replay_shortcut_does_not_fire_...` — all real `QTest.keyClick` events, not signal emission.

## Review Priority

`compute_review_priority` (`src/glyphcue/application/review_priority.py`) takes a `ReviewSignals` bundle and returns a `ReviewPriority`: a plain 0..1 `score` and a coarse `level` (`"None"`/`"Low"`/`"Medium"`/`"High"`, DESIGN.md section 21's own accepted vocabulary), built from independently-explainable `components`, each with its own plain-language `explanation`.

**Monotonic aggregation (corrective).** The score is `min(1.0, sum(contribution for each active component))` — a capped sum, not an average. The original formula averaged component contributions, which is NOT monotonic: a Cue with only cross-frame disagreement (one component, contribution 1.0, score 1.0) would DROP to ~0.5 the moment a mild, below-threshold OCR-confidence reading was also detected, because averaging a strong signal with a weak one pulls the result down — i.e. adding evidence of a NEW problem could make a Cue look LESS worth reviewing, the opposite of what Review Priority is for. A capped sum of non-negative contributions cannot do this: each additional component can only add to the running total before the cap applies, so the score is monotonic non-decreasing in the number and strength of contributing signals by construction. Regression: `tests/application/test_review_priority.py`'s `test_adding_any_single_nonzero_signal_never_lowers_the_score`, `test_adding_a_weak_signal_on_top_of_a_strong_one_never_lowers_the_score`, and `test_score_is_monotonic_non_decreasing_across_every_added_signal_combination` (an exhaustive combinatorial sweep over every subset of the four wired signals).

Wired signals, each backed by real reconstruction diagnostics, not guessed:

- **OCR confidence** — mean confidence across the Cue's supporting Observations, only flagged below a 0.9 threshold (a routine sub-1.0 real OCR reading is not itself review-worthy; see the module's own docstring for why this threshold exists rather than penalizing every non-1.0 score).
- **Cross-frame disagreement** — M5's own `ConsensusDiagnostics.had_disagreement`.
- **Missing language layer** — M6's own `MultilingualDiagnostics.missing_languages` count.
- **Ambiguous language layer** — M6's own `MultilingualDiagnostics.ambiguous_languages` count (the geometry-only-fallback flag M6's second corrective pass added).

**Timing instability is not wired in this pass.** ROADMAP M7 lists it as one of several "such as" example signals, not a mandatory one, and no part of the current reconstruction pipeline computes a real, explainable timing-instability diagnostic to build a signal from. Wiring a fabricated stand-in just to check a box would violate the "no fake confidence" discipline this whole milestone is built around.

**A Cue with no applicable signal shows "No Review Flags" / `level="None"`, never a fabricated non-zero score.** Path B's `reconstruct_cues` currently produces no per-Cue diagnostics at all — every Path B Cue is therefore honestly `level="None"` today (`_no_priority_signal` in `path_b_workspace.py`).

## No fake confidence

`ReviewPriority.score` is never displayed as a percentage-of-correctness. The right pane shows `"Review Priority: {level} ({score:.2f})"` — DESIGN.md section 21's own accepted example format (`"Review Priority: 0.72"`) paired with the level word, never `"92% correct"` or similar. `diagnostics_view` lists each component's own plain-language explanation, so a reviewer can always see exactly why a Cue was ranked where it was — never a hidden weighting.

## QA interactions

All of ROADMAP M7's listed interactions are implemented as `cue_review_actions.py` pure functions (`approve_cue`, `discard_cue`, `edit_cue_language_text`, `nudge_cue_timing`, `split_cue`, `merge_cues`), each independently unit-tested (`tests/application/test_cue_review_actions.py`), then wired into `ReconstructionQaWorkspace`'s buttons/shortcuts:

- **Approve** — the QA pane's dominant action (DESIGN.md section 23), bound to both a button and `Ctrl+Enter`, with its own distinct dominant styling (see "Action hierarchy" below).
- **Split** — at a user-adjustable time (defaults to the Cue's own midpoint); both halves are marked `NEEDS_REVIEW`, and both halves keep every original Observation id.
- **Merge — temporal next, not queue next (corrective).** "Merge with Next" now merges the active Cue with the Cue that follows it in the underlying **timeline** (`_temporal_next_cue`, sorted by `start_time`), not the next row in the Review-Priority-ordered queue. The original implementation used `queue.currentRow() + 1`, which is the priority order — with even one Cue whose priority differs from strict chronological order, that silently merges two non-adjacent captions. Regression: `test_merge_with_next_merges_the_temporally_next_cue_even_when_priority_order_differs` (≥3 Cues, priority order deliberately ≠ time order).
- **Merge — reliable merged-Cue identification (corrective).** `merge_cues` now returns `(cues, merged_cue_id)` instead of just `cues`. The old caller-side code guessed the merged Cue as "the first Cue in the list whose id isn't one of the two old ids" — with a THIRD, unrelated Cue present, that guess can silently pick the wrong Cue entirely. Regression: `test_merge_cues_returns_the_merged_cues_own_id_reliably_among_other_cues`.
- **Merge — stable id dedup, not double-counted provenance (corrective).** Both halves of a Split keep every original `observation_id`; merging those two halves back together previously concatenated the id tuples verbatim, duplicating every id. `_deduplicated_ids` now unions them, order-preserving. Regression: `test_merge_cues_after_a_prior_split_does_not_duplicate_observation_ids`.
- **Merge — structural text separator, not an ASCII-space assumption (corrective).** Merged layer text is now joined with `"\n"`, not `" "`. A bare space silently assumes a Western word-boundary convention; a newline makes no assumption about any script's word boundaries (and mirrors the multi-layer export join) without attempting real CJK-aware boundary normalization, which stays out of scope for M8. Regression: `test_merge_cues_joins_text_with_a_structural_separator_not_an_ascii_space`.
- **Discard** — reuses `ReviewState.REJECTED` for review history, but is now enforced at the **export boundary** (see below).
- **Editable text / language layers** — `LanguageLayersPanel`'s `editable=True` mode renders a `QTextEdit` per layer.
- **Timing nudge** — Cue-level only (four buttons, ±0.1s each on start/end).
- **Previous / Next / Replay** — queue navigation and `PlaybackController.play_span` (Path A) via `[`, `]`, `R`. **Replay is disabled, not a fake affordance, when no `replay_callback` is wired (corrective)** — Path B has no playback controller at all; `replay_button`/`replay_shortcut` are both explicitly disabled rather than presenting a control that silently does nothing. Regression: `test_replay_capability_is_{disabled,enabled}_when_{no_,a_}replay_callback_is_wired`.
- **Evidence selection** — the curated/full evidence toggle (see below).

### Action hierarchy (corrective, DESIGN.md section 23)

Approve, Split/Merge, and Discard now carry distinct styling (`design_tokens.Color`-based, no new tokens introduced): Approve is filled, bold, `Color.SUCCESS` — the one dominant action. Split/Merge share identical, neutral secondary styling. Discard is `Color.DANGER`-colored but explicitly NOT given Approve's fill/weight/size, so its consequence is legible without ever matching Approve's prominence. This was previously unstyled (every QA button used the same default `QPushButton` look), which is a real DESIGN.md section 23 gap, not a cosmetic nice-to-have — the spec requires Approve to read as dominant and Discard to never share that prominence. Regression: `test_action_hierarchy_gives_approve_dominant_styling_and_discard_danger_styling`.

## Curated vs. full evidence

`select_curated_evidence` (`src/glyphcue/application/curated_evidence.py`) picks the DESIGN.md section 19-20 default subset — in-point, every observation that disagreed with the winning text, a representative middle sample when nothing disagreed, and the out-point. It only ever selects a subset; `show_full_evidence_checkbox` switches the QA pane's evidence view to the full list, so provenance is never actually lost.

**Per-language curated selection (corrective).** `_refresh_active_pane` now calls `select_curated_evidence` once PER language layer, against that layer's OWN `observation_ids` and OWN winning `text`, then unions and dedups the results across layers (sorted by `start_time`) for the combined evidence view. The original implementation ran curated selection ONCE for the whole Cue, comparing every layer's observations against only the FIRST (primary) layer's winning text — which meant a fully-correct `zh` layer's observations were flagged as "disagreement" purely because `zh` text naturally differs from the Cue's `en` text, inflating the evidence view with false positives on every multilingual Cue. Regression: `test_multilingual_curated_evidence_never_flags_a_correct_layer_as_disagreeing_with_another_language`.

## Discard / export contract (corrective)

`ReviewState.REJECTED` (Discard) is still kept internally as real review history — who rejected what stays visible in the QA session. But `Pysubs2SubtitleFormatAdapter.write` now explicitly excludes any `REJECTED` Cue from the exported SRT/VTT file. Discard's whole point is "do not ship this line"; before this fix, a discarded Cue's text still made it into the exported file, silently contradicting the review decision. Regression: `tests/adapters/test_pysubs2_subtitle_io.py::test_write_excludes_discarded_rejected_cues` and a full end-to-end Path B regression, `tests/ui/test_path_b_workspace.py::test_discarding_a_cue_then_exporting_excludes_it_from_the_output_file`.

## Evaluation: does Review Priority actually find errors? (rewritten)

The original evaluation (`benchmarks/review_priority/run_evaluation.py`) generated a ground-truth "is this Cue wrong" label FIRST, then generated evidence-quality parameters (confidence, disagreement) directly correlated with that label by construction — a label leak: the evaluation was partly measuring its own hand-tuned correlation, not the real ranking mechanism acting on a real reconstruction.

The rewritten methodology removes that leak entirely:

1. An independent ground-truth Cue text corpus is defined first — 200 purely random 24-letter synthetic strings, one per Cue, seeded only from the Cue's own index (deliberately NOT a shared sentence template; an earlier draft of this rewrite used one, and its shared literal prefix across every Cue risked the real reconstruction seam's own similarity-based state-run grouping merging different synthetic Cues into one run).
2. For each ground-truth Cue, 6 noisy Observations are generated: each reading is independently either a clean, exact capture of the ground truth or a corrupted one, with the ODDS of a clean reading set by a per-Cue `noise_level` drawn independently of any correctness label (no such label exists yet at this point).
3. ALL of those Observations are fed through the real, unmodified production reconstruction seam, `reconstruct_cues_with_consensus` — the exact function Path A's OCR pipeline calls — producing real reconstructed Cues and real `ConsensusDiagnostics`.
4. `is_error` is derived AFTER the fact, automatically, by comparing each reconstructed Cue's winning text against the ground truth for the Cue whose observations produced it — never hand-labeled.
5. Review Priority is computed from the SAME real diagnostics and real Observations the reconstruction run produced.
6. Ranking is compared against 20 independently seeded random-order baselines, averaged, rather than a single shuffle.

| Top fraction reviewed | Review Priority recall | Mean random baseline recall (20 seeds) | Beats random? |
|---|---|---|---|
| 10% | 7.5% | 9.75% | No |
| 20% | 20.0% | 19.75% | Yes |
| 30% | 30.0% | 31.75% | No |

`actual_error_rate` in this run: 18.8% (40/213 reconstructed Cues). Raw output: `benchmarks/review_priority/evaluation_results.json`.

**This is an honest negative/mixed result, reported as such, not tuned away.** Review Priority is roughly at parity with random review in this corrected, non-leaking scenario — a small edge at one cut, a small deficit at the other two, well within noise. The likely real reason (not a scoring-formula bug — the monotonic fix above is independently verified): with `_OBSERVATIONS_PER_CUE = 6` and exact-text-equality voting, `had_disagreement` fires almost any time there is ANY noise at all — a Cue with 5 clean readings and 1 corrupted outlier still trips `had_disagreement=True` even though the majority vote trivially recovers the correct text — so the boolean signal does not distinguish "harmless minority noise, correctly resisted by the vote" from "vote genuinely failed." The current `ReviewSignals` shape uses this coarse boolean rather than `ConsensusDiagnostics.agreement_ratio` (a real, already-computed but currently-unwired degree-of-agreement diagnostic) which would likely discriminate this scenario far better — but wiring a new signal into `compute_review_priority` is a scope change beyond this corrective pass's mandate (fix correctness bugs and the evaluation's methodology, not add new signals), so it is recorded here as a genuine, specific finding for a future pass, not acted on speculatively.

**Scope, stated precisely**: this evaluates the *ranking mechanism*, in a specific synthetic multi-reading-per-Cue scenario, against ground truth actually run through the real reconstruction seam — not a claim about real-world OCR/subtitle error rates. It is Path A/OCR-shaped (`ConsensusDiagnostics`-based) — Path B's evaluation is not attempted since Path B currently has no comparable diagnostics to rank by.

## Deliberately out of scope

Per ROADMAP M7 and DESIGN.md section 25 (`DEFERRED`): batch approval, advanced styling, comprehensive format repair, professional retiming, and Path B linked video are not attempted here. Durable cross-restart QA persistence remains a documented, minimal-migration follow-up. Wiring `agreement_ratio` (or any other new signal) into Review Priority, and M8 (Path B CJK / rolling normalization deepening), are both explicitly deferred, not started here.

## Acceptance gate closure

1. Path A and Path B both fit the frozen shell — one shared `ReconstructionQaWorkspace`, proven by both `tests/ui/test_path_a_media_pane_ocr.py` and `tests/ui/test_path_b_workspace.py` exercising the identical QA controls.
2. Evidence remains visible during QA — `evidence_view` is always present in the right pane.
3. Curated evidence is useful and full evidence remains accessible — `select_curated_evidence` (now correctly scoped per language layer) + `show_full_evidence_checkbox`.
4. Review Priority is explainable — every non-zero score has named `components` with plain-language `explanation`s, and the aggregation itself is a documented, tested, monotonic invariant, not an opaque or accidentally-unstable formula.
5. No fake confidence percentage appears — `"Review Priority: {level} ({score:.2f})"`, DESIGN.md's own accepted format, never a probability-styled percentage.
6. **Top-ranked cues capture more real errors than random review on benchmark data — honest mixed/negative result, not tuned away.** See Evaluation above: roughly at parity with random (beats it at one of three cuts measured), in a corrected, non-leaking methodology. This is reported as-is per ROADMAP M7's own instruction to record a negative result honestly rather than keep adjusting parameters until the numbers look better.
7. Keyboard review flow is usable — `Space` (play/pause), `Ctrl+Enter` (approve+advance), `R` (replay), `[`/`]` (previous/next), verified with real `QTest` keyboard events including the case where a language-layer text edit has focus, not just signal emission.
8. No full subtitle-editor scope has leaked in — no advanced styling, batch approval, or professional retiming; single shared implementation keeps this enforced structurally, not just by discipline.
