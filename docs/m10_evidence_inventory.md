# Milestone 10 — Existing-Evidence Inventory (Reuse / Gap Map)

**Purpose:** a repo-level accounting of every M3–M9 benchmark, evaluation script,
result artifact, and ADR/decision doc against ROADMAP.md §17's M10 requirements
— what can be reused as-is, what needs extending, and what does not exist yet.
Written before any new M10 code or corpus so later work builds on a stable
contract instead of re-deriving this by re-reading six benchmark scripts again.

This document does not replace `EVALUATION_REPORT.md` — it is the working
input to it.

---

## 1. Evaluation corpus

| What ROADMAP §17 asks for | What exists | Verdict |
|---|---|---|
| 3–5 representative videos × 2–5 min segments | None. All M3–M9 evidence uses synthetic, hand-authored, or generated fixtures (rendered text images, synthetic corrupted strings, hand-built `Observation` lists) — never a real video. | **Gap.** No representative-video corpus exists at all. This is the largest true gap and the reason the user wants a corpus manifest / ground-truth schema built before any metrics work. |
| Path B fixtures | `benchmarks/path_b_normalization` (17 hand-authored cases, en + CJK), `tests/application/test_path_b_diagnostics.py` (superset source) | **Reuse.** Already a real, versioned, hand-authored fixture corpus with independent ground truth. Needs a corpus-manifest entry, not new fixtures. |
| Public demo-safe material | None identified yet. | **Gap.** |

---

## 2. Text metrics (CER / WER)

| Seam | Existing artifact | Reuse verdict |
|---|---|---|
| CER | `benchmarks/ocr_runtime_selection/cer.py` (`character_error_rate` — Levenshtein / len(reference)). Reused directly (via `sys.path`/module import, not a shared package) by `benchmarks/multi_frame_consensus/run_evaluation.py` and `benchmarks/multilingual_reconstruction/run_evaluation.py`. | **Reuse the algorithm, fix the packaging.** Three separate scripts already import the *same* function through fragile `sys.path.insert` / relative-import tricks instead of a real shared module. This is exactly the duplication risk the M10 prompt warns against — not a new implementation, but it should be promoted into one importable location (decision deferred to the corpus/metrics seam discussion, not decided in this inventory). |
| WER | Nowhere. | **Gap.** No WER implementation exists anywhere in the repo. |

---

## 3. Cue recovery (precision / recall)

| Seam | Existing artifact | Verdict |
|---|---|---|
| Path A OCR→Cue recovery precision/recall | None. `multi_frame_consensus` evaluation measures CER of the winning text, not whether the right *number* of Cues were recovered (missed/spurious Cues). `selective_ocr_pipeline` verification reports `observations_created` counts but does not score them against ground-truth Cue boundaries as precision/recall. | **Gap.** No Cue-level precision/recall exists anywhere in the repo for either path. |
| Path B Cue recovery | `benchmarks/path_b_normalization` reports pass/fail per case (`expected_texts` exact match), which is a correctness check, not precision/recall over a corpus with missed/spurious Cues. | **Partial reuse.** The fixture corpus and hand ground truth are reusable; the pass/fail scoring is not the precision/recall ROADMAP §17 asks for and would need a real metric layered on top. |

---

## 4. Timing (start / end error)

| Seam | Existing artifact | Verdict |
|---|---|---|
| Path A | None measured anywhere. | **Gap.** |
| Path B | `benchmarks/path_b_normalization`'s `Case.expected_spans` mechanism checks *exact* span equality for a handful of cases (pass/fail), not a continuous start/end error metric. | **Partial reuse.** Same underlying fixture/expected-span data could feed a real timing-error metric instead of exact-match pass/fail, without re-authoring cases. |

---

## 5. Multilingual (layer separation / missing-wrong assignment)

| Seam | Existing artifact | Verdict |
|---|---|---|
| Per-language CER after separation | `benchmarks/multilingual_reconstruction/run_evaluation.py` + `evaluation_results.json` — real PaddleOCR, real `assign_observations_to_languages` / `reconstruct_multilingual_cues_for_track_group`, per-language CER, `missing_languages` already recorded per block. | **Reuse.** This already produces most of what §17 asks for (layer separation quality, missing-language detection) on a small block corpus. |
| Missing / wrong layer assignment as an explicit metric (rate, not just a list) | `missing_languages` is recorded per block but never aggregated into a rate/summary across the corpus, and there is no "wrong assignment" (language A's text ending up tagged as language B) metric at all. | **Gap (extension, not a rewrite).** Needs aggregation + a wrong-assignment metric added on top of the existing per-block data. |

---

## 6. Path B (duplicate-removal / segmentation / timing normalization)

| Seam | Existing artifact | Verdict |
|---|---|---|
| Duplicate-removal (`repetition_collapsed`), segmentation (`rolling_growth`/`sliding_overlap`/`segmentation_ambiguous`), timing normalization (`expected_spans`) | `benchmarks/path_b_normalization` — 17 cases, categorized (`clean_preservation`, `rolling_reconstruction`, `over_merge_guard`, `out_of_order_safe`, `malformed_recoverable_import`), diagnostic-flag assertions, some span assertions. | **Reuse the corpus and categories; the correctness measure is pass/fail, not the independent per-seam metrics §17 names.** The explicit self-declared scope note in the script says this "is the same hand-authored... fixture matrix the implementation was built against via TDD... not a held-out validation set" — that honesty note should carry into `EVALUATION_REPORT.md` verbatim in spirit, not be silently dropped. |

---

## 7. Performance

| Metric | Existing artifact | Verdict |
|---|---|---|
| Processing speed, frames analyzed/sec, OCR calls/minute | `benchmarks/selective_ocr_pipeline/verification_results.json` (`PipelineMetrics`: `frames_analyzed`, `ocr_calls`, `elapsed_seconds`, `ocr_calls_per_minute`, `effective_processing_speed`) — real `build_ocr_evidence_job`, both selective and dense-baseline runs. | **Reuse directly.** This already is a real, comparative (selective vs. `NaiveDenseOcrPolicy` dense baseline) performance measurement on a real fixture video, exactly the kind of "baseline that already exists in the architecture" §17 prefers. |
| CPU / memory | `benchmarks/ocr_runtime_selection/benchmark_results.json` (`memory_baseline_mb`, `memory_after_load_mb`, `max_observed_rss_mb`, `startup_seconds`) — but scoped to engine load/per-item OCR calls only, not a full Path A pipeline run end-to-end. | **Partial reuse.** Real, honestly-caveated (see the script's own docstring about `max_observed_rss_mb` not being a true peak) memory/CPU numbers exist for the OCR engine layer only. No end-to-end pipeline CPU/memory measurement exists yet — that is a gap if a real video corpus is added in M10. |
| Package/runtime cost | `docs/adr/0001-ocr-runtime-selection.md` mentions packaging friction (e.g. the `enable_mkldnn=False` PaddlePaddle workaround) narratively. | **Partial reuse (narrative only).** No measured package-size/runtime-cost number exists anywhere. |

---

## 8. Review Priority (error-capture curve, top-N/top-percentile recall, random baseline, missed failure classes)

| Requirement | Existing artifact | Verdict |
|---|---|---|
| Error-capture curve, top-N/top-percentile recall, random-baseline comparison | `benchmarks/review_priority/run_evaluation.py` + `evaluation_results.json` — 200 synthetic Cues, real `reconstruct_cues_with_consensus` + `compute_review_priority`, 20-trial-averaged random baseline, top-10/20/30% recall, an explicit `negative_result` flag. | **Full reuse — this is already exactly what §17 requires**, including the honest negative result (`beats_random: false` at top-10% and top-30%). The M10 prompt explicitly forbids re-tuning this to look better; this evaluation should be re-run/possibly extended (larger N, more percentiles) but never adjusted toward a rosier outcome. |
| Missed failure classes | Not broken out. The script records *which* Cue IDs are wrong (`wrong_ids`) but never classifies *why* they went wrong (e.g. clustered around high noise level vs. grouping mistakes). | **Gap (extension).** Needs a failure-class breakdown layered onto the existing wrong/right split — same run, same data, new aggregation. |

---

## 9. ADR closure

| ROADMAP §17 topic | Current state | Verdict |
|---|---|---|
| OCR runtime | `docs/adr/0001-ocr-runtime-selection.md` — full ADR (context, chosen runtime, rejected alternatives, accepted costs, evidence). | **Done. No action.** |
| Selective OCR strategy | `docs/benchmarks/selective_ocr_pipeline.md` — has a "What this confirms (and doesn't)" section, but is filed as a benchmark write-up, not a decision record; no explicit "alternatives rejected" framing. | **Gap — needs a real ADR**, though the evidence to write it from already exists. |
| Consensus/reconstruction approach | `docs/consensus/multi_frame_consensus.md` — already has "Why this baseline, and not something else" and "Failure modes" sections, i.e. ADR-shaped content, just not filed as an ADR. | **Gap in filing, not in substance.** Needs to be captured as an ADR (can largely reference/summarize the existing doc rather than re-deriving it). |
| Multilingual timing simplification | ROADMAP.md §4 states the frozen domain decision (shared Cue-level timing, no per-language timing) but gives no ADR-style alternatives-considered/trade-off record. `docs/multilingual/track_group_reconstruction.md` covers the *layer-separation algorithm's* baseline choice, not this domain-simplification decision. | **Real gap.** No document anywhere explains why per-language independent timing was rejected for V1, beyond "representative material didn't need it." |
| Media architecture | ROADMAP.md §3 states the frozen choice (Qt Multimedia/QMediaPlayer for playback, PyAV for frame/timestamp access, bundled FFmpeg CLI via `QProcess` for heavy transforms) as a baseline list, with no rationale, alternatives, or trade-off discussion anywhere in the repo. | **Real gap.** No ADR and no supporting narrative doc exists for this decision at all. |
| Packaging path | Primary (`pyside6-deploy`/Nuitka) and fallback (PyInstaller) stated in ROADMAP.md §3; packaging itself is explicitly M12 scope, not yet implemented. | **Deferred, not a gap.** ROADMAP correctly scopes packaging acceptance to M12; M10 should record this as "deferred to M12," not attempt to write an ADR for a decision not yet exercised in practice. |

---

## 10. Summary — real M10 work implied by this inventory

Real gaps (net-new work), in the order the M10 prompt itself implies:

1. **Evaluation corpus manifest + ground-truth schema** — nothing like this exists; every prior benchmark invented its own ad hoc fixture format. *(User-confirmed next step.)*
2. **Representative-video corpus** (3–5 videos × 2–5 min) — does not exist; largest scope item, may need private-sample handling per ROADMAP's privacy allowance.
3. **Shared metrics module** (WER; Cue precision/recall; timing start/end error; multilingual missing/wrong-assignment rate; Review Priority failure-class breakdown) — some of this promotes/extends existing per-benchmark code (CER, span-exact-match, missing_languages), some is entirely new (WER, precision/recall, wrong-assignment rate).
4. **Two missing ADRs**: media architecture, multilingual timing simplification — write from scratch.
5. **Two ADRs promoted from existing narrative docs**: selective OCR strategy, consensus/reconstruction approach — largely a filing/summarizing exercise, not new analysis.
6. **`EVALUATION_REPORT.md`, `FAILURE_MODE_REPORT.md`, Build-vs-Integrate table** — new documents, but should assemble already-real evidence from this inventory rather than regenerate it.

## 11. Status update (this session)

- **Corpus manifest schema** — done: `src/glyphcue/evaluation/corpus.py` (`CorpusEntry`, `GroundTruthCue`, `CorpusVisibility`, `load_corpus_manifest`, `load_corpus`). Supports parsing, required-field/segment validation, and merging multiple manifests (a committed public one + a gitignored private one) with duplicate-id detection. Real video corpus content and public/private manifest file locations are not yet decided — schema only.
- **Shared metrics module** — done for the seams identified above: `src/glyphcue/evaluation/metrics.py` now has `character_error_rate` (canonical, tested), `word_error_rate` (new), `cue_recovery_precision_recall` (new), `timing_error` (new), `multilingual_layer_assignment_errors` (new, distinguishes a true miss from a wrong-layer assignment).
- **CER duplication cleanup (post-TDD refactor, reviewed separately from the red/green cycles above)** — done: `benchmarks/ocr_runtime_selection/cer.py` deleted; `multi_frame_consensus`, `multilingual_reconstruction`, and `ocr_runtime_selection/run_benchmark.py` now all import `character_error_rate` from `glyphcue.evaluation.metrics` instead of three separate `sys.path`/relative-import routes to the same duplicated formula. `docs/benchmarks/ocr_runtime_selection.md`, `docs/consensus/multi_frame_consensus.md`, and `src/glyphcue/application/text_similarity.py`'s docstring updated to point at the new canonical location instead of the deleted file.
- **Review Priority failure-class breakdown** — done (separate commit): `classify_review_priority_failure` + `recall_at_top_fraction` (new, tested), re-run against the unmodified M7 corpus/scoring. Real finding: the majority failure class (`low_confidence_and_other_signal`, 34/40) beats random at 2 of 3 top-fraction cuts; `low_confidence_only` (6/40) never beats random at any cut — reported honestly in `docs/qa/reconstruction_qa_review_priority.md`, not tuned away.
- **Path B independent duplicate-removal / segmentation / timing-normalization metrics** — done: each of the 17 existing hand-authored cases hand-tagged with which of ROADMAP.md section 17's three named Path B metrics it is real evidence for (`group_pass_fail_by_tag`, new and tested; reuses the already-tested `timing_error` for the continuous start/end error). Same corpus, same `reconstruct_cues_with_diagnostics`, no new cases, no algorithm change. Result: 2/2 duplicate-removal, 14/14 segmentation, 3/3 timing (0.0s error — expected on this exact-match hand-authored corpus, not a generalization claim). Regression-locked in `tests/application/test_path_b_normalization_evaluation.py`; documented in `docs/qa/path_b_cjk_rolling_normalization.md`.

Explicitly **not** gaps, i.e. do not re-run or re-derive for M10 without a stated reason:

- OCR runtime benchmark and ADR (§9 above) — complete.
- Selective-OCR-vs-dense-OCR performance baseline — complete, reusable as-is.
- Multi-frame-consensus-vs-single-frame baseline — complete, reusable as-is.
- Review Priority error-capture evaluation and its honest negative result — complete; extend (failure-class breakdown), never re-tune.
