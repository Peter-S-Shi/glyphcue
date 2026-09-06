# GlyphCue — Phase D Relay Authority

**Document type:** Public Canonical Phase D Relay Document  
**Status:** Phase D COMPLETE / PASS. Phase E COMPLETE / PASS. Phase F COMPLETE / PASS. Milestone 13 COMPLETE (merged via PR #29). Post-M13 Public Distribution Gate (Issue #30, PR #31) CLOSED & ACCEPTED. Release Ready = NO; Portfolio Packaging Ready = NO (pending post-merge release sequence: merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets: GlyphCue-Setup-1.0.0.exe, GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip, SHA256SUMS.txt, provenance.json → independent download verification).
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

### Corrective Iteration Policy

- Corrective iterations are risk-scoped. Ordinary runtime/model/manifest/SBOM/offline-resolution/signer fixes require a corrected build, Authenticode/signature verification, payload integrity checks, and targeted owner retest of the affected Phase D gate(s).
- A full Phase B/C dual-reconstruction reproducibility seal is not repeated automatically before every owner retest. It is reserved for final Release Candidate closure, or for a specific corrective change whose content, packaging, or provenance impact genuinely invalidates the existing reproducibility baseline and requires resealing.
- If a corrective change does require resealing, agents must state the invalidated baseline and rerun the appropriate reproducibility, integrity, provenance, untracked-file, source-identity, model/DLL identity, manifest/SBOM, and normalized signed-envelope comparisons before selecting that resealed artifact.
- A corrected build or reseal designation does not mark any Phase D gate PASS. D1/D2/D3/D4 PASS requires owner evidence and reconciliation under the applicable gate contract.

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
- **Current Status:** Phase D D4 reconciliation, Phase E owner-led validation, and Phase F owner-led lifecycle validation are all **COMPLETE / PASS**. Milestone 13 is **COMPLETE**. Post-M13 Public Distribution Gate (Issue #30, PR #31) is **CLOSED & ACCEPTED**. `Release Ready = NO` and `Portfolio Packaging Ready = NO` remain current until the post-merge release sequence (merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets: `GlyphCue-Setup-1.0.0.exe`, `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`, `SHA256SUMS.txt`, `provenance.json` → independently verify downloads) completes.

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
| **D4** | Evidence Reconciliation & Phase D Verdict | Repository Workspace | Owner & agents collect evidence from D1–D3; compare against #26 charter acceptance criteria; produce final Phase D verdict. Per Issue #27, Phase D PASS permitted progression to Phase E only and did not make GlyphCue Release Ready. | ✅ COMPLETE / PASS |

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
- [x] Progression permitted to Phase E at D4 closure. Phase E and Phase F have since completed; Milestone 13 is complete; Post-M13 Public Distribution Gate is closed; Release Ready remains NO and Portfolio Packaging Ready remains NO pending post-merge release sequence (merge PR #31 → create v1.0.0 tag → generate final provenance.json & SHA256SUMS.txt → publish GitHub Release with all four assets → independent download verification).
- [x] Evidence recorded in `build_artifacts/phase_d/d4_verdict/`

### Phase F Lifecycle Finding (Not A Phase D Failure) — RESOLVED

Owner lifecycle observation after normal Inno uninstall found substantial owned
installation payload still present under the GlyphCue install directory,
including `app/` and `lib/` trees. The owner then manually removed only the
install directory and confirmed that directory no longer existed. This was a
Phase F uninstall hygiene defect and lifecycle-hardening item; it was not a D1,
D2, or D3 failure. **Status: RESOLVED.** Root cause and fix, plus a second,
narrower F4 defect found and fixed during the same corrective pass, are
recorded in full in Section 11 below.

---

## 8. Phase E Closure — Representative Performance & Output Quality

Phase E owner-led validation is **COMPLETE / PASS**. The expensive OCR tests
were not rerun during this reconciliation; agents inspected the local evidence
under `build_artifacts/phase_e/` and recorded only sanitized metrics and
structure.

### E1 Performance Verdict

- **E1 Result:** PASS.
- **Fixture Governance:** The canonical frozen fixture is identified by
  SHA-256 `72a7621639730b62b5a06a266499ea66768df277cad15553cab6d2487b972465`.
  Its bytes/hash are frozen inputs generated under the frozen DevQA generation
  environment. Downstream candidate validation must consume that frozen artifact
  rather than assume candidate runtimes will regenerate byte-identical MP4
  encoding.
- **Runtime:** Packaged DirectML runtime using `DirectMlOcrEngine` and
  `DirectMlTextDetector`.
- **Timing:** Warm-up was discarded. Three timed runs measured `1.153x`,
  `1.387x`, and `1.392x` realtime; median `1.387x` realtime.
- **Repeat Policy:** No repeat required.

### E2 Output-Quality Verdict

- **E2 Result:** PASS.
- **Synthetic Golden:** Canonical synthetic golden comparison was an exact
  match under the packaged DirectML runtime.
- **Bounded Real-OCR Spot Check:** The owner compared packaged DirectML against
  trusted DevQA DirectML on the private `sample_h` 900-930s window. Both lanes
  produced 225 observations, 29 cues, 6 adjacent exact duplicate raw cues, and
  2 missing-language cues, with identical cue timing and structure.
- **Nondeterminism Classification:** Owner evidence recorded four cue text
  differences limited to one OCR character in the known fixed-footer/noise
  line; the main subtitle text remained identical. This is bounded real-OCR
  nondeterminism, not a packaging regression.
- **Privacy Boundary:** Raw private sample text, local host paths, and
  machine-specific evidence remain in gitignored local evidence only and are not
  published in tracked governance docs.

### E3 Reconciliation Verdict

- Phase E is **COMPLETE / PASS**.
- Phase F has since completed (Section 11); Milestone 13 is **COMPLETE**.
- `Release Ready = NO`.
- Issue #27 is the completed execution record for Phases A-F; no Milestone
  13 execution gate remains open.

---

## 9. Local Evidence Root

The local gitignored evidence roots for Phase D, Phase E, and Phase F artifacts, logs,
screenshots, relay state, and machine-specific context are
`build_artifacts/phase_d/`, `build_artifacts/phase_e/`, and `build_artifacts/phase_f/`.

---

## 10. Release Gate Sequencing & Release Readiness Boundary

> [!IMPORTANT]
> **Phase D, Phase E, and Phase F PASS completed Milestone 13's owner-executed validation scope.**
> Subsequent post-M13 Public Distribution Gate (Issue #30, PR #31) has CLOSED & ACCEPTED redistribution and packaging compliance:
> 
> 1. **Release Redistribution Compliance Gate**: CLOSED & ACCEPTED. All 5 OCR models resolved under Apache-2.0; GlyphCue licensed under MIT; PyAV FFmpeg replaced with pinned LGPL-3.0 build (`GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`, SHA-256 `FC59A64DB0B932A63FB7432C57CFE850BA3CAA07F73E9BEC4437416E3240D3CC`).
> 2. **Release Signing Policy**: Self-signed Authenticode (`CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root`, thumbprint `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC`) accepted by Owner for v1.0.0 public distribution with explicit SmartScreen / not-publicly-trusted disclosure; formal production/public-trust code signing is future hardening, NOT a v1.0.0 blocker.
> 3. **Candidate Installer Frozen**: `GlyphCue-Setup-1.0.0.exe`, SHA-256 `F88C2FE2C6D226BD2FFF5ECFDC7E7F64DC32917B8C00597FB17D42B9A7244446` (Authenticode `Valid`).
> 
> **Final Release Assets (4 Total):**
> 1. `GlyphCue-Setup-1.0.0.exe` (SHA-256: `F88C2FE2C6D226BD2FFF5ECFDC7E7F64DC32917B8C00597FB17D42B9A7244446`)
> 2. `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip` (SHA-256: `FC59A64DB0B932A63FB7432C57CFE850BA3CAA07F73E9BEC4437416E3240D3CC`)
> 3. `SHA256SUMS.txt`
> 4. `provenance.json` (generated post-merge, bound to final `main` merge commit SHA and `v1.0.0` tag)
> 
> **Post-Merge Release Sequence:**
> `merge PR #31 → create v1.0.0 tag on accepted main commit → generate final provenance.json and SHA256SUMS.txt → publish GitHub Release with all four assets → independently verify downloads → Portfolio Packaging Ready = YES / Milestone 14`
> 
> **Current Release Status:** `Release Ready = NO`; `Portfolio Packaging Ready = NO` (until the above post-merge sequence completes).

---

## 11. Phase F Closure — Installer Lifecycle, Upgrade, Repair & Uninstall

Phase F owner-led lifecycle validation is **COMPLETE / PASS**. Two real defects
were found and fixed during this phase; both corrective histories are
preserved below as historical fact rather than edited away.

### F1 — Repair: PASS
### F2 — Two-Version Upgrade: PASS
### Runtime-Write Prohibition Gate: PASS

Owner confirmed that across a normal launch/exit cycle, the entire
installer-owned `app_root` remained at **21,721 files** before and after,
with **added/removed/modified = 0** and **first-party `__pycache__`/`*.pyc`
count = 0**.

### F3 — Default Uninstall: PASS (corrected)

**Original failure (historical fact, preserved):** the first F3 run left 202
residual files under the installer-owned `app_root` — all runtime-generated
`__pycache__`/`*.pyc` — because the launcher wrote Python bytecode into
`app_root` on every run, and standard Inno Setup uninstall only removes
files/directories it tracked at install time, so that untracked residue was
never cleaned up. Uninstall itself exited 0 and correctly preserved
`%USERPROFILE%\.glyphcue` with an unchanged DB hash throughout.

**Fix (PR #28):** the packaged launcher now runs `python.exe -B` (suppressing
bytecode writes) in both authoritative launcher-compilation paths
(`execute_phase_b.py`, `execute_phase_c.py`), and default uninstall now
unconditionally force-removes `{app}` after the existing, unchanged opt-in
user-data purge logic.

**Corrected retest: PASS.** Exit 0; `app_root` fully removed; 0 residual
files; user data/DB preserved with unchanged hash; synthetic sentinel
preserved.

### F4 — Explicit Purge: PASS (corrected)

**Original failure (historical fact, preserved):** the first F4 attempt (with
the "Remove user databases and custom settings" checkbox checked) crashed at
uninstall runtime with `Internal error: Unknown constant "userprofile"` —
`{userprofile}` is not a valid Inno Setup constant, so
`ExpandConstant('{userprofile}\.glyphcue')` always failed once actually
evaluated. The failure was narrowly scoped: `app_root` was already fully
removed, the synthetic `%USERPROFILE%\.glyphcue` remained intact, and real
user-data backups and their hashes were entirely unaffected.

**Fix (PR #28):** the purge path now resolves via `GetEnv('USERPROFILE')`,
fails closed (skips deletion entirely) if that variable is blank, and only
then builds the deletion path via `AddBackslash(...) + '.glyphcue'`. Default
(non-purge) uninstall and the independent `{app}` force-removal are
unaffected.

**Final retest: PASS.** `app_root` removed; synthetic
`%USERPROFILE%\.glyphcue` removed; real user-data backup unaffected. The
owner subsequently restored the real user data, and the restored DB hash
matches the pre-Phase-F baseline.

### Provenance Truth Audit & Correction (metadata-only, PR #28)

A narrow provenance audit found that `generate_payload_manifest.py`'s
`classify_payload_file()` recorded a **hardcoded constant**
(`dea596e97c1648d9480494f2923e9d0aeee6a2f02ab91fd4455e10592c82400a`) as
`GlyphCue.exe`'s `source_artifact_sha256` regardless of which
`LAUNCHER_CS_SOURCE` revision was actually compiled — that constant matches
neither the pre-fix nor post-fix launcher source hash, so it was never real
provenance for any build. Pre-Merge Governance Gate review found the
Phase B/C caller-side fix alone was insufficient: the stale constant still
existed as an executable fallback inside `generate_payload_manifest.py`
itself (`build_source_artifact_sha_map()` and `classify_payload_file()`).

**Correction (source-of-truth):** the hardcoded fallback was removed
entirely from `generate_payload_manifest.py`. With no extraction-map
provenance supplied, `source_artifact_sha256` for `GlyphCue.exe` is now left
unresolved (`None`) — fail-closed, never fabricated. Both authoritative
launcher build paths (`execute_phase_b.py`, `execute_phase_c.py`) supply the
real provenance by computing `source_artifact_sha256` dynamically from the
actual `LAUNCHER_CS_SOURCE` compiled into that build, via each path's
existing `extraction_map`/`extraction_provenance_map`, which
`classify_payload_file()` already prefers. This is a manifest-generation-
code-only change — it does not alter runtime, launcher behavior, or
uninstall logic — so per the Corrective Iteration Policy (Section 1) it
does not invalidate and does not require rerunning the F1/F2/Runtime-Write/
F3/F4 owner evidence above, which predates this manifest-code fix.

**Reconciliation of the already-built corrective `app_root`:** the manifest
and SBOM under `build_artifacts/phase_f/f3_corrective/app_root/legal/manifest/`
(the exact `app_root` Owner Runtime-Write/F3/F4 evidence was collected
against) were regenerated with the real launcher source hash
(`0656b07fd2384b3065b7ba9b3ba41d1b5d4106c3e0406fcd61b4a8d75207823f`).
Manifest-to-disk reconciliation confirmed **21,718 manifest entries = 21,718
on-disk files, 0 unindexed, 0 missing, 0 integrity mismatches**. The inner
`GlyphCue.exe` launcher binary itself is confirmed byte-identical before and
after (`e2d2230f3f8839036b1a1f6103e38848217495f624e45801dcb3c49f3d68e829`) —
only its manifest metadata changed. Because the payload manifest/SBOM bytes
changed, the outer installer was rebuilt (Inno Setup 6.3.3 portable, the
already-restored compiler) and re-signed with the existing M13 development
test certificate; the inner launcher was not recompiled or re-signed.

### Final Metadata-Reconciled Installer

| Property | Value |
|---|---|
| **SHA-256 (Signed)** | `DBC855FB710A8B4BDB9B9F181942E61F2FEE404DD3B1ABDDE20CAC8E8A85A9F0` |
| **Size (Bytes)** | `544,293,224` |
| **Authenticode Status** | `Valid` |
| **Signer Thumbprint** | `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC` |
| **Signer Scope** | Local self-signed development test certificate only; not a production signing identity. |

### Historical Owner-Tested Candidate (Pre-Provenance-Reconciliation)

| Property | Value |
|---|---|
| **SHA-256 (Signed)** | `85B683221BFCA6DAC53E297449DABBE25925E7CAB4E0839847744C2897750BB7` |
| **Status** | This is the exact installer identity Runtime-Write Prohibition, F3, and F4 above were actually Owner-validated against. Superseded only by the metadata-only provenance correction above; no runtime, launcher, or uninstall behavior differs between the two candidates (the inner `GlyphCue.exe` is byte-identical), so that owner evidence is inherited unchanged. |

### Phase F Verdict

Phase F is **COMPLETE / PASS**. Combined with Phase D and Phase E, Milestone
13's owner-executed validation scope is **COMPLETE**. The post-M13 Public
Distribution Gate (Issue #30, PR #31) is **CLOSED & ACCEPTED**. `Release Ready`
remains **NO** and `Portfolio Packaging Ready` remains **NO** pending the post-merge
release sequence with all four assets and independent download verification (Section 10).
