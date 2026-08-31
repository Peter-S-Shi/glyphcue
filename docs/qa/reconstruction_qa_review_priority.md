# Reconstruction QA & Review Priority — Milestone 7

This document answers ROADMAP.md section 14's explainability requirement: what the shared QA seam and Review Priority ranking are, why they're built this way, where they knowingly fall short, and what the evaluation shows.

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

## Review Priority

`compute_review_priority` (`src/glyphcue/application/review_priority.py`) takes a `ReviewSignals` bundle and returns a `ReviewPriority`: a plain 0..1 `score` (the average of independently-explainable `components`, each with its own plain-language `explanation`) and a coarse `level` (`"None"`/`"Low"`/`"Medium"`/`"High"`, DESIGN.md section 21's own accepted vocabulary).

Wired signals, each backed by real reconstruction diagnostics, not guessed:

- **OCR confidence** — mean confidence across the Cue's supporting Observations, only flagged below a 0.9 threshold (a routine sub-1.0 real OCR reading is not itself review-worthy; see the module's own docstring for why this threshold exists rather than penalizing every non-1.0 score).
- **Cross-frame disagreement** — M5's own `ConsensusDiagnostics.had_disagreement`.
- **Missing language layer** — M6's own `MultilingualDiagnostics.missing_languages` count.
- **Ambiguous language layer** — M6's own `MultilingualDiagnostics.ambiguous_languages` count (the geometry-only-fallback flag M6's second corrective pass added).

**Timing instability is not wired in this pass.** ROADMAP M7 lists it as one of several "such as" example signals, not a mandatory one, and no part of the current reconstruction pipeline computes a real, explainable timing-instability diagnostic to build a signal from (M5's boundary-confidence internals aren't exposed as a diagnostic field). Wiring a fabricated stand-in just to check a box would violate the "no fake confidence" discipline this whole milestone is built around. This is a genuine, documented gap, not a silent omission — a real future signal source (e.g. flagging Cues whose boundary fell back to the ~1ms instant-marker default) is a natural, minimal follow-up.

**A Cue with no applicable signal shows "No Review Flags" / `level="None"`, never a fabricated non-zero score.** Path B's `reconstruct_cues` currently produces no per-Cue diagnostics at all (no OCR confidence, no disagreement signal exists for imported subtitle files) — every Path B Cue is therefore honestly `level="None"` today (`_no_priority_signal` in `path_b_workspace.py`), not silently scored as if evidence existed. This is stated plainly in the UI (`"No Review Flags"`), not hidden.

## No fake confidence

`ReviewPriority.score` is never displayed as a percentage-of-correctness. The right pane shows `"Review Priority: {level} ({score:.2f})"` — DESIGN.md section 21's own accepted example format (`"Review Priority: 0.72"`) paired with the level word, never `"92% correct"` or similar. `diagnostics_view` lists each component's own plain-language explanation, so a reviewer can always see exactly why a Cue was ranked where it was — never a hidden weighting.

## QA interactions

All of ROADMAP M7's listed interactions are implemented as `cue_review_actions.py` pure functions (`approve_cue`, `discard_cue`, `edit_cue_language_text`, `nudge_cue_timing`, `split_cue`, `merge_cues`), each independently unit-tested (`tests/application/test_cue_review_actions.py`), then wired into `ReconstructionQaWorkspace`'s buttons/shortcuts:

- **Approve** — the QA pane's dominant action (DESIGN.md section 23), bound to both a button and `Ctrl+Enter`.
- **Split** — at a user-adjustable time (defaults to the Cue's own midpoint); both halves are marked `NEEDS_REVIEW` (reusing the existing `ReviewState` enum, no schema change) since a machine split is not itself a correct reconstruction, and both halves keep every original Observation id (there is no real evidence for which half each region belongs to without human input).
- **Merge** — combines the active Cue with the next queue entry; matching-language layers concatenate text and union `observation_ids`; a language present in only one side is kept as real evidence, not treated as missing.
- **Discard** — reuses `ReviewState.REJECTED`.
- **Editable text / language layers** — `LanguageLayersPanel`'s new `editable=True` mode (extended from M6's read-only cards, not a new widget) renders a `QTextEdit` per layer; edits apply on Approve, mirroring the pre-M7 `PathBWorkspace` pattern exactly.
- **Timing nudge** — Cue-level only (four buttons, ±0.1s each on start/end); Language Layers still have no timing fields of their own (ROADMAP section 4, unchanged, checked directly against `Cue`'s own `__post_init__` invariants rather than re-deriving validation).
- **Previous / Next / Replay** — queue navigation and `PlaybackController.play_span` (Path A) via `[`, `]`, `R`.
- **Evidence selection** — the curated/full evidence toggle (see below).

## Curated vs. full evidence

`select_curated_evidence` (`src/glyphcue/application/curated_evidence.py`) picks the DESIGN.md section 19-20 default subset — in-point, every observation that disagreed with the winning text, a representative middle sample when nothing disagreed, and the out-point — never just "the first four observations." It only ever selects a subset; the full observation list is always the same list `select_curated_evidence` was given, and `show_full_evidence_checkbox` switches the QA pane's evidence view between the two, so provenance is never actually lost, only defaulted to a smaller, more relevant view (ROADMAP M7 acceptance gate 3).

## Evaluation: does Review Priority actually find errors?

`benchmarks/review_priority/run_evaluation.py` — a synthetic, constructed evaluation (no scraped video/subtitle/transcript data). 200 synthetic Cues, each independently assigned a ground-truth "this reconstruction is actually wrong" label (~25% wrong), with evidence quality (OCR confidence, disagreement) generated with a deliberate but IMPERFECT correlation to that label — errors are more likely, not certain, to come with degraded evidence, mirroring the real claim under test. The real, unmodified `compute_review_priority` + `review_signals_from_consensus_diagnostics` rank the synthetic Cues; nothing about the ranking logic is benchmark-specific.

| Top fraction reviewed | Review Priority recall | Random baseline recall |
|---|---|---|
| 10% | 32.7% | 6.1% |
| 20% | 59.2% | 16.3% |
| 30% | 83.7% | 22.4% |

Review Priority beat random review at every cut measured. Raw output: `benchmarks/review_priority/evaluation_results.json`. The script computes and reports a `negative_result` flag honestly — if ranking had NOT beaten random at some cut, that would be printed and recorded as-is, not tuned away until the numbers looked better (the script contains no free parameters fit against this specific outcome).

**Scope, stated precisely**: this evaluates the *ranking mechanism* against a constructed correlation between evidence quality and correctness, not a claim about real-world OCR/subtitle error rates or the true strength of that correlation in real target material. It is also Path A/OCR-shaped (`ConsensusDiagnostics`-based) — Path B's evaluation is not attempted here since Path B currently has no comparable diagnostics to rank by (see "Review Priority" above).

## Deliberately out of scope

Per ROADMAP M7 and DESIGN.md section 25 (`DEFERRED`): batch approval, advanced styling, comprehensive format repair, professional retiming, and Path B linked video are not attempted here. Durable cross-restart QA persistence is a documented, minimal-migration follow-up, not attempted speculatively (see above). M8 (Path B CJK / rolling normalization deepening) is not started.

## Acceptance gate closure

1. Path A and Path B both fit the frozen shell — one shared `ReconstructionQaWorkspace`, proven by both `tests/ui/test_path_a_media_pane_ocr.py` and `tests/ui/test_path_b_workspace.py` exercising the identical QA controls.
2. Evidence remains visible during QA — `evidence_view` is always present in the right pane.
3. Curated evidence is useful and full evidence remains accessible — `select_curated_evidence` + `show_full_evidence_checkbox`.
4. Review Priority is explainable — every non-zero score has named `components` with plain-language `explanation`s.
5. No fake confidence percentage appears — `"Review Priority: {level} ({score:.2f})"`, DESIGN.md's own accepted format, never a probability-styled percentage.
6. Top-ranked cues capture more real errors than random review on benchmark data — see Evaluation above (32.7% vs 6.1% at top-10%).
7. Keyboard review flow is usable — `Space` (play/pause), `Ctrl+Enter` (approve+advance), `R` (replay), `[`/`]` (previous/next), all real `QShortcut`s on the shared workspace, identical across both paths.
8. No full subtitle-editor scope has leaked in — no advanced styling, batch approval, or professional retiming; single shared implementation keeps this enforced structurally, not just by discipline.
