# GlyphCue — Product Hardening II: Audit & Compact Risk Map

**Status:** Read-only hardening audit & execution roadmap. No product code changed.  
**Baseline:** `main` @ `a825cdbe3def54921376ca0f81535362a0f44c83` (includes merged PR #14 and PR #15).  
**Branch:** `hardening/product-hardening-ii`.  
**Lifecycle Context:** Milestone 12 is CLOSED & ACCEPTED (2026-09-05). Feature Freeze is REINSTATED. Packaging remains SUSPENDED until the Product Hardening II gate passes.  

---

## 1. Scope & Operating Discipline

Product Hardening II is a focused post-rework acceptance pass, **not** a repetition of Milestone 11's expansive discovery and **not** a new feature milestone.

### Closed Decisions & Non-Goals
1. **Cue Cleaner V0.6.1 Decision is Closed**: V0.6.1 is intentionally conservative; residual duplicates and fragments are an accepted V1 limitation per Human Adjudication (2026-09-05). The existing manual Merge workflow (`M` shortcut / Merge button) is the designated human resolution path. Zero-duplicate purity is explicitly **not** a release blocker.
2. **No Algorithmic Redesign**: No changes to Cue Cleaner V0.6.1, the DirectML OCR engine/detector, Paddle fallback, or upstream multi-frame consensus reconstruction.
3. **Packaging Suspended**: Packaging (PyInstaller onedir, Inno Setup) remains frozen until this hardening gate passes.
4. **Owner Testing Aggressively Minimized**: Everything that can be verified deterministically by the agent (automated unit/integration tests, simulated UI workflows, SQLite inspection, DirectML preflight probe) is assigned to the agent. Human testing is reserved solely for a single final smoke check before Milestone 13.

---

## 2. Audit of M12 Seam Interactions (PRs #14 & #15)

Milestone 12 introduced major UI and post-reconstruction quality changes across two vehicles:
- **PR #14 (Stage ①: UI / Review Workflow Recovery)**:
  - Multi-select and batch purge of discarded cues (`Purge Discarded`).
  - Strict chronological sorting `(start_time, end_time, id)` with review-state card border semantics (`SUCCESS` green, `BORDER_NEUTRAL_LIGHT` neutral, `WARNING` yellow, `DANGER` red, `ACCENT` blue for selection).
  - Outermost `QScrollArea` horizontal overflow wrapper (`_WORKBENCH_MIN_WIDTH = 1160px`).
  - `CompactTimeline` endpoint seam marker, click-to-seek, "Resume from Last End".
  - "Clear Video Cues…" destructive per-source cue reset modal.
  - Low-disturbance synthesized completion chime (`JobState.SUCCEEDED`).
- **PR #15 (Stage ②: Cue Production Quality Recovery)**:
  - Downstream Cue Cleaner V0.6.1 integrated via manual "Clean Cues" button.
  - Strict eligibility: `ReviewState.PENDING` only; human work (`APPROVED`, `REJECTED`, `NEEDS_REVIEW`) passes through 100% untouched.
  - Multilingual line attribution: verbatim donor subsequence matching with fail-closed safety on ambiguity or non-verbatim output.
  - Language-signature partitioning: isolating cues by ordered language configuration to prevent cross-run unioning.
  - Single-language edge-strip acceptance: single-language cues accept cleaner deduplications and trims directly.
  - Uncertainty surfacing: `preserve_complementary_evidence_cluster` mapped to `ReviewState.NEEDS_REVIEW`.
  - Atomic persistence via `save_cues_for_source` inside fail-closed try-except.
  - Cross-layer total ordering: repository queries and queue reconstruction enforce `(start_time, end_time, id)`.

---

## 3. Compact Risk Map Across Critical V1 Workflows

Each risk is classified into one of four mutually exclusive governance categories:
- **[ALREADY COVERED]**: Strongly verified by existing automated tests; no immediate gap.
- **[TARGETED REGRESSION]**: Automated test gap identified; to be closed in Step ② test batch.
- **[AGENT RUNTIME VERIFICATION]**: Requires live runtime execution by the agent on real hardware/scripts.
- **[HUMAN CONFIRMATION]**: Genuinely requires the repository owner's hands-on sensory check.

---

### Workflow A: Path A OCR → Reconstructed Cues → Clean Cues → QA/Edit/Merge/Discard → Persistence → All 4 Exports

| ID | Seam / Interaction Risk | Classification | Audit Finding & Rationale |
|:---|:---|:---:|:---|
| **A1** | **Clean Cues on Mixed-State Cue Sets** | `[ALREADY COVERED]` | `ReviewState.PENDING` cues are cleaned; `APPROVED`, `REJECTED`, and `NEEDS_REVIEW` cues pass through untouched with preserved IDs and states. Covered in `test_cue_cleaning.py` and `test_clean_cues_integration.py`. |
| **A2** | **Clean Cues Button State Transitions** | `[ALREADY COVERED]` | Fixed on branch: `_on_qa_cues_changed` triggers `_update_clean_cues_button_enabled`. Disables when all pending cues are reviewed or list is empty. Covered in `test_clean_cues_button_disables_when_cues_reviewed_via_qa`. |
| **A3** | **Post-Clean Manual Merge Workflow (`M`)** | `[TARGETED REGRESSION]` | When a residual duplicate persists after Clean Cues, user selects and merges via `M`. Merged cue gets `NEEDS_REVIEW` and persists immediately. Need targeted test asserting: Clean Cues → manual Merge → persist → second Clean Cues click → assert merged cue is untouched. |
| **A4** | **Post-Clean Split Workflow (`S`)** | `[TARGETED REGRESSION]` | User splits a cleaned cue into two halves. Both become `NEEDS_REVIEW` with new IDs. Need targeted test asserting: split halves sort chronologically, persist cleanly, and are ignored by subsequent Clean Cues. |
| **A5** | **Post-Clean Batch Purge Discarded** | `[ALREADY COVERED]` | Discard marks `REJECTED` (red border). `Purge Discarded` deletes rejected IDs from SQLite and updates queue. Tested in `test_m12_workflow_recovery.py`. |
| **A6** | **All Four Exports (SRT, VTT, TXT, MD)** | `[TARGETED REGRESSION]` | `ExportControls` provides SRT, VTT, Readable TXT, and AI-ready MD. All 4 formats must exclude `REJECTED` cues, include merged/edited/approved/pending cues in chronological order, and never overwrite source. Need unified regression asserting all 4 formats simultaneously on a cleaned + edited workspace. |
| **A7** | **Destructive Reset ("Clear Video Cues…")** | `[ALREADY COVERED]` | Confirmation dialog prompts user; deletes cues for `_source_id` only; preserves observations and other videos; resets queue and disables Clean Cues button. Covered in `test_m12_workflow_recovery.py`. |

---

### Workflow B: Path B Ingestion, Normalization, Review & Export

| ID | Seam / Interaction Risk | Classification | Audit Finding & Rationale |
|:---|:---|:---:|:---|
| **B1** | **Caption Normalization & Diagnostics** | `[ALREADY COVERED]` | Path B rolling growth, sliding overlap, repetition collapse, and 1:1 preserved states function correctly. Covered by 22 tests in `tests/ui/test_path_b_workspace.py`. |
| **B2** | **Card Border Semantics in Path B** | `[ALREADY COVERED]` | `CueQueueItemDelegate` renders borders based on `ReviewState` across both paths. Path B cues start as `PENDING` (neutral border) and transition to `APPROVED` (green) / `NEEDS_REVIEW` (yellow) cleanly. |
| **B3** | **Path B Export Integrity** | `[ALREADY COVERED]` | Path B shares `ExportControls` and `Pysubs2SubtitleFormatAdapter`; verified by automated tests. |

---

### Workflow C: In-Place Path Switching (Path A ↔ Path B)

| ID | Seam / Interaction Risk | Classification | Audit Finding & Rationale |
|:---|:---|:---:|:---|
| **C1** | **Edit Commitment on Mode Switch** | `[TARGETED REGRESSION]` | Switching modes calls `commit_pending_edits()` on both panes. Need targeted test verifying: user types an uncommitted edit in Path A, switches to Path B, switches back to Path A, and verifies edit was committed and persisted to SQLite without loss. |
| **C2** | **Media Viewport & Layout Seam Stability** | `[ALREADY COVERED]` | Stacked widget retains Path A media pane and Path B workspace in memory; splitter sizes (280/640/360) and outer scroll area preserve visual geometry across switches. |

---

### Workflow D: Failure, Cancellation & Data Integrity

| ID | Seam / Interaction Risk | Classification | Audit Finding & Rationale |
|:---|:---|:---:|:---|
| **D1** | **Clean Cues Fail-Closed Exception Handling** | `[ALREADY COVERED]` | `_on_clean_cues_clicked` wraps both `clean_eligible_cues_for_source` and `save_cues_for_source` in a fail-closed try block. Any error updates status label and leaves SQLite/workspace 100% untouched. |
| **D2** | **OCR Job Cancellation Safety** | `[ALREADY COVERED]` | Cancellation token checks at frame boundaries; try/finally ensures DB connection, media reader, and OCR engine are released on cancellation or error. |
| **D3** | **Non-Destructive Ingestion & Export Safety** | `[ALREADY COVERED]` | Export refuses destination == source (`ValueError`); writes to atomic sibling `.tmp` before renaming; raw observations remain immutable in SQLite. |

---

### Workflow E: Persistence Across Reopen & Total Ordering Invariants

| ID | Seam / Interaction Risk | Classification | Audit Finding & Rationale |
|:---|:---|:---:|:---|
| **E1** | **Cross-Session Reopen with Mixed Cues** | `[TARGETED REGRESSION]` | Reopening video in a fresh `PathAMediaPane` instance after Clean Cues, manual Merge, Discard, and Approval. Need targeted test asserting: exact total order `(start_time, end_time, id)` is preserved, all review states match, and Clean Cues button state is accurately reconstructed. |
| **E2** | **Incremental OCR Multi-Cycle Re-Clean** | `[TARGETED REGRESSION]` | User performs 0–10s OCR → Clean Cues → 10–20s OCR → Clean Cues → 20–30s OCR → Clean Cues. Need targeted regression verifying no ordering inversion, no loss of earlier cleaned cues, and correct total ordering throughout. |

---

### Workflow F: Performance-Sensitive Seams & Runtime Stability

| ID | Seam / Interaction Risk | Classification | Audit Finding & Rationale |
|:---|:---|:---:|:---|
| **F1** | **In-Memory Clean Cues Latency** | `[ALREADY COVERED]` | Cleaner V0.6.1 is pure Python in-memory string/interval processing. Executes in <0.05s on 100+ cues. Does not block UI thread perceptibly. |
| **F2** | **DirectML Engine & Detector Reachability** | `[AGENT RUNTIME VERIFICATION]` | Fail-closed verifier `tools/devqa_directml_verify.py` constructs real DirectML sessions and asserts `DmlExecutionProvider` is active. Can be executed directly by the agent on this Windows machine. |
| **F3** | **Audio Chime Reliability** | `[ALREADY COVERED]` | Low-disturbance synthesized wave chime runs via `winsound.PlaySound` in background thread with fail-soft exception handling. Covered in `test_audio_chime.py`. |

---

### Workflow G: Human Confirmation (Owner-Only)

| ID | Seam / Interaction Risk | Classification | Audit Finding & Rationale |
|:---|:---|:---:|:---|
| **G1** | **Pre-RC Single-Pass Sanity Click-Through** | `[HUMAN CONFIRMATION]` | A single 3-minute hands-on pass by the owner: open video → run 10s OCR → click Clean Cues → press `M` on a residual duplicate → export SRT. Only required immediately before Milestone 13 tagging. |

---

## 4. Immediate Blocker Analysis

**Result: Zero immediate blockers found.**
- All 957 automated tests across the repository pass cleanly on the base commit `a825cdb`.
- No architectural violations, data races, unhandled exception paths, or uncommitted regressions were found during code inspection.
- The two defensive improvements from PR #15 code review (button state update on QA cue changes, wrapping persistence in try-except) are present in the merged base.

---

## 5. Proposed Step ② Targeted Regression Batch

To close the identified `[TARGETED REGRESSION]` and `[AGENT RUNTIME VERIFICATION]` gaps with high ROI, Step ② will execute the following focused test additions:

### Proposed Test File: `tests/ui/test_product_hardening_ii_seams.py`

1. **Test 1: Full Post-Clean QA & Merge Lifecycle (Risks A3, A4)**
   - Create mock video with candidate raw cues containing a residual duplicate.
   - Trigger `Clean Cues` → assert duplicate survives (accepted limitation).
   - User triggers `merge_active_cue_with_next()` (`M`) → assert merged cue has `NEEDS_REVIEW`.
   - Trigger `Clean Cues` again → assert merged cue is untouched.
   - User triggers `split_active_cue()` (`S`) on another cue → assert both halves are `NEEDS_REVIEW` and untouched by Clean Cues.
2. **Test 2: Unified 4-Format Export Conformance (Risk A6)**
   - Take a workspace containing a mix of `APPROVED`, `PENDING`, `NEEDS_REVIEW` (merged/split), and `REJECTED` (discarded) cues.
   - Export to SRT, VTT, Readable Transcript (TXT), and AI-ready Transcript (MD).
   - Assert all 4 exports:
     - Exclude the `REJECTED` cue.
     - Include all other cues with exact text and valid ascending timestamps.
     - Preserve source file without mutation.
3. **Test 3: Mode Switching Uncommitted Edit Safety (Risk C1)**
   - In Path A, select a cue and edit language text in the QA widget without pressing enter/tab.
   - Switch to Path B (`switch_to_mode("path_b")`).
   - Switch back to Path A (`switch_to_mode("path_a")`).
   - Assert the edit was committed, the cue was saved to SQLite, and its state is `NEEDS_REVIEW`.
4. **Test 4: Clean Reload & Total Ordering Across Reopen (Risk E1)**
   - Build a populated SQLite database with cleaned, merged, approved, and discarded cues.
   - Construct a fresh `PathAMediaPane` and open the same source.
   - Assert loaded cues strictly match `(start_time, end_time, id)` order, review states match, and Clean Cues button is enabled if and only if pending cues remain.
5. **Test 5: Multi-Cycle Incremental OCR Re-Clean Sequence (Risk E2)**
   - Simulate sequential OCR additions: Range 1 [0–10s] → Clean Cues → Range 2 [10–20s] → Clean Cues → Range 3 [20–30s] → Clean Cues.
   - Assert no cue ordering regressions, no duplicate explosion, and total timeline continuity across all 3 cycles.

### Agent Runtime Verification Action
- Execute `tools/devqa_directml_verify.py` via python runner to confirm DirectML provider activation and hardware readiness on this platform.
