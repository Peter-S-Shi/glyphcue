# GlyphCue — Phase D Relay Authority

**Document type:** Public Canonical Phase D Relay Document  
**Status:** D0 — Execution Preflight & Relay Scaffold COMPLETE. D1 — NOT STARTED.  
**Branch:** `milestone/13-release-candidate`  
**Operating Model:** Owner-executed, Agent-instrumented Validation  
**Phase C Closure Commit:** `00a3c65ccd7fca5180e94f242947c2438a0f9651`  
**D0 Scaffold Baseline Commit:** `182bc46788df66c95b272aa64193937ebed0fb4f`  
**Governing Issues:** [#26](https://github.com/Peter-S-Shi/glyphcue/issues/26), [#27](https://github.com/Peter-S-Shi/glyphcue/issues/27)  
**Date:** 2026-09-05  

---

## 1. Operating Model & Authority

Phase C is **FINAL ACCEPTED**. Both independent clean reconstructions (Clean Reconstruction A and Clean Reconstruction B) produced identical pre-sign payloads with verified Authenticode signatures.

### Owner-Executed, Agent-Instrumented Validation Model

Validation across Milestone 13 (Phases D, E, F) operates under an **owner-executed, agent-instrumented** paradigm:
- The repository owner personally operates the target environment: VM boot/shutdown/reboot, network adapter isolation toggling, installer execution, UI interactions, native screenshot captures, and executing diagnostic commands supplied by AI assistants.
- Coding agents are **not** assumed to directly operate the clean target VM environment.
- Owner-executed actions and evidence collection performed according to frozen checklists are explicitly **valid, primary evidence**. No agent shall demand repeating human VM operations merely for "independent execution".
- AI assistants (ChatGPT, Claude, AG, Codex) guide the owner step-by-step with explicit command strings, checklist steps, and evidence requirements.
- Agents inspect, reconcile, and audit the resulting logs, screenshots, and command outputs deposited into `build_artifacts/phase_d/`.
- `build_artifacts/phase_d/relay_state.json` serves as the machine-local handoff and evidence authority. Interrupted owner testing **must** be resumable from an exact recorded evidence checkpoint rather than restarted blindly.

> [!IMPORTANT]
> **Dynamic HEAD Resolution Rule:**  
> Tracked repository documents (`PHASE_D_RELAY.md`, `phase_d_state.json`) record fixed historical baselines (`phase_c_closure_commit` = `00a3c65...` and `d0_scaffold_baseline_commit` = `182bc46...`) and do not store a static "current HEAD" to avoid self-referential commit churn.  
> Every executing relay agent **must** dynamically resolve the live branch HEAD at module execution start via `git rev-parse HEAD` and record that exact SHA into `build_artifacts/phase_d/relay_state.json` under `source_head`.

Any agent or owner executing Phase D must:
1. Read this document in full before taking any action.
2. Complete the **Owner VM Qualification Gate** before starting D1.
3. Read `docs/m13_phase_d/phase_d_state.json` to determine current module and status.
4. Read `build_artifacts/phase_d/relay_state.json` for live machine-local handoff state (local paths, evidence locations, background processes, dynamically resolved `source_head`).
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

Before any Phase D installation, the owner/agent **must** independently verify the installer SHA-256 (`Get-FileHash GlyphCue-Setup.exe -Algorithm SHA256`). If it does not match exactly, **stop immediately**.

---

## 3. Owner VM Qualification Gate (Pre-D1 Mandatory Check)

Before launching D1, the repository owner must run this qualification checklist on their target Windows VM environment to classify the target environment:

### Owner VM Qualification Checklist
1. **OS Version Verification**:
   - Run `Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber`
   - Requirement: Windows 11 x64 (Build 22000+) clean environment.
2. **Network Isolation Capability**:
   - Verify network interface can be disabled or outbound traffic blocked prior to installation (`Get-NetAdapter | Disable-NetAdapter` or VM network disconnect).
   - Requirement: Strict offline installation capability.
3. **Graphics Hardware & Direct3D 12 Feature Level Probe**:
   - Run `dxdiag /t %TEMP%\dxdiag_out.txt` or `Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion`.
   - Check Direct3D 12 Feature Level 11_0+ support and GPU availability.
4. **Environment Classification Verdict**:
   - **Environment A (DirectML-capable)**: Windows 11 x64, network-isolated, discrete/virtual GPU present with Direct3D 12 Feature Level 11_0+ capability.
   - **Environment B (CPU Fallback target)**: Windows 11 x64, network-isolated, GPU absent or explicitly disabled in Device Manager / VM settings, exercising pure CPU execution path.
   - **Ineligible**: OS version < Build 22000, corrupted C++ runtime, or inability to enforce network isolation.

Record the classification verdict in `build_artifacts/phase_d/d0_preflight/vm_qualification.json` and `relay_state.json`.

> [!IMPORTANT]
> Evidence from different VM states, snapshots, or machines must **never** be silently combined as though it came from one continuous test environment. If environment continuity cannot be proven, the relevant module must be marked `NEEDS_REVIEW` — not `PASS`.

---

## 4. Phase D Module Definitions & Scope Boundaries

| Module | Name | Scope |
|---|---|---|
| **D0** | Execution Preflight, Relay Scaffold & VM Qualification Gate | Relay infrastructure, installer selection, environment role freeze, dynamic HEAD contract, Owner VM Qualification Gate. No installation. ✅ COMPLETE |
| **D1** | Environment A — Clean Offline Install, First Launch & Relaunch | Owner installs canonical installer on network-blocked Environment A, verifies installer integrity, executes first launch, reboots system, and verifies successful relaunch post-reboot. |
| **D2** | Environment A — DirectML Runtime Fidelity | On post-D1 Environment A: verify model SHA-256 identities and runtime/DLL integrity; verify `DmlExecutionProvider` is active on detector and recognizer ONNX sessions with explicit proof of no silent CPU fallback; run bounded runtime-functional OCR smoke on approved deterministic fixture (successful end-to-end execution, non-empty output). |
| **D3** | Environment B — CPU Fallback Validation | On Environment B: verify DirectML is absent/unavailable by design; verify identical model/runtime DLL integrity intact; verify `CPUExecutionProvider` active on detector and recognizer sessions; prove fallback is intentional rather than caused by corruption/missing DLLs; run bounded runtime-functional OCR smoke on CPU path. |
| **D4** | Evidence Reconciliation & Phase D Verdict | Owner & agents collect evidence from D1–D3; compare against #26 charter acceptance criteria; produce final Phase D verdict. Per Issue #27, a Phase D PASS permits progression to Phase E only — it does NOT make GlyphCue Release Ready. |

> [!IMPORTANT]
> Scope Boundary Enforcement:
> - Phase D scope is strictly **offline installation, post-reboot relaunch, runtime provider verification, intentional fallback verification, and bounded functional OCR smoke testing**.
> - **Phase E** — Formal performance benchmarking, realtime ratio evaluation, and output-quality/CER evaluation belong exclusively to Phase E.
> - **Phase F** — Upgrade, repair, and uninstall lifecycle testing belong exclusively to Phase F.

---

## 5. High-Level Operating Model across Remaining M13 Phases

The owner-executed, agent-instrumented operating model extends through the remaining Milestone 13 release roadmap without weakening any acceptance gate:

- **Phase D (Target-Machine Offline Runtime & DirectML Validation)**:
  - *Owner:* Performs VM qualification, offline installation, first launch, post-reboot relaunch, execution of provider verification scripts, and bounded OCR smoke runs.
  - *Agents:* Provide deterministic verification command strings, inspect/reconcile output logs and screenshots, audit evidence against charter #26, and maintain relay state.
- **Phase E (Representative Performance & Quality Benchmarking)**:
  - *Owner:* Executes frozen benchmark procedures (realtime ratio, CER, Cue quality) on qualified Environment A and B targets using canonical video corpus fixtures.
  - *Agents:* Analyze benchmark telemetry, verify non-regression contracts, compute CER metrics, and render performance evaluation verdicts.
- **Phase F (Installer Lifecycle & Maintenance Validation)**:
  - *Owner:* Performs observable installer lifecycle actions (over-install upgrade, repair mode, clean uninstall, residual registry/folder cleanup inspection).
  - *Agents:* Supply lifecycle test fixtures/scripts, inspect post-uninstall filesystem and registry state logs, and audit lifecycle evidence.
- **Cross-Phase Division of Responsibilities**:
  - *Redistribution Compliance Gate*: Research & agent audit (ONNX model licensing resolution).
  - *Release Code Changes & Test Automation*: Agent responsibility under TDD.
  - *Release Signing & Final Release Governance*: Joint Owner / Agent gate check before release.

---

## 6. Mandatory Relay Contract

Every agent or owner stopping normally, hitting quota exhaustion, encountering a failure, or pausing execution must record the following in `build_artifacts/phase_d/relay_state.json` **before stopping**:

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
  "exact_next_action": "<precise instruction for the next agent/owner step>",
  "next_agent_directive": "<continue|observe|diagnose|stop>"
}
```

> [!CAUTION]
> A healthy long-running task or owner testing session must be recorded with exact completed checks and evidence locations so that any interrupted testing can be resumed from an exact checkpoint without restarting blindly.  
> A module may only be marked `PASS` when its own evidence contract is complete.  
> Absolute machine paths, VM/snapshot IDs, private credentials, or local process details belong in `relay_state.json` only — **never** in this document or `phase_d_state.json`.

---

## 7. Strengthened Fail-Closed Evidence Contracts per Module

### D1 Evidence Contract (Environment A — Offline Install, First Launch & Post-Reboot Relaunch)
- [ ] Owner VM Qualification Gate passed and recorded (`vm_qualification.json`)
- [ ] Canonical installer SHA-256 verified pre-install (`3ea8720033d7d23a5c55296bb2ee08fffb3bc43e2f6a4d9ad0387c63951355a3`)
- [ ] Target machine network adapter disabled / outbound network traffic blocked (strict offline environment)
- [ ] Signed installer ran to completion without error
- [ ] First launch successful (UI renders, application initializes persistent SQLite database and applies schema migrations)
- [ ] Target system rebooted
- [ ] Relaunch post-reboot successful (UI renders cleanly, persistent state intact)
- [ ] Log and screenshot evidence recorded in `build_artifacts/phase_d/d1_env_a_install/`

### D2 Evidence Contract (Environment A — DirectML Runtime Fidelity)
- [ ] Exact model SHA-256 identities verified on disk inside installed payload tree:
  - `PP-OCRv6_det_medium.onnx` (`92078b7355007ccfffcd4c8cd441a3afd4538904d06881b29a155e1e679907c2`)
  - `PP-OCRv6_rec_small.onnx` (`6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884`)
  - `ch_ppocr_mobile_v2.0_cls_mobile.onnx` (`e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`)
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

## 8. Local Evidence Root

The local gitignored evidence root for all Phase D artifacts, logs, screenshots, relay state, and machine-specific context is:

```
build_artifacts/phase_d/
```

This directory and all its contents are gitignored and must never be committed or pushed.

---

## 9. Release Gate Sequencing & Release Readiness Boundary

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
