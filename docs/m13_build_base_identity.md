# GlyphCue — Milestone 13: Frozen Build-Base Identity

**Document type:** Authoritative frozen build-base record for the Minimum Runtime-Fidelity Packaging Experiment  
**Governing issues:** [#17](https://github.com/Peter-S-Shi/glyphcue/issues/17), [#20](https://github.com/Peter-S-Shi/glyphcue/issues/20), [#21](https://github.com/Peter-S-Shi/glyphcue/issues/21), [#24](https://github.com/Peter-S-Shi/glyphcue/issues/24), [#25](https://github.com/Peter-S-Shi/glyphcue/issues/25), [#26](https://github.com/Peter-S-Shi/glyphcue/issues/26), [#27](https://github.com/Peter-S-Shi/glyphcue/issues/27)  
**Trusted Source Commit:** `5905df09d012cb63a34b98c484b43958477e52e8`  
**Target Branch:** `milestone/13-release-candidate`  
**Date:** 2026-09-05  

---

## 1. Executive Summary

This document freezes all inputs, toolchain specifications, native artifact hashes, model identities, and the deterministic synthetic test fixture for the **GlyphCue V1 Minimum Runtime-Fidelity Packaging Experiment**.

Both required clean reconstructions (Reconstruction 1 and Reconstruction 2) and all subsequent offline runtime validation environments must consume these frozen identities without live internet package resolution.

---

## 2. Frozen Runtime & Artifact Identities

### 2.1 CPython 3.12.10 Embeddable Runtime
- **Archive Filename:** `python-3.12.10-embed-amd64.zip`
- **Source URL:** `https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip`
- **Size (Bytes):** `11,133,606`
- **SHA-256 Hash:** `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`
- **Verification Source:** Official python.org sigstore / SHA-256 release record.

### 2.2 ONNX Model Artifacts
| Model Filename | Size (Bytes) | SHA-256 Hash | Role / Status |
|---|---|---|---|
| `PP-OCRv6_det_medium.onnx` | 62,119,454 | `92078b7355007ccfffcd4c8cd441a3afd4538904d06881b29a155e1e679907c2` | PP-OCRv6 Text Detector (Medium profile) — Authoritative Production Candidate per #20/#26; `verification_status: unresolved` |
| `PP-OCRv6_rec_small.onnx` | 21,234,383 | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` | PP-OCRv6 Text Recognizer (Small profile); `verification_status: unresolved` |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | 585,532 | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` | Text Direction Classifier (Mobile profile); `verification_status: unresolved` |

### 2.3 Critical Native DLLs
| Binary File | Size (Bytes) | SHA-256 Hash | Origin |
|---|---|---|---|
| `DirectML.dll` | 18,527,776 | `b73972115320e906a49602f2027a3266622881b0d325ba685e0f165a9482a8d7` | `onnxruntime-directml==1.24.4` wheel |
| `onnxruntime.dll` | 21,111,832 | `302c69f9779d63ef4ab90316e59444c4acbaca7fe3455020d79d10bcfcb00715` | `onnxruntime-directml==1.24.4` wheel |

### 2.4 Database SQL Migrations
| Migration File | Size (Bytes) | SHA-256 Hash |
|---|---|---|
| `0001_create_cues.sql` | 137 | `823d7aa7551f3c3fc3e61683f4e23699eef6438efd09a564f8b7e3b1ab2d05ff` |
| `0002_create_language_layers.sql` | 250 | `be845d70da4be9c960b879ceb5e41192c1ec585940ab4f7c0f8c4626fd5f974a` |
| `0003_create_track_groups.sql` | 193 | `4c2d162d65b48ef558552849cf04fa2c5c69d377a408ca7d85e00eb6bb9a3118` |
| `0004_create_observations.sql` | 531 | `8c578d6bc72ac86ee8fd1e1015875e3b77e98578692d97b23df6b278ec4f1de0` |
| `0005_add_source_id_to_cues_and_observations.sql` | 284 | `7c821706ab1c45dc7b30823e1e874bcb0f265d51e14702bed9c75039dfef7ed7` |

---

## 3. Deterministic Synthetic Test Fixture

- **Generator Recipe:** `tools/packaging/generate_synthetic_fixture.py`
- **Output Filename:** `glyphcue_synthetic_fixture_v1.mp4`
- **Duration / Dimensions:** 6.0 seconds (60 frames at 10 fps), 1280x720, MP4 container (`mp4v`).
- **File Size:** `183,789` bytes
- **SHA-256 Hash:** `72a7621639730b62b5a06a266499ea66768df277cad15553cab6d2487b972465`
- **Golden Reference Output:** `docs/m13_synthetic_fixture_golden.json` (3 reconstructed cues with millisecond timestamps and confidence metrics).

---

## 4. Packaging Toolchain & Scripts

| Tool / Script | Purpose |
|---|---|
| `tools/packaging/generate_synthetic_fixture.py` | Generates and verifies the deterministic synthetic test video fixture. |
| `tools/packaging/generate_golden_reference.py` | Generates the golden reference OCR output from the synthetic fixture. |
| `tools/packaging/assemble_embeddable_runtime.py` | Assembles `<app_root>` topology per #25 with `python312._pth` isolation. |
| `tools/packaging/generate_payload_manifest.py` | Generates `payload_manifest.json` and evaluates fail-closed gates. |
| `tools/packaging/generate_cyclonedx_sbom.py` | Generates valid CycloneDX 1.6 JSON (`sbom.json`) from the manifest. |
| `tools/packaging/verify_payload_drift.py` | Compares two isolated reconstruction outputs for payload drift. |
| `tools/packaging/verify_signatures.py` | Evaluates the Signature Gate for first-party and third-party binaries. |
| `tools/packaging/glyphcue_installer.iss` | Inno Setup 6 installer script template (per-user, user data isolation, purge support). |
| `tools/packaging/validate_scaffold.py` | Automated test script to validate the Phase A scaffold and tooling. |
