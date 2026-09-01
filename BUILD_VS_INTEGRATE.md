# Build vs. Integrate

Required by ROADMAP.md §17. Written as the minimum precursor
`FAILURE_MODE_REPORT.md` needs to classify each failure mode correctly:
a failure rooted in an integrated mature dependency (PaddleOCR, Qt,
pysubs2, PyAV) is a different kind of finding than a failure in
GlyphCue's own orchestration glue, and both differ again from a failure
in GlyphCue's own custom reconstruction/ranking algorithms. This table
states, for each real capability actually shipped, which of those three
buckets it falls in and what real evidence backs that split — it does
not re-derive anything not already established by an existing ADR or
milestone doc; it only assembles the split explicitly.

| Capability | Mature dependency (integrated as-is) | GlyphCue orchestration (glue code that invokes/schedules the dependency) | GlyphCue custom contribution (novel algorithm/logic, not from the dependency) | Evidence / rationale |
|---|---|---|---|---|
| OCR text recognition | **PaddleOCR** (`paddleocr==3.7.0` / `paddlepaddle==3.3.1`, pinned) — does all actual character recognition | `build_ocr_evidence_job` / `build_multilingual_ocr_evidence_job` invoke it once per triggered frame (per language, for multilingual); `PaddleOcrEngine` normalizes vendor exceptions/types behind the frozen `OcrEngine` Protocol and works around a real `enable_mkldnn=True` crash on this CPU | Canonical `en`/`zh`/`ja` language-code mapping (PaddleOCR's own `ch`/`japan` vendor codes never cross the boundary) | `docs/adr/0001-ocr-runtime-selection.md`, `src/glyphcue/adapters/paddleocr_engine.py`, `tests/adapters/test_boundaries.py` |
| Media decode / frame access | **PyAV** — container demuxing and frame decode | `PyAvMediaFrameSource` wraps frame iteration and timestamp mapping into GlyphCue's own media-source boundary; ROI cropping applied to decoded frames | None — decode itself is not reimplemented | `docs/adr/0004-media-architecture.md` |
| App threading / background work | **PySide6 (Qt)** — `QObject`, `Signal`, thread primitives | `Job`/`JobContext` (`src/glyphcue/jobs/job.py`) is GlyphCue's own cooperative-cancellation contract built on top of Qt signals + a Python `threading.Thread` — Qt itself has no built-in "cancel a background job cleanly" abstraction at this level | The cancellation *contract* itself (`request_cancel()` + `is_cancel_requested()` + terminal-state guarantee) is GlyphCue's own design, not a Qt pattern reused verbatim | `src/glyphcue/jobs/job.py`; hardened further in `benchmarks/_job_harness.py` after the incident in `docs/m10_private_corpus_incident.md` |
| Subtitle file I/O | **pysubs2** — SRT/VTT parsing and serialization | `Pysubs2SubtitleFormatAdapter` wraps it with GlyphCue's own atomic write (temp-file-then-rename), source-overwrite refusal, `REJECTED`-Cue export exclusion, and a per-event defensive `try`/`except` so one malformed entry doesn't discard an entire file | The per-event recovery/warning contract (`ImportWarning(source_index, reason)`) is GlyphCue's own addition on top of pysubs2's own parse | `docs/qa/path_b_cjk_rolling_normalization.md` ("Malformed/recoverable import") |
| Frame-difference change detection | None — a commodity mean-absolute-pixel-difference technique, not a library | `ChangeTriggeredOcrPolicy` decides, per frame, whether to spend an OCR call | The entire gating strategy (first-frame / change-detected / periodic-confirmation triggers) is GlyphCue's own, evaluated against a naive dense-OCR control baseline it also owns | `docs/adr/0002-selective-ocr-strategy.md` |
| Multi-frame consensus / state-run grouping | None | N/A | `group_into_state_runs` + majority-vote `consensus_value` (M5) — fully custom | `docs/adr/0003-consensus-reconstruction-approach.md` |
| Multilingual layer separation | None (Unicode script-range checks are hand-rolled, not a language-ID library) | `build_multilingual_ocr_evidence_job` schedules one OCR engine per configured language per triggered frame | `assign_observations_to_languages`'s fixed-point cluster/classify/eliminate algorithm (M6) — fully custom, and the one place a first design (trust the engine's own language tag) was tried and evidence-falsified before the current script-detection-first design was adopted | `docs/multilingual/track_group_reconstruction.md` |
| Path B rolling/CJK caption normalization | None | N/A | `_classify_transition`'s temporal-eligibility state machine (M8) — fully custom | `docs/qa/path_b_cjk_rolling_normalization.md` |
| Review Priority ranking | None | N/A | `compute_review_priority`'s monotonic capped-sum aggregation over named, explainable signals (M7) — fully custom | `docs/qa/reconstruction_qa_review_priority.md` |

## What this table is for in `FAILURE_MODE_REPORT.md`

Using the split above, that report's failure categories map as:

- A finding rooted in a **mature dependency** cell (PaddleOCR's own per-call latency, a PaddleOCR/CPU compatibility crash, pysubs2's own parse limits) is a **dependency/runtime limitation** — not something GlyphCue's own logic can fix by itself.
- A finding rooted in a **GlyphCue orchestration** cell (a job-cancellation bug, an OCR-trigger threshold that wasn't calibrated against real material) is a **GlyphCue orchestration limitation** — GlyphCue's own glue code, fixable without touching the dependency or the custom algorithm.
- A finding rooted in a **GlyphCue custom contribution** cell (Review Priority's weak signal on one failure class, Path B's designed-conservative non-merge behavior) is a **GlyphCue reconstruction/ranking limitation** — GlyphCue's own algorithm, evaluated against its own stated evidence.
- Anything that isn't in this table at all because it lives in a `benchmarks/` script rather than shipped product code is an **evaluation-harness failure**, a separate axis from all three rows above.
