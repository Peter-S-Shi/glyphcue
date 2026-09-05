# GlyphCue — Phase D Relay Authority

**Document type:** Public Canonical Phase D Relay Document  
**Status:** D0 — Execution Preflight & Relay Scaffold COMPLETE. D1 — NOT STARTED.  
**Branch:** `milestone/13-release-candidate`  
**Authoritative HEAD:** `00a3c65ccd7fca5180e94f242947c2438a0f9651`  
**Governing Issues:** [#26](https://github.com/Peter-S-Shi/glyphcue/issues/26), [#27](https://github.com/Peter-S-Shi/glyphcue/issues/27)  
**Date:** 2026-09-05  

---

## 1. Authority & Prerequisites

Phase C is **FINAL ACCEPTED**. Both independent clean reconstructions (Clean Reconstruction A and Clean Reconstruction B) produced identical pre-sign payloads with verified Authenticode signatures.

Any agent executing Phase D must:
1. Read this document in full before taking any action.
2. Read `docs/m13_phase_d/phase_d_state.json` to determine current module and status.
3. Read `build_artifacts/phase_d/relay_state.json` for live machine-local handoff state (local paths, PIDs, log locations, background processes).
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
| **Environment A** | Clean Windows 11 x64 target with DirectML-capable hardware (D3D12 Feature Level 11_0+, compatible GPU). Offline install from the canonical signed installer. No prior GlyphCue installation. |
| **Environment B** | Clean Windows 11 x64 target where DML is definitively unavailable or disabled (no discrete GPU or GPU disabled), exercising explicit CPU-only fallback path of ONNX Runtime. No prior GlyphCue installation. |

> [!IMPORTANT]
> Evidence from different VM states, snapshots, or machines must **never** be silently combined as though it came from one continuous test environment. If environment continuity cannot be proven, the relevant module must be marked `NEEDS_REVIEW` — not `PASS`.

---

## 4. Phase D Module Definitions

| Module | Name | Scope |
|---|---|---|
| **D0** | Execution Preflight & Relay Scaffold | Relay infrastructure, installer selection, environment role freeze. No installation. ✅ COMPLETE |
| **D1** | Environment A — Clean Offline Install & First Launch | Install canonical installer on Environment A, verify installer integrity, execute first launch, confirm basic UI readiness. |
| **D2** | Environment A — DirectML Runtime Fidelity | On the post-D1 Environment A install: verify `DmlExecutionProvider` is active for detector and recognizer models; run end-to-end OCR proof with real video/image input; confirm output Cue quality is acceptable. |
| **D3** | Environment B — CPU Fallback Validation | Install canonical installer on Environment B, confirm DirectML is unavailable, verify ONNX Runtime correctly falls back to CPU/MLAS provider; run end-to-end OCR to confirm CPU path is functional. |
| **D4** | Evidence Reconciliation & Phase D Verdict | Collect evidence from D1–D3; compare against #26 charter acceptance criteria; produce final Phase D verdict. Release Ready gate can only be opened after D4 PASS and Resolution of the Release Redistribution Compliance Gate. |

> [!IMPORTANT]
> Phase D scope is **installation, first launch, runtime provider verification, and basic OCR fidelity** only.  
> **Phase E** (performance/output quality benchmarking) and **Phase F** (upgrade/repair/uninstall lifecycle) are explicitly **out of scope** for Phase D.

---

## 5. Mandatory Relay Contract

Every agent stopping normally, hitting quota exhaustion, encountering a failure, or leaving a healthy background task must record the following in `build_artifacts/phase_d/relay_state.json` **before stopping**:

```json
{
  "module": "<D0|D1|D2|D3|D4>",
  "status": "<NOT_STARTED|RUNNING|PASS|FAIL|NEEDS_REVIEW|PAUSED_QUOTA>",
  "source_head": "<git commit SHA>",
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

## 6. Evidence Contract per Module

### D1 Evidence Contract
- [ ] Canonical installer SHA-256 verified pre-install
- [ ] Installer ran to completion on Environment A without error
- [ ] Application launched successfully (UI appeared)
- [ ] Log and screenshot evidence in `build_artifacts/phase_d/d1_env_a_install/`

### D2 Evidence Contract
- [ ] `DmlExecutionProvider` confirmed active for detector and recognizer (logged)
- [ ] End-to-end OCR run on real video/image input completed without crash
- [ ] Output Cues meet acceptable quality bar (non-empty, non-degenerate)
- [ ] Evidence in `build_artifacts/phase_d/d2_env_a_directml/`

### D3 Evidence Contract
- [ ] Canonical installer SHA-256 verified pre-install on Environment B
- [ ] DirectML confirmed unavailable/disabled on Environment B
- [ ] ONNX Runtime CPU/MLAS fallback confirmed (logged)
- [ ] End-to-end OCR run on CPU path completed without crash
- [ ] Evidence in `build_artifacts/phase_d/d3_env_b_cpu/`

### D4 Evidence Contract
- [ ] All D1–D3 evidence collected and reconciled
- [ ] Charter #26 acceptance criteria evaluated against evidence
- [ ] Final Phase D verdict (PASS / FAIL / NEEDS_REVIEW) produced
- [ ] Release Redistribution Compliance Gate status recorded
- [ ] Evidence in `build_artifacts/phase_d/d4_verdict/`

---

## 7. Local Evidence Root

The local gitignored evidence root for all Phase D artifacts, logs, screenshots, relay state, and machine-specific context is:

```
build_artifacts/phase_d/
```

This directory and all its contents are gitignored and must never be committed or pushed.

---

## 8. Phase D is NOT Release Ready

Phase D completion is a necessary but not sufficient condition for release. The following additional gates must be satisfied before release:

- **Release Redistribution Compliance Gate**: OPEN. Must be resolved for all three ONNX model licenses before public release.
- **Phase D Verdict**: Must be PASS (not FAIL or NEEDS_REVIEW).
