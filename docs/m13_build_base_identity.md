# GlyphCue — Milestone 13: Frozen Build-Base Identity

**Document type:** Authoritative frozen build-base record for the Minimum Runtime-Fidelity Packaging Experiment  
**Governing issues:** [#17](https://github.com/Peter-S-Shi/glyphcue/issues/17), [#20](https://github.com/Peter-S-Shi/glyphcue/issues/20), [#21](https://github.com/Peter-S-Shi/glyphcue/issues/21), [#24](https://github.com/Peter-S-Shi/glyphcue/issues/24), [#25](https://github.com/Peter-S-Shi/glyphcue/issues/25), [#26](https://github.com/Peter-S-Shi/glyphcue/issues/26), [#27](https://github.com/Peter-S-Shi/glyphcue/issues/27)  
**Trusted Source Commit:** `5905df09d012cb63a34b98c484b43958477e52e8`  
**Target Branch:** `milestone/13-release-candidate`  
**Date:** 2026-09-05  

---

## 1. Executive Summary

This document freezes all inputs, toolchain specifications, native artifact hashes, model identities, the complete 85-package wheel artifact set, and the deterministic synthetic test fixture for the **GlyphCue V1 Minimum Runtime-Fidelity Packaging Experiment**.

Both required clean reconstructions (Reconstruction 1 and Reconstruction 2) and all subsequent offline runtime validation environments must consume these exact frozen identities. No dynamic or unpinned package resolution is permitted.

---

## 2. Windows Build-Base & Toolchain Identity

| Property / Tool | Frozen Specification | Status |
|---|---|---|
| **Host Reconstruction OS** | Microsoft Windows 11 Home 10.0.26200 (Build 26200, 64-bit) | Verified |
| **Supported V1 Target OS** | Windows 11 x64 (Build 22000+) | Supported V1 Release Target |
| **DirectML Technical Floor** | Windows 10 Build 19041+ (DirectML D3D12 Feature Level 11_0+ API minimum floor — technical reference only; not a supported V1 target OS) | Reference Only |
| **Python Runtime** | CPython 3.12.10 (AMD64) | Frozen |
| **Installer Compiler** | Inno Setup 6.3.3 (`ISCC.exe` x64, per-user `{localappdata}\Programs\GlyphCue`) | Frozen |
| **Code Signing Mechanism** | Windows SDK SignTool 10.0.26100.0 / PowerShell Authenticode API (Win11 Build 26200) | Frozen |
| **Approved Test Certificate Subject** | `CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root` | Frozen |
| **CycloneDX Generator Tool** | `cyclonedx-py 5.1.1` (`specVersion: "1.6"`) via `tools/packaging/generate_cyclonedx_sbom.py` | Frozen |
| **Drift Comparator** | `tools/packaging/verify_payload_drift.py v1.2.0` | Frozen |

---

## 3. Content-Addressed Local Staging & Cache Contract

To prevent Phase B from silently resolving or downloading newer artifacts:

1. **Download Cache Layout:** `<cache_root>/downloads/{sha256}/{filename}`
2. **Unpacked Wheel Cache:** `<cache_root>/unpacked_wheels/{sha256}/`
3. **Staging App Root:** `<staging_root>/app_root`
4. **Enforcement Rule:** Before extracting any wheel or Python archive, the assembly process must compute and verify the SHA-256 hash against `docs/m13_build_base_identity.json`. Any mismatch or untracked package immediately aborts the assembly as a **FAIL / NEEDS REVIEW**.

---

## 4. Frozen Runtime & Artifact Identities

### 4.1 CPython 3.12.10 Embeddable Runtime
- **Archive Filename:** `python-3.12.10-embed-amd64.zip`
- **Source URL:** `https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip`
- **Size (Bytes):** `11,133,606`
- **SHA-256 Hash:** `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`
- **Verification Source:** Official python.org sigstore / SHA-256 release record.

### 4.2 ONNX Model Artifacts
| Model Filename | Size (Bytes) | SHA-256 Hash | Role / Status |
|---|---|---|---|
| `PP-OCRv6_det_medium.onnx` | 62,119,454 | `92078b7355007ccfffcd4c8cd441a3afd4538904d06881b29a155e1e679907c2` | PP-OCRv6 Text Detector (Medium profile) — Authoritative Production Candidate per #20/#26; `verification_status: unresolved` (Release Redistribution Compliance Gate OPEN downstream) |
| `PP-OCRv6_rec_small.onnx` | 21,234,383 | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` | PP-OCRv6 Text Recognizer (Small profile); `verification_status: unresolved` |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | 585,532 | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` | Text Direction Classifier (Mobile profile); `verification_status: unresolved` |

### 4.3 Critical Native DLLs
| Binary File | Size (Bytes) | SHA-256 Hash | Origin Wheel |
|---|---|---|---|
| `DirectML.dll` | 18,527,776 | `b73972115320e906a49602f2027a3266622881b0d325ba685e0f165a9482a8d7` | `onnxruntime_directml-1.24.4-cp312-cp312-win_amd64.whl` |
| `onnxruntime.dll` | 21,111,832 | `302c69f9779d63ef4ab90316e59444c4acbaca7fe3455020d79d10bcfcb00715` | `onnxruntime_directml-1.24.4-cp312-cp312-win_amd64.whl` |
| `qwindows.dll` | 991,032 | Dynamic (Qt QPA plugin) | `PySide6-6.11.2-cp310-abi3-win_amd64.whl` |
| `ffmpegmediaplugin.dll` | 701,752 | Dynamic (Qt Multimedia plugin) | `PySide6-6.11.2-cp310-abi3-win_amd64.whl` |
| `qsqlite.dll` | 1,986,872 | Dynamic (Qt SQL plugin) | `PySide6-6.11.2-cp310-abi3-win_amd64.whl` |

### 4.4 Database SQL Migrations
| Migration File | Size (Bytes) | SHA-256 Hash |
|---|---|---|
| `0001_create_cues.sql` | 137 | `823d7aa7551f3c3fc3e61683f4e23699eef6438efd09a564f8b7e3b1ab2d05ff` |
| `0002_create_language_layers.sql` | 250 | `be845d70da4be9c960b879ceb5e41192c1ec585940ab4f7c0f8c4626fd5f974a` |
| `0003_create_track_groups.sql` | 193 | `4c2d162d65b48ef558552849cf04fa2c5c69d377a408ca7d85e00eb6bb9a3118` |
| `0004_create_observations.sql` | 531 | `8c578d6bc72ac86ee8fd1e1015875e3b77e98578692d97b23df6b278ec4f1de0` |
| `0005_add_source_id_to_cues_and_observations.sql` | 284 | `7c821706ab1c45dc7b30823e1e874bcb0f265d51e14702bed9c75039dfef7ed7` |

---

## 5. Complete Frozen Wheel Artifact Inventory (85 Packages)

The full machine-readable wheel inventory is recorded in `docs/m13_build_base_identity.json`. Below are the representative core packages and their exact wheel SHA-256 hashes:

| Package | Version | Exact Artifact Filename | SHA-256 Hash |
|---|---|---|---|
| `onnxruntime-directml` | 1.24.4 | `onnxruntime_directml-1.24.4-cp312-cp312-win_amd64.whl` | `f2ecb68b7b7b259d2ef3112ae760149f9b5a1e7c0fbb73d539da6250a648a614` |
| `PySide6` | 6.11.2 | `PySide6-6.11.2-cp310-abi3-win_amd64.whl` | `5c1f0b0946288338f0d8a4f001c9aeb71fa284fae101372ec09c647b590e0b3c` |
| `PySide6_Essentials` | 6.11.2 | `PySide6_Essentials-6.11.2-cp310-abi3-win_amd64.whl` | `da7cbe22b5282245b08c9d09c6475654316a7590890641b433cfb97c8db054e0` |
| `shiboken6` | 6.11.2 | `shiboken6-6.11.2-cp310-abi3-win_amd64.whl` | `bf81be0a1e05d9c72ec1eb87bf23f03b5ecdf8bb7b3543d463870634ee1ef8f4` |
| `av` (PyAV) | 18.1.0 | `av-18.1.0-cp312-cp312-win_amd64.whl` | `ca07185016e75924dd1804fcaeb4d1f2b6e1ee7e12720bf2ad39316715f5c35b` |
| `numpy` | 2.3.5 | `numpy-2.3.5-cp312-cp312-win_amd64.whl` | `265a882a84d436cf4df24a520a3206cbf66fc568bca2ebc4d29f0450fa2e8964` |
| `rapidocr` | 3.9.2 | `rapidocr-3.9.2-py3-none-any.whl` | `10f22ffcbfd80d287bf742ff15004ec9092fc0a312bb0ff0f3fafeefbc97b79d` |
| `paddleocr` | 3.7.0 | `paddleocr-3.7.0-py3-none-any.whl` | `7bebb1d556fe3c5d80410714ee6b9dc70377c8e96bf7d84f8ee96f42d2a4e908` |
| `paddlepaddle` | 3.3.1 | `paddlepaddle-3.3.1-cp312-cp312-win_amd64.whl` | `7d7cb919245155f653457a419eb315998a6984e72750e5015e1fe746a5d78a87` |
| `paddlex` | 3.7.2 | `paddlex-3.7.2-py3-none-any.whl` | `6a8047ce5ca5e9d9976bb2d3ca45efd9ef25bf789233f27f0da16672323f46f4` |
| `opencv-contrib-python` | 4.10.0.84 | `opencv_contrib_python-4.10.0.84-cp37-abi3-win_amd64.whl` | `1b8584ea0bc84d19d6512e03597d3910f2bbd725656123a07a166a0d0a75f101` |
| `pyclipper` | 1.4.0 | `pyclipper-1.4.0-cp312-cp312-win_amd64.whl` | `4f3f4c6e917d59ebfefc5a089a5c88bdaeaee22cf8b2b627464e8b3e8e2c4515` |
| `pypdfium2` | 5.13.0 | `pypdfium2-5.13.0-py3-none-win_amd64.whl` | `7b7cb1d7e2f50c05fe9e3f6dc1839e9921eef00c71a38b14a275fdf0eb38c64c` |
| `shapely` | 2.1.2 | `shapely-2.1.2-cp312-cp312-win_amd64.whl` | `7be26b55ae245dfa6bcf33890f55cf6493dc35f11e956487e35b7194f1c9c7f1` |
| `python-bidi` | 0.6.11 | `python_bidi-0.6.11-cp312-cp312-win_amd64.whl` | `246df16e9b46dfa69527ec47a61d1ea00d14b4ae4465495c65f973359d9cce54` |
| `antlr4-python3-runtime` | 4.9.3 | `antlr4-python3-runtime-4.9.3.tar.gz` | `f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b` |

---

## 6. Deterministic Synthetic Test Fixture

- **Generator Recipe:** `tools/packaging/generate_synthetic_fixture.py`
- **Output Filename:** `glyphcue_synthetic_fixture_v1.mp4`
- **Duration / Dimensions:** 6.0 seconds (60 frames at 10 fps), 1280x720, MP4 container (`mp4v`).
- **File Size:** `183,789` bytes
- **SHA-256 Hash:** `72a7621639730b62b5a06a266499ea66768df277cad15553cab6d2487b972465`
- **Golden Reference Output:** `docs/m13_synthetic_fixture_golden.json` (3 reconstructed cues with millisecond timestamps and confidence metrics).
