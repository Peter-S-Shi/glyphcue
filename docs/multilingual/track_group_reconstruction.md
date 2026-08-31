# Multilingual Track Group Reconstruction — Milestone 6

This document answers ROADMAP.md section 13's explainability requirement for the layer-separation method: what the algorithm is, why it changed mid-implementation based on real evidence, where it fails, and what the real-PaddleOCR verification shows.

## What the algorithm is

`reconstruct_multilingual_cues_for_track_group` (`src/glyphcue/application/multilingual_reconstruction.py`) reconstructs a Track Group's real per-region OCR Observations into Cues whose `language_layers` follow `TrackGroup.languages`' own configured order.

A single-language Track Group is a direct call to M5's `reconstruct_cues_with_consensus` — not a reimplementation, the actual function — so M5's behavior and regression suite are unaffected by M6 existing at all.

A multi-language Track Group:

0. Reorders each frame's raw regions into a stable, language-based canonical order (`_canonicalize_frame_order`) before M5's same-frame aggregation runs, using the same layer-separation logic as step 3 below. Without this, two frames of the identical stable subtitle could have OCR return their regions in a different order and join into differently-ordered joined strings that M5's state-run grouping would wrongly read as two different states (`test_layer_order_is_stable_across_frames_even_when_detection_order_varies`).
1. Reuses M5's `group_into_state_runs` UNCHANGED to decide *when* state boundaries happen. One physical video frame is one OCR-triggering event regardless of how many languages are read from it, so every language layer sees identical `state_trigger` evidence and trigger cadence for a given frame — this is what lets M6 reuse M5's grouping instead of re-deriving boundary logic per language.
2. For each run, recovers the real, un-joined per-region Observations (via `member_observation_ids`, never M5's joined string) and splits them into one bucket per expected language (`assign_observations_to_languages`, see below).
3. Each bucket gets its own majority-vote text (`consensus_value`, the same tie-break-by-confidence mechanism M5 already uses) — so multi-region same-frame aggregation still happens, just per language instead of across all of them at once.
4. Cue timing (`resolve_cue_timing`, shared with M5) comes from the same run boundary every language layer of that Cue shares — no per-layer timing exists at all (ROADMAP section 4, frozen).

## The layer-separation algorithm (`assign_observations_to_languages`)

1. **Cluster by visual line**: same-frame regions whose vertical geometry overlaps are grouped together — this is what collapses multiple engines' independent readings of the identical physical line into one classification decision (see "Evidence hygiene" below for why this matters).
2. **Classify each cluster**: script detection (Han / Kana / Latin Unicode ranges) over the cluster's own text is the primary signal. The engine's `Observation.language` hint is used only to break a genuine script-level tie (Han alone can't distinguish Chinese from Japanese).
3. **Reading order / vertical layout**: any cluster that still can't be classified, and any expected language with no cluster at all, are paired off by geometry reading order against `TrackGroup.languages`' own configured order.
4. A cluster that classifies to an already-claimed language just adds to that language's bucket (a genuine two-line same-language caption, or a duplicate reading); anything left over is folded into the geometrically nearest already-assigned bucket.

Layer order in every reconstructed Cue is always `TrackGroup.languages`' own configured order, never whatever order OCR happened to detect regions in for a given frame — ordering stability is structural, not a separate rule to get right.

## Evidence hygiene: why the signal priority changed mid-implementation

The first implementation trusted `Observation.language` (the OCR engine's own reported language) as the PRIMARY signal, falling back to script detection only when the hint was missing. A targeted real-PaddleOCR verification (`benchmarks/multilingual_reconstruction/`, not a repeat of M5's noise/consensus benchmark — see "Evaluation" below) immediately falsified that assumption:

**Real finding**: every `PaddleOcrEngine` instance, regardless of which language it was configured/constructed for, detects and correctly transcribes EVERY text region in the cropped ROI — not just the one it was configured to recognize. `Observation.language` reflects which configured engine INSTANCE produced a given reading, not evidence about what language that specific region actually contains. Running a bilingual (English + Chinese) block through both an `en`-configured and a `zh`-configured engine produced 4 real observations: both engines correctly read BOTH lines, each tagging all of its own output with its own configured language regardless of the line's real content.

Trusting the hint as primary signal meant a majority-vote tie between the real English reading (correctly tagged "en") and the SAME engine's own correct-but-mistagged reading of the Chinese line (also tagged "en", since it came from the "en" engine) — and the tie broke on confidence, which had no reason to favor the semantically-correct one. The observed result: the "en" language layer sometimes won with the Chinese text.

**The fix**: script detection over the region's own actual text became the primary signal (the recovered text is real, readable evidence; which engine instance produced it is not), with the hint demoted to a tie-break for genuinely script-ambiguous cases (Han: Chinese or Japanese). A second real-evidence pass surfaced a further bug in a naive "claim once, no duplicates allowed" per-observation loop: with N engines each independently re-reading every physical line, N observations legitimately belong to the SAME language, and a single-claim assumption forced later, correctly-scripted duplicate readings into the wrong bucket once an earlier duplicate had already "claimed" that language slot. The final cluster-by-visual-line design (classify each *physical line*, once, from all of its readings together, rather than each *observation* independently) closes that gap structurally — clustering makes duplicate readings of one physical line agree with each other by construction, instead of relying on an unreliable "already claimed" heuristic across independent per-observation decisions.

This is exactly the kind of assumption ROADMAP section 13 asks to validate with benchmark evidence before committing to it, and the correction is transparently recorded here rather than silently rewritten.

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

## Failure modes / known limitations (recorded, not hidden)

- **Ambiguous script with no decisive hint and no geometry separation**: a cluster whose text is genuinely Han-only, whose engine hints don't clearly favor one candidate, and which has no distinguishing geometry from another cluster, falls through to the final nearest-geometry leftover merge — which is only as good as the geometry available. Not yet measured against a real target sample exhibiting this; no such case has been observed in the fixtures above.
- **Same-language multi-region captions**: a genuine two-line SAME-language subtitle inside a multilingual Track Group clusters as two separate visual lines, both classified to the same language, and both land in that language's bucket for majority voting — this does not currently rejoin them with a line break the way M5's own single-language same-frame aggregation does. Not measured against real material; a documented gap, not a silent one.
- **No claim about non-CJK/non-Latin scripts** (Cyrillic, Arabic, Devanagari, etc.): `_SCRIPT_CANDIDATE_LANGUAGES` only classifies Han/Kana/Latin, matching the `en`/`zh`/`ja` languages `PaddleOcrEngine` currently supports (ROADMAP section 13's V1 material profile). Extending script detection to more ranges is a follow-up, not attempted speculatively here.

## Why this baseline, and not something else

ROADMAP section 13 is explicit: "the implementation should use the simplest method that benchmark evidence supports." Geometry-first clustering plus script-detection classification is a deterministic, whiteboard-explainable pipeline — no ML language-ID model, no learned weights. The FIRST, simpler design (trust the hint) was tried first, per that same instruction, and was abandoned only once real evidence showed it was actually wrong, not preemptively over-engineered against a hypothetical failure. This mirrors M5's own "start simple, measure, only add complexity the evidence demands" discipline.

## Conclusion

Milestone 6 acceptance gates, closed:

1. Two-language target material reconstructs into separate language layers — real PaddleOCR evidence above, CER 0.0.
2. Three-language fixture does not break the model/UI — real PaddleOCR evidence above; `LanguageLayersPanel` renders N cards generically.
3. Timing is Cue-level — `resolve_cue_timing` shared with M5, no per-layer timing field exists.
4. Layer ordering is stable — structural (`TrackGroup.languages`' own order), proven across varying detection order (`test_layer_order_is_stable_across_frames_even_when_detection_order_varies`).
5. Missing/asymmetric layer behavior is explicit — empty `LanguageLayer` + `MultilingualDiagnostics.missing_languages`, no fabrication, no schema expansion.
6. Multilingual separation quality is evaluated — this document + `benchmarks/multilingual_reconstruction/`.
7. No bilingual-only hard-coding remains — `assign_observations_to_languages`/`reconstruct_multilingual_cues_for_track_group` are generic over `expected_languages: tuple[str, ...]`; proven directly with a four-language fixture (`test_four_language_track_group_has_no_bilingual_only_assumption`).
