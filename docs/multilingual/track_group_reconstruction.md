# Multilingual Track Group Reconstruction — Milestone 6

This document answers ROADMAP.md section 13's explainability requirement for the layer-separation method: what the algorithm is, why it changed mid-implementation based on real evidence, where it fails, and what the real-PaddleOCR verification shows.

## What the algorithm is

`reconstruct_multilingual_cues_for_track_group` (`src/glyphcue/application/multilingual_reconstruction.py`) reconstructs a Track Group's real per-region OCR Observations into Cues whose `language_layers` follow `TrackGroup.languages`' own configured order.

A single-language Track Group is a direct call to M5's `reconstruct_cues_with_consensus` — not a reimplementation, the actual function — so M5's behavior and regression suite are unaffected by M6 existing at all.

A multi-language Track Group:

0. Reorders each frame's raw regions into a stable, language-based canonical order (`_canonicalize_frame_order`) before M5's same-frame aggregation runs, using the same layer-separation logic as step 3 below. Without this, two frames of the identical stable subtitle could have OCR return their regions in a different order and join into differently-ordered joined strings that M5's state-run grouping would wrongly read as two different states (`test_layer_order_is_stable_across_frames_even_when_detection_order_varies`).
1. Reuses M5's `group_into_state_runs` UNCHANGED to decide *when* state boundaries happen. One physical video frame is one OCR-triggering event regardless of how many languages are read from it, so every language layer sees identical `state_trigger` evidence and trigger cadence for a given frame — this is what lets M6 reuse M5's grouping instead of re-deriving boundary logic per language.
2. For each run, recovers the real, un-joined per-region Observations (via `member_observation_ids`, never M5's joined string) and splits them into one or more **visual-line clusters** per expected language (`assign_observations_to_languages`, see below) — a language's clusters are never flattened into one pool: each is a separate physical line.
3. Each cluster gets its own majority-vote text (`consensus_value`, the same tie-break-by-confidence mechanism M5 already uses — multiple engines'/frames' readings of the SAME physical line are what a cluster actually is), and a language's per-line texts are then joined top-to-bottom with a real `"\n"` — so a genuine two-line same-language caption keeps BOTH lines, not just whichever one happened to win a flat vote against the other.
4. Cue timing (`resolve_cue_timing`, shared with M5) comes from the same run boundary every language layer of that Cue shares — no per-layer timing exists at all (ROADMAP section 4, frozen).

## The layer-separation algorithm (`assign_observations_to_languages`)

1. **Cluster by visual line**: same-frame (and same-run, cross-frame) regions whose vertical geometry overlaps are grouped together — this is what collapses multiple engines'/frames' independent readings of the identical physical line into one classification decision, while keeping two genuinely different physical lines of the same language as two separate clusters (see "Evidence hygiene" below for why this matters, and for a second bug this same clustering closes).
2. **Classify every cluster together, as one fixed-point process** (`_classify_clusters`), not independently per cluster: script detection (Han / Kana / Latin Unicode ranges) over a cluster's own text is the primary signal. When a cluster's script is genuinely ambiguous (Han: Chinese or Japanese), it's resolved first by **elimination** — against languages some OTHER cluster in the same run has already decisively claimed (e.g. a Kana cluster claiming "ja" leaves a separate plain-Han cluster with only "zh" possible) — and only if that still doesn't narrow to one candidate, by an engine-hint vote that requires a **strict unique winner**. A genuine tie (1:1 or otherwise) is never silently broken by `Counter`/insertion order; it's left unresolved for step 3. Looping this to a fixed point (repeat until a pass makes no further progress) makes the whole result independent of what order the clusters happen to be processed in.
3. **Reading order / vertical layout** for whatever's still unresolved: any cluster that couldn't be classified, and any expected language with no cluster at all, are paired off by geometry reading order against `TrackGroup.languages`' own configured order. Every language that received a cluster this way — real geometry-only guessing, not decisive evidence — is recorded in the result's `ambiguous_languages` set, which `MultilingualDiagnostics.ambiguous_languages` surfaces per Cue (ROADMAP section 13: "if still no evidence, an explicit ambiguity/degraded diagnostic, not a guess").
4. A cluster that classifies to an already-claimed language just joins that language's existing cluster list (a genuine two-line same-language caption, or a duplicate reading of one line); anything left over after step 3 is folded into whichever already-assigned cluster is geometrically nearest to it.

Layer order in every reconstructed Cue is always `TrackGroup.languages`' own configured order, never whatever order OCR happened to detect regions in for a given frame — ordering stability is structural, not a separate rule to get right.

## Evidence hygiene: why the signal priority changed mid-implementation

The first implementation trusted `Observation.language` (the OCR engine's own reported language) as the PRIMARY signal, falling back to script detection only when the hint was missing. A targeted real-PaddleOCR verification (`benchmarks/multilingual_reconstruction/`, not a repeat of M5's noise/consensus benchmark — see "Evaluation" below) immediately falsified that assumption:

**Real finding**: every `PaddleOcrEngine` instance, regardless of which language it was configured/constructed for, detects and correctly transcribes EVERY text region in the cropped ROI — not just the one it was configured to recognize. `Observation.language` reflects which configured engine INSTANCE produced a given reading, not evidence about what language that specific region actually contains. Running a bilingual (English + Chinese) block through both an `en`-configured and a `zh`-configured engine produced 4 real observations: both engines correctly read BOTH lines, each tagging all of its own output with its own configured language regardless of the line's real content.

Trusting the hint as primary signal meant a majority-vote tie between the real English reading (correctly tagged "en") and the SAME engine's own correct-but-mistagged reading of the Chinese line (also tagged "en", since it came from the "en" engine) — and the tie broke on confidence, which had no reason to favor the semantically-correct one. The observed result: the "en" language layer sometimes won with the Chinese text.

**The fix**: script detection over the region's own actual text became the primary signal (the recovered text is real, readable evidence; which engine instance produced it is not), with the hint demoted to a tie-break for genuinely script-ambiguous cases (Han: Chinese or Japanese). A second real-evidence pass surfaced a further bug in a naive "claim once, no duplicates allowed" per-observation loop: with N engines each independently re-reading every physical line, N observations legitimately belong to the SAME language, and a single-claim assumption forced later, correctly-scripted duplicate readings into the wrong bucket once an earlier duplicate had already "claimed" that language slot. The cluster-by-visual-line design (classify each *physical line*, once, from all of its readings together, rather than each *observation* independently) closes that gap structurally — clustering makes duplicate readings of one physical line agree with each other by construction, instead of relying on an unreliable "already claimed" heuristic across independent per-observation decisions.

This is exactly the kind of assumption ROADMAP section 13 asks to validate with benchmark evidence before committing to it, and the correction is transparently recorded here rather than silently rewritten.

**A third pass, after the algorithm above shipped in this same PR, found and fixed two more real bugs** rather than waiting for a later corrective:

- **A hint-vote tie could still be silently decided.** The Han-ambiguous fallback used `Counter.most_common(1)[0][0]`, which breaks a tied vote by insertion/iteration order — not a real signal, just whichever tag the code happened to see first. Fixed by requiring a *strict* unique top-count winner (`_strict_hint_winner`); a genuine tie now falls through to the geometry fallback and is flagged `ambiguous_languages`, instead of quietly picking a winner nobody actually decided. Regression: `test_han_hint_tie_stays_unresolved_by_classification_not_broken_by_counter_order`, `test_han_tie_resolution_is_independent_of_engine_input_order` (same evidence, permuted input, must classify identically).
- **Elimination now uses real cross-cluster evidence, not just per-cluster guessing.** A Kana cluster's decisive "ja" claim is exactly the kind of fact that should make a separate, genuinely Han-ambiguous cluster in the same run resolve to "zh" by elimination, with no hint vote even needed. The single fixed-point classification pass (`_classify_clusters`) does this deterministically, order-independent by construction. Regression: `test_kana_cluster_claiming_ja_lets_a_plain_han_cluster_resolve_to_zh`.
- **Same-language multi-line captions were silently losing lines.** The original flat `dict[str, list[Observation]]` return threw away which physical line each observation came from, so a genuine two-line English caption inside a multilingual block got ONE flat majority vote across both lines' readings — one line won, the other was discarded, never appearing anywhere in the output. Fixed by changing the return shape to `dict[str, list[list[Observation]]]` (clusters, not a flat list) and voting + newline-joining per cluster at the caller (see "What the algorithm is" above). Regression: `test_two_english_lines_and_one_chinese_line_all_preserved_across_engines_and_frames` (2 English lines + 1 Chinese line, multiple engines, detection order varied across frames — the English layer must come back as `"line1\nline2"`, not one line silently dropped).

## Missing / asymmetric layers

Rare inconsistent source material — one language's OCR engine finding nothing at all in a run other languages have real text for — produces an explicit, empty-text `LanguageLayer` for that language plus a `MultilingualDiagnostics.missing_languages` entry naming it. No fabricated text, no schema expansion: the same `LanguageLayer.text` field V1 already has, just empty, with the diagnostic as the explicit signal (`test_missing_layer_in_one_run_produces_explicit_diagnostic_not_fabricated_text`, and the real M4-analogous end-to-end regression `test_asymmetric_evidence_produces_a_missing_layer_diagnostic`).

## Real evidence-production path

`build_multilingual_ocr_evidence_job` (`src/glyphcue/application/multilingual_ocr_evidence_job.py`) is M4's job architecture extended from one `OcrEngine` to one engine per Track Group-expected language — a single OCR engine instance only ever recognizes the one language it was configured for is untrue in the sense that it will still transcribe other scripts too (see above), but it must still be constructed once per language so a genuinely multilingual evidence stream exists in the first place. The OCR-invocation decision is made exactly once per frame, shared across every language's engine call for that frame — this is what lets M6 reuse M5's `group_into_state_runs` unchanged (every language layer sees identical trigger cadence and `state_trigger` reasons, since they're evidence about the same physical frame read multiple times). `metrics.ocr_calls` honestly counts real per-engine invocations (a triggered frame in a 2-language Track Group costs 2 OCR calls, not 1).

## Evaluation

**Deterministic unit-level proof** of the layer-separation and reconstruction mechanics (clustering, script-vs-hint priority, missing/asymmetric layers, stable ordering, N-language genericity, shared Cue timing): `tests/application/test_language_layer_assignment.py`, `tests/application/test_multilingual_reconstruction.py`.

**Real M4-analogous evidence-production proof** (scripted per-language engines, real synthetic video, real `build_multilingual_ocr_evidence_job` + `reconstruct_multilingual_cues_for_track_group`): `tests/application/test_multilingual_evidence_run_to_cue_end_to_end.py`.

**Targeted real-PaddleOCR verification** (`benchmarks/multilingual_reconstruction/`): copyright-safe, in-script-rendered bilingual (English + Chinese) and trilingual (English + Chinese + Japanese) blocks, each language's own real `PaddleOcrEngine` instance run against the identical image, results fed through the real production `assign_observations_to_languages` + `reconstruct_multilingual_cues_for_track_group`. After the evidence-driven fix above:

| Scenario | Language | Ground truth recovered exactly (CER 0.0) |
|---|---|---|
| bilingual (en+zh) | en | yes |
| bilingual (en+zh) | zh | yes |
| trilingual (en+zh+ja) | en | yes |
| trilingual (en+zh+ja) | zh | yes |
| trilingual (en+zh+ja) | ja | yes |

Raw output: `benchmarks/multilingual_reconstruction/evaluation_results.json`.

**Scope, stated precisely**: this benchmark verifies layer *separation* against real OCR detection/geometry/script behavior. It does not repeat M5's multi-frame noise/consensus degradation sweep (`benchmarks/multi_frame_consensus/`) — M6 does not change M5's consensus voting, so that evidence is unchanged and was not re-run. It also does not yet cover a real-video (not single-frame) multilingual scenario with real `ChangeTriggeredOcrPolicy` triggers — the scripted end-to-end test above covers that mechanism with synthetic (not real-OCR) content, the same split M5 used between its own scripted trigger-mechanism test and its real-OCR benchmark.

## Production Path A wiring

`PathAMediaPane` (`src/glyphcue/ui/path_a_media_pane.py`) accepts an optional `ocr_engine_factory: Callable[[str], OcrEngine]` alongside the existing single `ocr_engine`. When Run OCR Evidence is clicked, the CURRENT Track Group's own `languages` decide what actually runs:

- exactly one language: unchanged M4/M5 behavior — `build_ocr_evidence_job` with a single engine (the plain `ocr_engine` if given, else `ocr_engine_factory(language)`).
- more than one language: `build_multilingual_ocr_evidence_job` with one engine per language (`{language: ocr_engine_factory(language) for language in languages}`), and on success, `reconstruct_multilingual_cues_for_track_group`'s first reconstructed Cue is shown in `language_layers_panel` (a `LanguageLayersPanel`, DESIGN.md section 12's production 1…N layer presentation) right there on the same Path A surface.

This is deliberately the thinnest wiring that makes "configure N languages, run OCR, see N layers" actually reachable by a user — not a queue, not Approve/Split/Merge/Review Priority, none of which are in scope until Milestone 7. `create_path_a_app` wires `ocr_engine_factory=PaddleOcrEngine` for the real production entrypoint. Regression: `test_multilingual_track_group_uses_the_multi_engine_job_and_shows_layers` (proves the multi-engine job actually ran, not a single-engine one, and the layers actually appear) and `test_single_language_track_group_still_uses_the_single_engine_job` (proves a single-language Track Group is not silently routed through the multilingual path just because a factory happens to be available).

**The language configuration itself is now user-reachable**, not just constructible by a caller in code. `LanguageSelectionPanel` (`src/glyphcue/ui/language_selection_panel.py`) is a generic 1…N add/remove/select list — never hard-coded to "Language A"/"Language B" — constrained to `available_languages` (default: `PaddleOcrEngine.CANONICAL_LANGUAGES`, i.e. `en`/`zh`/`ja`, the only languages the real OCR runtime can actually be constructed for). `PathAMediaPane`'s old `_DEFAULT_LANGUAGE = "und"` placeholder — used whenever no Track Group had ever been saved — is gone: a freshly-created panel now always starts at a single legal canonical language, never a code no real engine could run with. Saving persists `TrackGroup(roi, languages)` together as one record; reconstructing the pane over the same repository restores both. Run OCR reads the picker's LIVE selection (the same "what you see is what runs" contract `current_roi()` already has), not a separate re-fetch from the repository. Regression: `test_user_configured_language_selection_persists_and_drives_the_real_multi_engine_run` — configures en→en+zh through the real widget (no test-code shortcut of seeding a multilingual `TrackGroup` straight into the repository), saves, constructs a SECOND, fresh pane instance over the same repository (a stand-in for reopening the app), and proves that second pane restores the (en, zh) selection and actually drives the real two-engine job.

**The final multilingual Cue's `end_time` now uses real processing-end evidence.** `reconstruct_multilingual_cues_for_track_group` already accepted an optional `processing_end_time` (mirroring M5's own frozen final-boundary contract — see `docs/consensus/multi_frame_consensus.md`), but the Path A wiring wasn't passing it, so a subtitle state that ran to the end of the whole-media processing range would fall back to the ~1ms OCR-instant-marker default. `PathAMediaPane` now resolves the SAME `ProcessingRange` instance the OCR job itself runs with (`self._processing_range`) against the real probed media duration before starting the job, and passes that resolved end as `processing_end_time=` once reconstruction runs — never re-derived from frame index/fps. Regression: `test_final_multilingual_cue_uses_the_real_processing_range_end_not_a_1ms_instant` (asserts the final Cue's `end_time` equals the real `probe_media(...).duration_seconds`, independently computed in the test, not a duplicated hardcoded assumption).

## Failure modes / known limitations (recorded, not hidden)

- **No claim about non-CJK/non-Latin scripts** (Cyrillic, Arabic, Devanagari, etc.): `_SCRIPT_CANDIDATE_LANGUAGES` only classifies Han/Kana/Latin, matching the `en`/`zh`/`ja` languages `PaddleOcrEngine` currently supports (ROADMAP section 13's V1 material profile). Extending script detection to more ranges is a follow-up, not attempted speculatively here.
- **A cluster that resolves to zero decisive/eliminated evidence at all** (no recognized script anywhere in it, no usable hint, and every expected language already claimed by something else) falls through to the nearest-geometry leftover merge, same as before — genuine geometry-only guessing, now at least always flagged via `ambiguous_languages` rather than looking as confident as a real classification. Not yet measured against a real target sample exhibiting this.

## Why this baseline, and not something else

ROADMAP section 13 is explicit: "the implementation should use the simplest method that benchmark evidence supports." Geometry-first clustering plus script-detection classification is a deterministic, whiteboard-explainable pipeline — no ML language-ID model, no learned weights. The FIRST, simpler design (trust the hint) was tried first, per that same instruction, and was abandoned only once real evidence showed it was actually wrong, not preemptively over-engineered against a hypothetical failure. This mirrors M5's own "start simple, measure, only add complexity the evidence demands" discipline.

## Conclusion

Milestone 6 acceptance gates, closed:

1. Two-language target material reconstructs into separate language layers — real PaddleOCR evidence above, CER 0.0.
2. Three-language fixture does not break the model/UI — real PaddleOCR evidence above; `LanguageLayersPanel` renders N cards generically.
3. Timing is Cue-level — `resolve_cue_timing` shared with M5, no per-layer timing field exists.
4. Layer ordering is stable — structural (`TrackGroup.languages`' own order), proven across varying detection order (`test_layer_order_is_stable_across_frames_even_when_detection_order_varies`).
5. Missing/asymmetric layer behavior is explicit — empty `LanguageLayer` + `MultilingualDiagnostics.missing_languages`/`ambiguous_languages`, no fabrication, no schema expansion, and no silent-tie guessing (see "Evidence hygiene").
6. Multilingual separation quality is evaluated — this document + `benchmarks/multilingual_reconstruction/`.
7. No bilingual-only hard-coding remains — `assign_observations_to_languages`/`reconstruct_multilingual_cues_for_track_group` are generic over `expected_languages: tuple[str, ...]`; proven directly with a four-language fixture (`test_four_language_track_group_has_no_bilingual_only_assumption`).

Also closed this pass: same-language multi-line captions are preserved intact (`test_two_english_lines_and_one_chinese_line_all_preserved_across_engines_and_frames`), and a real Path A surface reachably wires TrackGroup-configured N languages to the real multi-engine job and layer presentation ("Production Path A wiring" above).
