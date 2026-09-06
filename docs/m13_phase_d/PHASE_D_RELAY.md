# GlyphCue — Phase D Relay Authority

**Document type:** Public Canonical Phase D Relay Document  
**Status:** Phase D COMPLETE / PASS. Phase E is next. M13 remains in progress. Release Ready = NO.
**Branch:** `milestone/13-release-candidate`  
**Operating Model:** Risk-separated, Owner-executed, Agent-instrumented Validation
**Phase C Closure Commit:** `00a3c65ccd7fca5180e94f242947c2438a0f9651`  
**D0 Scaffold Baseline Commit:** `182bc46788df66c95b272aa64193937ebed0fb4f`  
**Governing Issues:** [#26](https://github.com/Peter-S-Shi/glyphcue/issues/26), [#27](https://github.com/Peter-S-Shi/glyphcue/issues/27)  
**Date:** 2026-09-06

---

## 1. Operating Model & Authority

The original Phase C installer was **FINAL ACCEPTED** for its historical build state, then superseded for further Phase D testing after D3 exposed offline runtime model-resolution failures. The corrected D3 source/package/signing changes completed a corrected Phase B/C reseal loop with two clean reconstructions before a new Phase D canonical installer was designated.

### Risk-Separated, Owner-Executed Validation Model

Validation across Milestone 13 (Phases D, E, F) operates under a **risk-separated, owner-executed, agent-instrumented** paradigm:
- The repository owner personally operates the target environments (clean VMware Environment B for installation/CPU fallback; real RTX 3060 Windows host for DirectML hardware fidelity): VM boot/reboot, network adapter isolation toggling, installer execution, UI interactions, native screenshot captures, and executing diagnostic verification commands.
- Coding agents do **not** directly operate target VM/host environments. Owner-executed actions and evidence collection performed according to frozen checklists are explicitly **valid, primary evidence**.
- AI assistants (ChatGPT, Claude, AG, Codex) guide the owner step-by-step with explicit command strings, checklist steps, and evidence requirements.
- Agents inspect, reconcile, and audit the resulting logs, screenshots, and command outputs deposited into `build_artifacts/phase_d/`.
- `build_artifacts/phase_d/relay_state.json` serves as the machine-local handoff authority. Interrupted owner testing **must** be resumable from an exact recorded evidence checkpoint rather than restarted blindly.

### Corrective Reseal Policy

- If a corrective iteration changes first-party runtime code, packaged model inventory, payload manifest/SBOM inputs, offline model-resolution behavior, or signer identity, the previous Phase C accepted installer is superseded for further Phase D testing.
- Such a corrective iteration must establish a corrected B/C reseal loop before owner retest: rebuild/sign the corrected installer, perform two clean corrected reconstructions, and re-run affected reproducibility, integrity, provenance, untracked-file, source-identity, model/DLL identity, manifest/SBOM, and normalized signed-envelope comparisons.
- Only after corrected Phase C PASS may agents designate a new canonical Phase D installer. This designation does not mark D3 PASS; D3 PASS still requires owner clean-VM offline retest.

> [!IMPORTANT]
> **Dynamic HEAD Resolution Rule:**  
> Tracked repository documents (`PHASE_D_RELAY.md`, `phase_d_state.json`) record fixed historical baselines (`phase_c_closure_commit` = `00a3c65...` and `d0_scaffold_baseline_commit` = `182bc46...`) and do not store a static "current HEAD" to avoid self-referential commit churn.  
> Every executing relay agent **must** dynamically resolve the live branch HEAD at module execution start via `git rev-parse HEAD` and record that exact SHA into `build_artifacts/phase_d/relay_state.json` under `source_head`.

---

## 2. Selected Phase D Installer & Historical Test Record

### Canonical Installer Baseline

| Property | Value |
|---|---|
| **Filename** | `GlyphCue-Setup.exe` |
| **Source** | D3 narrow recognizer fallback fix rebuild |
| **Path** | `build_artifacts/d3_recognizer_fallback_fix/installer/GlyphCue-Setup.exe` |
| **Size (Bytes)** | `544,118,632` |
| **SHA-256 (Signed)** | `cf76cb5632befccccb3b63bcd884e5f1e6f515d68fba8fdf0490845100d9b870` |
| **Signer Subject** | `CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root` |
| **Signer Thumbprint** | `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC` |
| **Authenticode Status** | `Valid` (verified in authorized CurrentUser test-trust context) |
| **Certificate Scope** | Local self-signed development test certificate only; not a V1 production signing identity. Present in `CurrentUser\My` with private key and trusted via public certificate in `CurrentUser\Root` and `CurrentUser\TrustedPublisher` for local M13 testing. |

### Corrected B/C Reseal Evidence

| Check | Corrected Result |
|---|---|
| Phase B clean rebuild | PASS: `build_artifacts/d3_b_clean2/phase_b_report.json`; installer 544,156,896 bytes; SHA-256 `cff101ba4105e1f39d86ddfff1e585744a086315e6cf39317e398a76a68c1084`; runtime sanity PASS; signature gate PASS. |
| Phase C reconstructions | PASS: both reconstructions staged 91 frozen artifacts and assembled 21,718 files / 1,877,732,412 bytes. |
| Source identity | PASS: launcher pre-sign SHA-256 identical across reconstructions (`0a1612e3f5897f4147a758c045723aafacaeba206218327d5296f72202569102`); first-party bytecode leakage gate clean. |
| Model/DLL identity | PASS: ONNX and Paddle CPU model artifacts resolved from frozen packaged inventory; payload drift found 21,718 exact-matching unsigned files, 0 unsigned mismatches, 0 missing files, and 0 signed PE failures. |
| Manifest/SBOM/provenance/untracked gates | PASS for untracked-file, integrity, and experiment-scope provenance gates; release redistribution compliance remains OPEN by design. |
| Signed envelope comparison | PASS: recon1 installer `47c9fbe10db5481570cd4ee43606b818768707018987b294cebbd78a00d9b7a7`, recon2 installer `a7306ec7718215e5dcdaea03ca0353a5ba6d29fb4b52a505e840f33cdc4ff0a5`; 528-byte delta limited to Inno header/timestamp and PKCS#7 signature container variance. |
| Signer identity | PASS: `GlyphCue.exe` and both installers Authenticode `Valid` under local CurrentUser test-trust context with thumbprint `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC`. |

### Narrow D3 Recognizer Fallback Fix

After owner D1 PASS, owner D3 evidence showed a narrower remaining recognizer
selection bug: on Environment B with no usable DirectML device/session,
RapidOCR/ONNX Runtime internally fell back to `CPUExecutionProvider`, but
`create_ocr_engine(..., prefer_directml=True)` still selected
`DirectMlOcrEngine` and reported `backend='directml'`.

This checkpoint fixes only the recognizer selection contract: the DirectML OCR
probe must observe the RapidOCR text-recognition ONNX Runtime session provider
list starting with `DmlExecutionProvider`; otherwise it exits the DirectML path
and selects `PaddleOcrEngine`, matching the D3 Paddle CPU fallback contract.

The owner D3 retest installer for this narrow checkpoint is:

| Property | Value |
|---|---|
| **Path** | `build_artifacts/d3_recognizer_fallback_fix/installer/GlyphCue-Setup.exe` |
| **Size (Bytes)** | `544,118,632` |
| **SHA-256 (Signed)** | `cf76cb5632befccccb3b63bcd884e5f1e6f515d68fba8fdf0490845100d9b870` |
| **Authenticode Status** | `Valid` (verified in authorized CurrentUser test-trust context) |
| **Signer Thumbprint** | `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC` |
| **Validation** | Targeted recognizer fallback tests PASS (`20 passed`); installer rebuild runtime sanity PASS; signature gate PASS. |

### Superseded Installer

The previous Phase C accepted installer is superseded for further Phase D testing:

| Property | Value |
|---|---|
| **Filename** | `GlyphCue-Setup.exe` |
| **Source** | Clean Reconstruction A, original Phase C Final Accepted |
| **Size (Bytes)** | `441,941,848` |
| **SHA-256 (Signed)** | `3ea8720033d7d23a5c55296bb2ee08fffb3bc43e2f6a4d9ad0387c63951355a3` |
| **Superseded Because** | D3 offline runtime fidelity failed: DirectML/RapidOCR and production Paddle CPU fallback attempted external model retrieval instead of staying bound to packaged frozen artifacts. |

### Historical Test Record (Preserved Truth)
- **Initial D3 Retest Result:** **FAIL** (Historical Fact). The superseded installer (`3ea87200...`) failed during D3 offline CPU fallback testing because model resolution attempted external web retrieval rather than resolving from bundled offline model assets.
- **Corrected B/C Reseal Result:** **PASS**. Corrected Phase C reseal2 produced two clean reconstructions with payload drift PASS, manifest/SBOM and signature gates PASS, model/DLL identity PASS, source identity PASS, untracked/provenance gates PASS, and installer envelope drift PASS within the allowed signed-envelope variance.
- **Final D1 Result:** **PASS**. Owner validation confirmed clean offline install, first launch, reboot, and relaunch on qualified Environment B.
- **Final D2 Result:** **PASS**. Owner validation on the real RTX 3060 Windows host confirmed `DirectMlOcrEngine`, `DirectMlTextDetector`, ONNX Runtime sessions reporting `['DmlExecutionProvider', 'CPUExecutionProvider']` with DirectML first, and bounded OCR smoke returning `GLYPHCUE DIRECTML 123`.
- **Final D3 Result:** **PASS**. Owner validation on qualified offline Environment B confirmed `PaddleOcrEngine`, `PaddleOcrTextDetector`, offline initialization from packaged artifacts, one detected polygon, and bounded CPU OCR smoke returning `GLYPHCUE TEST 123`.
- **Current Status:** Phase D D4 reconciliation is **COMPLETE / PASS**. Phase E is next. M13 remains in progress and `Release Ready = NO`.

Before any Phase D retest installation, the owner/agent **must** independently verify the installer SHA-256 (`Get-FileHash GlyphCue-Setup.exe -Algorithm SHA256`).

---

## 3. Risk-Separated Target Environments & Owner VM Qualification

Target environments are risk-separated into two distinct target roles:

| Target Role | Machine Environment | Objective | OS Cleanliness Requirement |
|---|---|---|---|
| **Environment B (Offline CPU & Install Target)** | Qualified Clean VMware Windows 11 x64 VM (Build 22000+), Network Isolated | D1 Offline Install/First Launch/Relaunch & D3 Offline CPU Fallback | **Strict Clean OS / Isolated VM** |
| **Environment A (DirectML Hardware Target)** | Owner Real RTX 3060 Windows Host | D2 DirectML Provider Fidelity & Bounded Smoke | **Real Hardware Host (Clean OS Not Required)** |

### Owner VM Qualification Checklist (Environment B Pre-D1 Check)
1. **OS Version Verification**: Clean Windows 11 x64 (Build 22000+) environment.
2. **Network Isolation Capability**: Network interface disabled / outbound traffic blocked prior to installation.
3. **Environment Classification**: Environment B (Clean VMware VM, offline CPU fallback target).

---

## 4. Restructured Phase D Module Definitions & Scope Boundaries

| Module | Name | Target Environment | Scope | Status |
|---|---|---|---|---|
| **D0** | Execution Preflight, Scaffold & Qualification | N/A | Relay infrastructure, installer selection, risk-separated environment classification, dynamic HEAD contract. | ✅ COMPLETE |
| **D1** | Clean Offline Install, First Launch & Relaunch | Qualified Clean VMware Environment B | Owner installs corrected installer on network-blocked clean VMware VM, verifies installer integrity, executes first launch, reboots VM, and verifies successful relaunch post-reboot. | ✅ PASS (owner-validated) |
| **D2** | DirectML Hardware Runtime Fidelity | Owner Real RTX 3060 Windows Host | On real RTX 3060 host: verify model SHA-256 identities and runtime/DLL integrity; verify `DmlExecutionProvider` is active on detector and recognizer ONNX sessions with explicit proof of no silent CPU fallback; run bounded OCR smoke on approved deterministic fixture. (Clean OS not required). | ✅ PASS (owner-validated) |
| **D3** | Production Path Offline CPU Fallback Validation | Qualified Clean VMware Environment B | On clean VMware VM: verify real production path `PaddleOcrEngine` and `PaddleOcrTextDetector` initialize fully offline from bundled frozen model assets without external network retrieval; run bounded OCR smoke. (Note: does not require ONNX Runtime `CPUExecutionProvider`). | ✅ PASS (owner-validated; old-installer failure preserved historically) |
| **D4** | Evidence Reconciliation & Phase D Verdict | Repository Workspace | Owner & agents collect evidence from D1–D3; compare against #26 charter acceptance criteria; produce final Phase D verdict. Per Issue #27, a Phase D PASS permits progression to Phase E only — it does NOT make GlyphCue Release Ready. | ✅ COMPLETE / PASS |

> [!IMPORTANT]
> Scope Boundary Enforcement:
> - Phase D scope is strictly **offline installation, post-reboot relaunch, DirectML provider verification on real hardware, production CPU fallback verification, and bounded functional OCR smoke testing**.
> - **Phase E** — Formal performance benchmarking, realtime ratio evaluation, and output-quality/CER evaluation belong exclusively to Phase E.
> - **Phase F** — Upgrade, repair, and uninstall lifecycle testing belong exclusively to Phase F.

---

## 5. High-Level Operating Model across Remaining M13 Roadmap

The owner-executed, agent-instrumented operating model extends through the remaining Milestone 13 release roadmap:

- **Phase D (Target-Machine Offline Runtime & DirectML Validation)**:
  - *Owner:* Executes clean VMware VM install/relaunch/CPU-fallback and real RTX 3060 host DirectML validation.
  - *Agents:* Provide deterministic verification command strings, inspect/reconcile output logs and screenshots, audit evidence against charter #26, and maintain relay state.
- **Phase E (Representative Performance & Quality Benchmarking)**:
  - *Owner:* Executes frozen benchmark procedures (realtime ratio, CER, Cue quality) on RTX 3060 and VMware targets using canonical video corpus fixtures.
  - *Agents:* Analyze benchmark telemetry, verify non-regression contracts, compute CER metrics, and render performance evaluation verdicts.
- **Phase F (Installer Lifecycle & Maintenance Validation)**:
  - *Owner:* Performs observable installer lifecycle actions (over-install upgrade, repair mode, clean uninstall, residual registry/folder cleanup inspection).
  - *Agents:* Supply lifecycle test fixtures/scripts, inspect post-uninstall filesystem and registry state logs, and audit lifecycle evidence.
- **Division of Responsibilities**:
  - *Code Modifications & Packaging Fixes:* Agent responsibility under TDD.
  - *Redistribution Compliance Gate:* Agent research & audit.
  - *Final Governance Reconciliation & Release Signing:* Joint Owner / Agent gate check before release.

---

## 6. Mandatory Relay Contract

Every agent or owner stopping normally, hitting quota exhaustion, encountering a failure, or pausing execution must record the following in `build_artifacts/phase_d/relay_state.json` **before stopping**:

```json
{
  "module": "<D0|D1|D2|D3|D4>",
  "status": "<NOT_STARTED|RUNNING|PASS|FAIL|NEEDS_REVIEW|PAUSED_QUOTA>",
  "source_head": "<git commit SHA dynamically resolved via git rev-parse HEAD at module start>",
  "installer_sha256": "cf76cb5632befccccb3b63bcd884e5f1e6f515d68fba8fdf0490845100d9b870",
  "environment": "<Environment_A_RTX3060|Environment_B_VMware|N/A>",
  "completed_checks": ["<list of completed verification steps>"],
  "pending_checks": ["<list of remaining required steps>"],
  "evidence_location": "<repo-relative or absolute-local path to evidence>",
  "background_process": null,
  "last_known_result": "<brief description or 'none'>",
  "exact_next_action": "<precise instruction for next step>",
  "next_agent_directive": "<continue|observe|diagnose|stop>"
}
```

---

## 7. Strengthened Fail-Closed Evidence Contracts per Module

### D1 Evidence Contract (Clean VMware Environment B — Offline Install, First Launch & Post-Reboot Relaunch)
- [ ] Owner VM Qualification Gate passed and recorded for VMware Environment B
- [ ] Corrected installer SHA-256 verified pre-install
- [ ] Target VM network adapter disabled / outbound network traffic blocked (strict offline environment)
- [ ] Signed installer ran to completion without error
- [ ] First launch successful (UI renders, application initializes persistent SQLite database and applies schema migrations)
- [ ] Target VM rebooted
- [ ] Relaunch post-reboot successful (UI renders cleanly, persistent state intact)
- [ ] Log and screenshot evidence recorded in `build_artifacts/phase_d/d1_env_b_install/`

### D2 Evidence Contract (Owner Real RTX 3060 Host — DirectML Runtime Fidelity)
- [ ] Exact model SHA-256 identities verified on disk inside installed payload tree:
  - `PP-OCRv6_det_medium.onnx` (`92078b7355007ccfffcd4c8cd441a3afd4538904d06881b29a155e1e679907c2`)
  - `PP-OCRv6_rec_small.onnx` (`6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884`)
  - `ch_ppocr_mobile_v2.0_cls_mobile.onnx` (`e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`)
- [ ] Relevant runtime/DLL identities verified (`onnxruntime` libraries, bundled `DirectML.dll`, required C++ runtime dependencies)
- [ ] `DmlExecutionProvider` confirmed active on both text detector and recognizer ONNX sessions (logged session provider array inspection)
- [ ] Explicit proof of NO silent CPU-only fallback on RTX 3060 host (provider array starts with `DmlExecutionProvider`)
- [ ] Bounded runtime-functional OCR smoke using approved deterministic fixture executed end-to-end without crash
- [ ] OCR output confirmed non-empty and non-degenerate (functional execution check only; zero Phase E performance/quality benchmarking)
- [ ] Log and evidence recorded in `build_artifacts/phase_d/d2_env_a_directml/`

### D3 Evidence Contract (Clean VMware Environment B — Real Production Path Offline CPU Fallback)
- [ ] Corrected installer SHA-256 verified pre-install on clean VMware Environment B
- [ ] Target VM network adapter disabled / offline environment confirmed
- [ ] Production path fallback confirmed as `PaddleOcrEngine` and `PaddleOcrTextDetector`, initializing fully offline from bundled frozen model assets without external network retrieval
- [ ] Proof that CPU fallback is intentional by design rather than caused by missing DLLs, model corruption, or broken runtime packaging
- [ ] Bounded runtime-functional OCR smoke on CPU path executed end-to-end without crash, emitting non-empty, non-degenerate Cues
- [ ] Log and evidence recorded in `build_artifacts/phase_d/d3_env_b_cpu/`

### D4 Evidence Contract (Evidence Reconciliation & Phase D Verdict)
- [x] All D1–D3 evidence collected, verified fail-closed, and reconciled
- [x] Charter #26 acceptance criteria evaluated against D1–D3 evidence
- [x] Phase D verdict rendered: **PASS**
- [x] Progression permitted to Phase E. Release Ready remains `NO`; Phase E, Phase F, and Release Redistribution Compliance Gate remain required.
- [x] Evidence recorded in `build_artifacts/phase_d/d4_verdict/`

### Phase F Lifecycle Finding (Not A Phase D Failure)

Owner lifecycle observation after normal Inno uninstall found substantial owned
installation payload still present under the GlyphCue install directory,
including `app/` and `lib/` trees. The owner then manually removed only the
install directory and confirmed that directory no longer existed. This is a
Phase F uninstall hygiene defect and lifecycle-hardening item. It is not a D1,
D2, or D3 failure, and Phase F is not complete.

---

## 8. Local Evidence Root

The local gitignored evidence root for all Phase D artifacts, logs, screenshots, relay state, and machine-specific context is `build_artifacts/phase_d/`.

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
