# GlyphCue — Milestone 13: Independent Reconstruction Runbook & Handoff

**Document type:** Authoritative Independent Reconstruction Runbook & Verification Handoff  
**Governing issues:** [#17](https://github.com/Peter-S-Shi/glyphcue/issues/17), [#20](https://github.com/Peter-S-Shi/glyphcue/issues/20), [#21](https://github.com/Peter-S-Shi/glyphcue/issues/21), [#24](https://github.com/Peter-S-Shi/glyphcue/issues/24), [#25](https://github.com/Peter-S-Shi/glyphcue/issues/25), [#26](https://github.com/Peter-S-Shi/glyphcue/issues/26), [#27](https://github.com/Peter-S-Shi/glyphcue/issues/27)  
**Trusted Source Commit:** `5905df09d012cb63a34b98c484b43958477e52e8`  
**Target Branch:** `milestone/13-release-candidate`  
**Date:** 2026-09-05  

---

## 1. Executive Summary & Purpose

This runbook defines the exact, fail-closed procedure for an independent agent or clean developer session to execute and verify **Phase C (Reconstruction & Deterministic Drift Verification)** of the GlyphCue Minimum Runtime-Fidelity Packaging Experiment ([Issue #27](https://github.com/Peter-S-Shi/glyphcue/issues/27)).

Phase C proves that the GlyphCue V1 private runtime payload and installer can be reconstructed offline and deterministically from frozen inputs with zero functional or payload drift across independent clean environments.

---

## 2. Frozen Input Contracts & Baseline Identities

All reconstructions consume the authoritative frozen contracts recorded in the repository:

- **Build-Base Specification:** `docs/m13_build_base_identity.json` / `docs/m13_build_base_identity.md`
- **Authoritative Models:**
  - `PP-OCRv6_det_medium.onnx` (SHA-256: `92078b7355007ccfffcd4c8cd441a3afd4538904d06881b29a155e1e679907c2`)
  - `PP-OCRv6_rec_small.onnx` (SHA-256: `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884`)
  - `ch_ppocr_mobile_v2.0_cls_mobile.onnx` (SHA-256: `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`)
- **CPython 3.12.10 Embeddable Runtime:** `python-3.12.10-embed-amd64.zip` (SHA-256: `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`)
- **Python Dependencies:** Exact frozen wheel and sdist artifact inventory defined in `docs/m13_build_base_identity.json`.
- **SQL Migrations:** 5 schema migrations (V1 through V5).
- **Approved Test Certificate:**
  - Subject: `CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root`
  - Thumbprint: `A3E4E5320779C9F63E513D870E209C26B819C61E`
- **First-Party Launcher Compiler:** Microsoft C# Compiler `csc.exe` (`/target:winexe /platform:x64`).
  - Pre-sign baseline SHA-256: `0a1612e3f5897f4147a758c045723aafacaeba206218327d5296f72202569102`
  - Post-sign baseline SHA-256: `187ee188700d0ec599cbbe0854931967e35bab90fd5e09409fb7d18320516e17`

---

## 3. Independent Reconstruction Procedure

### Step 3.1: Environment Verification & Scaffold Self-Test

Before running reconstruction, verify the local Python virtual environment and run the packaging scaffold test suite:

```powershell
# 1. Ensure working directory is repository root
cd <workspace-root>

# 2. Run scaffold self-test and fail-closed integrity regressions
.venv\Scripts\python.exe tools\packaging\validate_scaffold.py
```

**Expected Outcome:** All 13 unit tests pass, verifying build-base completeness, synthetic fixture generation, fail-closed integrity gates, signature gates, dual-hash preservation, manifest-to-disk reconciliation, and strict offline staging enforcement.

---

### Step 3.2: Execute Strict Offline Reconstruction & Drift Verification

Execute `tools/packaging/execute_phase_c.py` targeting the designated output root:

```powershell
# Run Phase C reconstruction pipeline with isolated staging and output root
.venv\Scripts\python.exe tools\packaging\execute_phase_c.py --output-root build_artifacts\phase_c
```

#### Execution Pipeline Order:
1. **Strict Offline Input Staging:** Resolves all content-addressed artifacts defined in `docs/m13_build_base_identity.json` from the seed cache. Zero network access and zero undeclared fallback paths are used; missing inputs fail immediately with `FileNotFoundError`.
2. **Deterministic Payload Assembly:** Unpacks CPython runtime, configures `python312._pth` isolation, unpacks frozen dependencies with assembly-time dual-hash provenance tracking and deterministic collision detection, copies SQL migrations and authoritative ONNX models, and copies diagnostics tools without development `__pycache__` / `.pyc` clutter.
3. **Deterministic Launcher Compilation & Signing:** Compiles `GlyphCue.exe` via `csc.exe`, evaluates pre-sign hash, and signs using the approved test certificate.
4. **Signature Gate Evaluation:** Verifies Authenticode signature and asserts thumbprint equals `A3E4E5320779C9F63E513D870E209C26B819C61E`.
5. **Disposable Runtime Sanity Probe:** Copies `<app_root>` to a temporary scratch folder `_sanity_scratch_*` and executes sanity import checks (testing `glyphcue`, 5 SQL migrations, `PySide6` QPA plugins, `av`, and ONNX Runtime provider initialization). The actual `<app_root>` remains 100% immutable.
6. **CycloneDX 1.6 SBOM Generation:** Emits `legal/manifest/sbom.json` from the payload file inventory.
7. **Final Payload Manifest Generation & Reconciliation:** Emits `legal/manifest/payload_manifest.json` and asserts exact 100% path and count reconciliation against files on disk (0 unindexed files, 0 missing files).
8. **Inno Setup Installer Compilation:** Builds single-file standalone installer `GlyphCue_Setup_v0.1.0-dev_x64.exe` using `ISCC.exe`.
9. **Drift Verification Against Baseline:** Runs `verify_payload_drift.py` comparing pre-sign payload hashes, signature inventories, and installer envelope metadata between Reconstruction 1 and Reconstruction 2.

---

## 4. Verification Gates & Acceptance Criteria

| Verification Gate | Requirement / Pass Criterion | Failing Behavior |
|---|---|---|
| **Integrity Gate** | All staged and unpacked files match frozen SHA-256 hashes in `docs/m13_build_base_identity.json`. | Fails closed with `RuntimeError` |
| **Untracked File Gate** | 0 unclassified or unknown files in `<app_root>`. | Fails closed with `RuntimeError` |
| **Provenance Conflict Gate** | No two source wheels overwrite the same destination file unless explicitly allowlisted in deterministic recipe. | Fails closed with `RuntimeError` |
| **Signature Gate** | `GlyphCue.exe` validly signed by thumbprint `A3E4E5320779C9F63E513D870E209C26B819C61E`. | Fails closed with `RuntimeError` |
| **Manifest Reconciliation** | Final `payload_manifest.json` file count and paths exactly match files on disk. | Fails closed with `RuntimeError` |
| **Pre-Sign Payload Drift** | 0 bytes drift on all files prior to code signing across reconstructions. | `PAYLOAD_DRIFT_DETECTED` |
| **Installer Envelope Drift** | Only allowed timestamp, embedded signature, and `unins000.exe` compiler variations present; 0 unexpected envelope drift. | `ENVELOPE_DRIFT_DETECTED` |

---

## 5. Scope Boundary & Lifecycle Status

> [!IMPORTANT]
> **Phase C Scope Boundary & Current Status:**  
> - Phase A: **ACCEPTED**  
> - Phase B: **ACCEPTED**  
> - Phase C: **Same-Session Determinism PASS & Corrective Tooling Complete**; final Phase C acceptance remains **PENDING** independent-agent/session reconstruction.  
> - Phase D: **NOT STARTED**.  
>  
> Phase C certifies offline deterministic reconstruction, payload integrity, and installer compilation.  
> **DirectML hardware execution, physical GPU offload verification, and end-to-end OCR benchmark acceptance are strictly deferred to Phase D (Independent Target Machine / Offline Runtime Validation).** Local sanity probes in Phase C verify module imports and structure only, and do not constitute DirectML hardware acceptance.
