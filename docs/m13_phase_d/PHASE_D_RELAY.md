# GlyphCue — Phase D Relay Authority

**Document type:** Public Canonical Phase D Relay Document  
**Status:** D0 — Execution Preflight & Relay Scaffold COMPLETE. D1 — NOT STARTED.  
**Branch:** `milestone/13-release-candidate`  
**Phase C Closure Commit:** `00a3c65ccd7fca5180e94f242947c2438a0f9651`  
**D0 Scaffold Baseline Commit:** `182bc46788df66c95b272aa64193937ebed0fb4f`  
**Governing Issues:** [#26](https://github.com/Peter-S-Shi/glyphcue/issues/26), [#27](https://github.com/Peter-S-Shi/glyphcue/issues/27)  
**Date:** 2026-09-05  

---

## 1. Authority & Dynamic HEAD Resolution Rule

Phase C is **FINAL ACCEPTED**. Both independent clean reconstructions (Clean Reconstruction A and Clean Reconstruction B) produced identical pre-sign payloads with verified Authenticode signatures.

> [!IMPORTANT]
> **Dynamic HEAD Resolution Rule:**  
> Tracked repository documents (`PHASE_D_RELAY.md`, `phase_d_state.json`) record fixed historical baselines (`phase_c_closure_commit` = `00a3c65...` and `d0_scaffold_baseline_commit` = `182bc46...`) and do not store a static "current HEAD" to avoid self-referential commit churn.  
> Every executing relay agent **must** dynamically resolve the live branch HEAD at module execution start via `git rev-parse HEAD` and record that exact SHA into `build_artifacts/phase_d/relay_state.json` under `source_head`.

Any agent executing Phase D must:
1. Read this document in full before taking any action.
2. Read `docs/m13_phase_d/phase_d_state.json` to determine current module and status.
3. Read `build_artifacts/phase_d/relay_state.json` for live machine-local handoff state (local paths, PIDs, log locations, background processes, dynamically resolved `source_head`).
4. Check for any healthy running background tasks before starting new ones.
5. Confirm the selected installer SHA-256 before running any install.

---

## 2. Selected Phase D Installer (All Modules)

This is the **single canonical installer** for all Phase D testing. Do not substitute.

| Property | Value |
|---|---|
| **Filename** | `GlyphCue-Setup.exe` |
| **Source** | Clean Reconstruction A, Phase C Final Accepted |
| **Size (Bytes)** | `441,941,848` |
| **SHA-256 (Signed)** | `3ea8720033d7d23a5c55296bb2ee08fffb3bc43e2f6a4d9ad0387c63951355a3` |
| **Signer Subject** | `CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root` |
| **Signer Thumbprint** | `A3E4E5320779C9F63E513D870E209C26B819C61E` |
| **Authenticode Status** | `Valid` (verified) |

Before any Phase D installation, the executing agent **must** independently verify the installer SHA-256. If it does not match exactly, **stop immediately**.

---

## 3. Target Environment Roles

| Role | Requirements |
|---|---|
| **Environment A** | Clean Windows 11 x64 target with DirectML-capable hardware (D3D12 Feature Level 11_0+, compatible GPU). Network-blocked offline installation from the canonical signed installer. No prior GlyphCue installation. |
| **Environment B** | Clean Windows 11 x64 target where DirectML is definitively unavailable or disabled by design (no discrete GPU or GPU disabled), exercising the explicit CPU-only fallback path. Network-blocked offline installation from the canonical signed installer. No prior GlyphCue installation. |

> [!IMPORTANT]
> Evidence from different VM states, snapshots, or machines must **never** be silently combined as though it came from one continuous test environment. If environment continuity cannot be proven, the relevant module must be marked `NEEDS_REVIEW` — not `PASS`.

---

## 4. Phase D Module Definitions & Scope Boundaries

| Module | Name | Scope |
|---|---|---|
| **D0** | Execution Preflight & Relay Scaffold | Relay infrastructure, installer selection, environment role freeze, dynamic HEAD contract. No installation. ✅ COMPLETE |
| **D1** | Environment A — Clean Offline Install, First Launch & Relaunch | Install canonical installer on network-blocked Environment A, verify installer integrity, execute first launch, reboot system, and verify successful relaunch post-reboot. |
| **D2** | Environment A — DirectML Runtime Fidelity | On post-D1 Environment A: verify model SHA-256 identities and runtime/DLL integrity; verify `DmlExecutionProvider` is active on detector and recognizer ONNX sessions with explicit proof of no silent CPU fallback; run bounded runtime-functional OCR smoke on approved deterministic fixture (successful end-to-end execution, non-empty output). |
| **D3** | Environment B — CPU Fallback Validation | On Environment B: verify DirectML is absent/unavailable by design; verify identical model/runtime DLL integrity intact; verify `CPUExecutionProvider` active on detector and recognizer sessions; prove fallback is intentional rather than caused by corruption/missing DLLs; run bounded runtime-functional OCR smoke on CPU path. |
| **D4** | Evidence Reconciliation & Phase D Verdict | Collect evidence from D1–D3; compare against #26 charter acceptance criteria; produce final Phase D verdict. Per Issue #27, a Phase D PASS permits progression to Phase E only — it does NOT make GlyphCue Release Ready. |

> [!IMPORTANT]
> Scope Boundary Enforcement:
> - Phase D scope is strictly **offline installation, post-reboot relaunch, runtime provider verification, intentional fallback verification, and bounded functional OCR smoke testing**.
> - **Phase E** — Formal performance benchmarking, realtime ratio evaluation, and output-quality/CER evaluation belong exclusively to Phase E.
> - **Phase F** — Upgrade, repair, and uninstall lifecycle testing belong exclusively to Phase F.

---

## 5. Mandatory Relay Contract

Every agent stopping normally, hitting quota exhaustion, encountering a failure, or leaving a healthy background task must record the following in `build_artifacts/phase_d/relay_state.json` **before stopping**:

```json
{
  "module": "<D0|D1|D2|D3|D4>",
  "status": "<NOT_STARTED|RUNNING|PASS|FAIL|NEEDS_REVIEW|PAUSED_QUOTA>",
  "source_head": "<git commit SHA dynamically resolved via git rev-parse HEAD at module start>",
  "installer_sha256": "3ea8720033d7d23a5c55296bb2ee08fffb3bc43e2f6a4d9ad0387c63951355a3",
  "environment": "<Environment_A|Environment_B|N/A>",
  "completed_checks": ["<list of completed verification steps>"],
  "pending_checks": ["<list of remaining required steps>"],
  "evidence_location": "<repo-relative or absolute-local path to evidence>",
  "background_process": {
    "command": "<exact command string if a process is running>",
    "pid_or_task_id": "<PID or task ID>",
    "log_path": "<absolute local log path>",
    "observed_health": "<healthy|unknown|failing>",
    "expected_completion_artifact": "<path or description>"
  },
  "last_known_result": "<brief description or 'none'>",
  "exact_next_action": "<precise instruction for the next agent>",
  "next_agent_directive": "<continue|observe|diagnose|stop>"
}
```

> [!CAUTION]
> A healthy long-running process **must not be killed** merely because the owner asks for progress or agent quota is low.  
> The next agent **must inspect/attach/observe** the existing task before deciding to rerun it.  
> A module may only be marked `PASS` when its own evidence contract is complete.  
> Absolute machine paths, VM/snapshot IDs, private credentials, or local process details belong in `relay_state.json` only — **never** in this document or `phase_d_state.json`.

---

## 6. Strengthened Fail-Closed Evidence Contracts per Module

### D1 Evidence Contract (Environment A — Offline Install, First Launch & Post-Reboot Relaunch)
- [ ] Canonical installer SHA-256 verified pre-install (`3ea8720033d7d23a5c55296bb2ee08fffb3bc43e2f6a4d9ad0387c63951355a3`)
- [ ] Target machine network adapter disabled / outbound network traffic blocked (strict offline environment)
- [ ] Signed installer ran to completion without error
- [ ] First launch successful (UI renders, application initializes persistent SQLite database and applies schema migrations)
- [ ] Target system rebooted
- [ ] Relaunch post-reboot successful (UI renders cleanly, persistent state intact)
- [ ] Log and screenshot evidence recorded in `build_artifacts/phase_d/d1_env_a_install/`

### D2 Evidence Contract (Environment A — DirectML Runtime Fidelity)
- [ ] Exact model SHA-256 identities verified on disk inside installed payload tree:
  - `PP-OCRv6_det_medium.onnx` (`3ca2f33c3a936a282fb8d2e8aa8f9872e423528b17cebfca15fb38fb243bb2ff`)
  - `PP-OCRv6_rec_small.onnx` (`73d2a09ecff1cfca1c9a4bd69ca9069d2d0b5e821558bf2a3fa416b23bfa9900`)
  - `ch_ppocr_mobile_v2.0_cls_mobile.onnx` (`7c9fb2f87a87e382d6ce6df76e27b13480a4009e863375c3efefbfeb58fa05ef`)
- [ ] Relevant runtime/DLL identities verified (`onnxruntime` libraries, bundled `DirectML.dll`, required C++ runtime dependencies)
- [ ] `DmlExecutionProvider` confirmed active on both text detector and recognizer ONNX sessions (logged session provider array inspection)
- [ ] Explicit proof of NO silent CPU-only fallback on Environment A (provider array starts with `DmlExecutionProvider`)
- [ ] Bounded runtime-functional OCR smoke using approved deterministic/public-safe fixture executed end-to-end without crash
- [ ] OCR output confirmed non-empty and non-degenerate (functional execution check only; zero Phase E performance/quality benchmarking)
- [ ] Log and evidence recorded in `build_artifacts/phase_d/d2_env_a_directml/`

### D3 Evidence Contract (Environment B — CPU Fallback Validation)
- [ ] Canonical installer SHA-256 verified pre-install on Environment B
- [ ] Target machine network adapter disabled / offline installation confirmed
- [ ] DirectML confirmed absent or unavailable by design (hardware GPU disabled or unsupported D3D12 environment)
- [ ] Authoritative model SHA-256 identities and runtime/DLL integrity verified intact (identical to D2, proving no file corruption)
- [ ] Explicit proof that CPU fallback is intentional by design rather than caused by missing DLLs, model corruption, or broken runtime packaging
- [ ] `CPUExecutionProvider` confirmed active on both detector and recognizer ONNX sessions (logged; MLAS is the internal execution engine within `CPUExecutionProvider`, not a separate provider)
- [ ] Bounded runtime-functional OCR smoke on CPU path executed end-to-end without crash, emitting non-empty, non-degenerate Cues
- [ ] Log and evidence recorded in `build_artifacts/phase_d/d3_env_b_cpu/`

### D4 Evidence Contract (Evidence Reconciliation & Phase D Verdict)
- [ ] All D1–D3 evidence collected, verified fail-closed, and reconciled
- [ ] Charter #26 acceptance criteria evaluated against D1–D3 evidence
- [ ] Phase D verdict rendered (PASS / FAIL / NEEDS_REVIEW)
- [ ] If PASS: progression permitted to Phase E (Release Ready remains `NO`; Phase E, Phase F, and Release Redistribution Compliance Gate remain required)
- [ ] Evidence recorded in `build_artifacts/phase_d/d4_verdict/`

---

## 7. Local Evidence Root

The local gitignored evidence root for all Phase D artifacts, logs, screenshots, relay state, and machine-specific context is:

```
build_artifacts/phase_d/
```

This directory and all its contents are gitignored and must never be committed or pushed.

---

## 8. Release Gate Sequencing & Release Readiness Boundary

> [!IMPORTANT]
> **Phase D D4 PASS does NOT make GlyphCue Release Ready.**  
> Per Issue #27, a Phase D PASS permits progression to Phase E only. The following subsequent phases and compliance gates remain strictly required before any public release:
> 
> 1. **Phase E** — Representative Performance & Output Quality Benchmarking (realtime ratio, CER, Cue quality)
> 2. **Phase F** — Installer Lifecycle, Upgrade, Repair & Uninstall Testing
> 3. **Release Redistribution Compliance Gate**: OPEN. Must be resolved for all three ONNX model licenses before public release.
> 4. **Final Release Signing & Release Governance Verification**
> 
> **Current Release Status:** `Release Ready = NO`.
