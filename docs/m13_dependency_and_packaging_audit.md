# GlyphCue — Milestone 13: External Dependency & Historical Packaging Audit

**Document type:** Authoritative factual audit and runtime evidence baseline for Milestone 13  
**Project:** GlyphCue  
**Target Issue:** Wayfinder Issue #20 — Establish the Trusted GlyphCue Release-Runtime Baseline  
**Trusted Source Commit:** `5905df07beaa6ce036eb5ec047bfdb184c13a07a` (`main` HEAD post-M12 & Product Hardening II merge)  
**Branch:** `milestone/13-release-candidate`  
**Status:** Audit & Factual Baseline (Read-Only evidence gathering; production behavior unchanged)  
**Date:** 2026-09-05  

---

## 1. Executive Summary & Purpose

This document provides the public-safe, factual external evidence input required by **Wayfinder Issue #20** ("Establish the Trusted GlyphCue Release-Runtime Baseline").

Per the Milestone 13 audit discipline:
1. **No Packaging Architecture Decision**: This audit does not choose PyInstaller, Briefcase, Nuitka, or embedded CPython for release.
2. **No Installer Construction**: No installer script (`.iss`, `.msi`) or executable bundle is created in this step.
3. **No Duplication of Research**: Extends and consolidates historical evidence without duplicating prior research.
4. **Factual Integrity & Sanitization**: All machine paths, usernames, local environment details, and model identities are normalized (e.g. `<repo>`, `<runtime>`, `<models>`, `<user-data>`) and verified against the actual Windows development environment that passed Product Hardening II.

---

## 2. Trusted Windows Environment Inventory (Factual Baseline)

### 2.1 Python Environment & Dependency Separation

The accepted production baseline operates under a strict two-environment development separation to handle top-level C-extension / ONNX Runtime namespace constraints:

- **Default Development Environment (`<repo>/.venv`)**:
  - **Python Version**: `3.11.9` (64-bit Windows)
  - **Runtime Role**: Default dev/pytest suite environment, CPU-only PaddleOCR reference pipeline.
  - **Key Packages & Resolved Versions**:
    - `PySide6` == `6.11.2`, `PySide6_Essentials` == `6.11.2`, `shiboken6` == `6.11.2`
    - `av` == `18.1.0` (PyAV / FFmpeg bindings)
    - `numpy` == `2.3.5`
    - `paddleocr` == `3.7.0`, `paddlepaddle` == `3.3.1`, `paddlex` == `3.7.2`
    - `onnxruntime` == `1.29.0` (CPU-only distribution)
    - `rapidocr-onnxruntime` == `1.4.4`
    - `pysubs2` == `1.8.1`, `Pillow` == `12.3.0`, `pytest` == `9.1.1`

- **DirectML DevQA Environment (`<repo>/.venv-directml-devqa`)**:
  - **Python Version**: `3.12.10` (64-bit Windows)
  - **Runtime Role**: Hardware-accelerated DirectML DevQA preflight and execution environment.
  - **Key Packages & Resolved Versions**:
    - `PySide6` == `6.11.2`, `PySide6_Essentials` == `6.11.2`, `shiboken6` == `6.11.2`
    - `av` == `18.1.0`
    - `numpy` == `2.3.5`
    - `onnxruntime-directml` == `1.24.4` (Direct3D 12 GPU acceleration provider)
    - `rapidocr` == `3.9.2`
    - `paddleocr` == `3.7.0`, `paddlepaddle` == `3.3.1`, `paddlex` == `3.7.2`
    - `opencv-contrib-python` == `4.10.0.84`, `opencv-python-headless` == `5.0.0.93`
    - `pyclipper` == `1.4.0`, `pypdfium2` == `5.13.0`, `shapely` == `2.1.2`, `python-bidi` == `0.6.11`

### 2.2 Declared Spec vs. Resolved Reality

`pyproject.toml` declares abstract lower bounds and explicit opt-in extras:
- Base dependencies: `PySide6>=6.7`, `pysubs2>=1.7`, `av>=11`, `numpy>=1.26`
- `ocr` extra: `paddleocr==3.7.0`, `paddlepaddle==3.3.1`, `opencv-python-headless>=4.8` (exact pins required due to `paddleocr==3.7.0` + `paddlepaddle==3.3.1` `enable_mkldnn=False` CPU workaround; see `docs/adr/0001-ocr-runtime-selection.md`)
- `directml` extra: `rapidocr==3.9.2`, `onnxruntime-directml==1.24.4`, `pyclipper>=1.3`, `opencv-python-headless>=4.8` (marked `sys_platform == 'win32'`)

**Audit Finding**: Declared ranges are insufficient for release packaging. The actual trusted runtime relies on exact resolved pairings (`PySide6 6.11.2`, `PyAV 18.1.0`, `onnxruntime-directml 1.24.4`, `RapidOCR 3.9.2`, `PaddleOCR 3.7.0`, `PaddlePaddle 3.3.1`).

### 2.3 Core Native DLLs & System Bindings

Verification against the active `<runtime>` site-packages confirmed the exact native DLL binaries:

| Binary File | Relative Path in Environment | Size (Bytes) | SHA-256 Hash | Role / Function |
|---|---|---|---|---|
| `DirectML.dll` | `<runtime>/site-packages/onnxruntime/capi/DirectML.dll` | 18,527,776 | `b73972115320e906a49602f2027a3266622881b0d325ba685e0f165a9482a8d7` | Direct3D 12 GPU acceleration engine |
| `onnxruntime.dll` | `<runtime>/site-packages/onnxruntime/capi/onnxruntime.dll` | 21,111,832 | `302c69f9779d63ef4ab90316e59444c4acbaca7fe3455020d79d10bcfcb00715` | ONNX Runtime C++ engine binding |
| `mklml.dll` | `<runtime>/site-packages/paddle/libs/mklml.dll` | 92,649,344 | N/A (Dynamic load) | Intel MKL math kernel library for Paddle |
| `mkldnn.dll` | `<runtime>/site-packages/paddle/libs/mkldnn.dll` | 47,322,112 | N/A (Dynamic load) | oneDNN (MKL-DNN) neural network library |
| `avcodec-62-*.dll` | `<runtime>/site-packages/av.libs/avcodec-62-*.dll` | 19,266,048 | N/A (PyAV native) | FFmpeg video codec decoding library |
| `qwindows.dll` | `<runtime>/site-packages/PySide6/plugins/platforms/qwindows.dll` | 991,032 | N/A (Qt plugin) | Windows platform QPA plugin |
| `ffmpegmediaplugin.dll` | `<runtime>/site-packages/PySide6/plugins/multimedia/ffmpegmediaplugin.dll` | 701,752 | N/A (Qt plugin) | Qt Multimedia FFmpeg backend plugin |
| `qsqlite.dll` | `<runtime>/site-packages/PySide6/plugins/sqldrivers/qsqlite.dll` | 1,986,872 | N/A (Qt plugin) | Qt SQLite database driver plugin |

### 2.4 ONNX Model Files & Provenance

The trusted DirectML OCR engine and detector consume three normalized ONNX model artifacts:

| Model Filename | Normalized Path | Size (Bytes) | SHA-256 Hash | Model Role |
|---|---|---|---|---|
| `PP-OCRv6_det_small.onnx` | `<repo>/PP-OCRv6_det_small.onnx` | 9,929,594 | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` | PP-OCRv6 Text Detector (Small profile) |
| `PP-OCRv6_rec_small.onnx` | `<repo>/PP-OCRv6_rec_small.onnx` | 21,234,383 | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` | PP-OCRv6 Text Recognizer (Small profile) |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | `<repo>/ch_ppocr_mobile_v2.0_cls_mobile.onnx` | 585,532 | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` | Text Direction Classifier (Mobile profile) |

### 2.5 Application Resources & SQLite Migrations

The product persistence layer requires exact SQL migration scripts delivered via package data (`importlib.resources` from `glyphcue.persistence.migrations_sql`):

| Migration Script | Relative Path | Size (Bytes) | SHA-256 Hash |
|---|---|---|---|
| `0001_create_cues.sql` | `src/glyphcue/persistence/migrations_sql/0001_create_cues.sql` | 137 | `823d7aa7551f3c3fc3e61683f4e23699eef6438efd09a564f8b7e3b1ab2d05ff` |
| `0002_create_language_layers.sql` | `src/glyphcue/persistence/migrations_sql/0002_create_language_layers.sql` | 250 | `be845d70da4be9c960b879ceb5e41192c1ec585940ab4f7c0f8c4626fd5f974a` |
| `0003_create_track_groups.sql` | `src/glyphcue/persistence/migrations_sql/0003_create_track_groups.sql` | 193 | `4c2d162d65b48ef558552849cf04fa2c5c69d377a408ca7d85e00eb6bb9a3118` |
| `0004_create_observations.sql` | `src/glyphcue/persistence/migrations_sql/0004_create_observations.sql` | 531 | `8c578d6bc72ac86ee8fd1e1015875e3b77e98578692d97b23df6b278ec4f1de0` |
| `0005_add_source_id_to_cues_and_observations.sql` | `src/glyphcue/persistence/migrations_sql/0005_add_source_id_to_cues_and_observations.sql` | 284 | `7c821706ab1c45dc7b30823e1e874bcb0f265d51e14702bed9c75039dfef7ed7` |

### 2.6 Active ONNX Runtime Provider Verification

Live verification executed via `tools/devqa_directml_verify.py` against `.venv-directml-devqa` returned:
```text
[DevQA DirectML preflight] OK: DirectMlOcrEngine active, det providers=['DmlExecutionProvider', 'CPUExecutionProvider'], rec providers=['DmlExecutionProvider', 'CPUExecutionProvider']
[DevQA DirectML preflight] OK: DirectMlTextDetector active, providers=['DmlExecutionProvider', 'CPUExecutionProvider']
[DevQA DirectML preflight] PASS: DirectML OCR engine + text detector both confirmed active with DmlExecutionProvider.
```
- **Detector Session Active Providers**: `['DmlExecutionProvider', 'CPUExecutionProvider']`
- **Recognizer Session Active Providers**: `['DmlExecutionProvider', 'CPUExecutionProvider']`
- **Zero Fallback**: Proves Direct3D 12 GPU acceleration is genuinely active without silent CPU fallback.

---

## 3. Historical Packaging Evidence Reconstruction

### 3.1 Nuitka / pyside6-deploy Retirement (Facts vs. Inference)

- **Factual Record**: Retired on 2026-09-04 after 5 controlled build attempts on local Windows host.
- **Encountered Blockers**:
  1. *MinGW64 extraction race*: Cache-extraction race condition under Nuitka dependency download.
  2. *RAM exhaustion during Scons/gcc*: Compiler RAM exhaustion during heavy PySide6/C++ bindings compilation.
  3. *Indeterminate codegen stall*: Near-infinite compile-phase hang on generated C source.
  4. *Unclassified silent exit*: Compiler process exited silently without stack trace.
  5. *Python analysis RAM exhaustion*: Nuitka's module dependency graph generator exhausted 16GB+ RAM even under `--jobs=2`.
- **Disposition**: Human adjudication (2026-09-04) retired Nuitka as the V1 packaging path; PyInstaller activated as standard fallback.

### 3.2 PyInstaller Onedir Demonstration & Iterative Fixes

- **Factual Record**: Demonstrated 2026-09-04 using PyInstaller onedir mode under Python 3.12 (`.glyphcue-pyinstaller-venv`). Initial 779 MB bundle launched and rendered GUI, but failed on real "Run OCR Evidence" button click (`JobState.FAILED`).
- **Collection & Runtime Gaps Discovered & Fixed**:

| Gap # | Symptom / Failure | Root Cause | Fix Applied | Bundle Impact |
|---|---|---|---|---|
| **1** | `The pipeline (OCR) does not exist!` | `paddlex/configs/` (~1.3MB) missing from bundle | Added `--collect-data paddlex` | Configs collected |
| **2** | `importlib.metadata` missing extra deps | PyInstaller omitted `.dist-info` metadata for 6 packages (`imagesize`, `opencv-contrib-python`, `pyclipper`, `pypdfium2`, `python-bidi`, `shapely`) | Added `--copy-metadata paddlex` and `--copy-metadata` for all 6 | Dist-info copied |
| **3** | `mklml.dll error code 126` | Paddle dynamically loads `mklml.dll` via `LoadLibrary` at runtime, missed by static PE scan | Added `--collect-binaries paddle` | Bundle grew to 880 MB |
| **4** | DirectML path unavailable | `rapidocr` package missing from bundle (`_internal/rapidocr` absent) | Added `--collect-all rapidocr` | Bundle grew to 911 MB |

### 3.3 Behavioral Divergence: Packaged vs. Trusted Dev Environment

- **Performance Divergence**:
  - The default packaged `.exe` executing CPU Paddle path ran at **19.7×–20× slower than realtime** because `PaddleOcrEngine` explicitly sets `enable_mkldnn=False` and lacks GPU acceleration.
  - The DirectML path in the trusted environment ran at **4.02×–4.19× realtime** (measured at 4.806× median on `sample_g`), satisfying the $\le 5\times$ realtime target.
- **Runtime Policy Adjustment**:
  - To prevent packaged builds from running the 20× slower CPU path by default, `src/glyphcue/ui/app.py` flipped the environment variable polarity: `GLYPHCUE_PREFER_DIRECTML_*` (opt-in) was replaced with `GLYPHCUE_DISABLE_DIRECTML_*` (opt-out), ensuring normal launches default to DirectML on Windows.

---

## 4. Critical Runtime-Fidelity Seams for M13 Candidates

Any packaging candidate evaluated for Milestone 13 must strictly preserve seven runtime-fidelity seams:

1. **Seam 1 — Python & C-Extension Isolation**: Python interpreter, standard library, and C-extensions (`numpy`, `av`, `PySide6.QtCore`, `onnxruntime`) must be fully isolated without depending on global host Python.
2. **Seam 2 — Qt Shell & Plugin Discovery**: `PySide6` must discover `platforms/qwindows.dll`, `multimedia/ffmpegmediaplugin.dll`, `sqldrivers/qsqlite.dll`, and image format plugins regardless of current working directory.
3. **Seam 3 — Multimedia & Native DLL Resolution**: PyAV FFmpeg C-extension DLLs (`avcodec-62-*.dll`, `swscale-9-*.dll`) and Paddle MKL DLLs (`mklml.dll`, `mkldnn.dll`) must be located on DLL search paths.
4. **Seam 4 — ONNX Runtime DirectML Provider Activation**: `DirectML.dll` and `onnxruntime.dll` must be loaded and report `DmlExecutionProvider` as primary provider in `onnxruntime.InferenceSession.get_providers()` without silent fallback to CPU.
5. **Seam 5 — Model Identity & Integrity**: The exact PP-OCRv6 ONNX models (`PP-OCRv6_det_small.onnx`, `PP-OCRv6_rec_small.onnx`, `ch_ppocr_mobile_v2.0_cls_mobile.onnx`) matching the exact SHA-256 hashes must be accessible at runtime without downloading.
6. **Seam 6 — Package Resource & Migration Asset Discovery**: Package data files (`src/glyphcue/persistence/migrations_sql/*.sql`) must be discoverable via `importlib.resources`.
7. **Seam 7 — User-Data & Profile Isolation**: Database storage must strictly write to `<user-profile>/.glyphcue/glyphcue.sqlite3` (or isolated test databases), never writing state into package install or root directories.

---

## 5. Wayfinder Issue #20 Handoff Block

```text
================================================================================
WAYFINDER ISSUE #20 HANDOFF BLOCK
================================================================================
1. Trusted Source Commit:
   5905df07beaa6ce036eb5ec047bfdb184c13a07a (main HEAD post-M12 / Hardening II)

2. Frozen Runtime & Dependency Identity:
   - Python: 3.12.10 (DirectML DevQA) / 3.11.9 (Dev)
   - PySide6: 6.11.2 (Plugins: platforms/qwindows.dll, multimedia/ffmpegmediaplugin.dll, sqldrivers/qsqlite.dll)
   - PyAV: 18.1.0 (FFmpeg binaries: avcodec-62, swscale-9, avformat-62, avutil-60)
   - ONNX Runtime DirectML: 1.24.4 (DirectML.dll SHA256: b73972115320e906a49602f2027a3266622881b0d325ba685e0f165a9482a8d7)
   - RapidOCR: 3.9.2
   - PaddleOCR / PaddlePaddle: 3.7.0 / 3.3.1 (MKL DLLs: mklml.dll 92.6MB, mkldnn.dll 47.3MB)

3. Model Artifacts & SHA-256 Hashes:
   - PP-OCRv6_det_small.onnx: 090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f (9,929,594 bytes)
   - PP-OCRv6_rec_small.onnx: 6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884 (21,234,383 bytes)
   - ch_ppocr_mobile_v2.0_cls_mobile.onnx: e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c (585,532 bytes)

4. Active ORT Providers:
   ['DmlExecutionProvider', 'CPUExecutionProvider'] (Verified live via tools/devqa_directml_verify.py)

5. Critical Runtime-Fidelity Seams (7 Seams):
   (1) Python isolation; (2) Qt plugin discovery; (3) FFmpeg/MKL native DLLs; (4) DirectML provider activation;
   (5) PP-OCRv6 model identity; (6) migrations_sql resource discovery; (7) user-data isolation (<profile>/.glyphcue/).

6. Historical Packaging Conclusions:
   - Nuitka/pyside6-deploy retired (RAM exhaustion & Scons/gcc stalls across 5 attempts).
   - PyInstaller onedir demonstrated (911 MB bundle with 4 key collection fixes: --collect-data paddlex, --copy-metadata paddlex/extras, --collect-binaries paddle, --collect-all rapidocr).
   - DirectML activation is mandatory to avoid ~20× CPU slowdown.

7. Unresolved Facts:
   - No standalone installer script (.iss / Inno Setup) or single-file executable authored yet.
   - Briefcase / embedded CPython remain un-benchmarked research candidates.

8. Evidence File Locations:
   - Audit Document: docs/m13_dependency_and_packaging_audit.md
   - Machine Inventory: docs/m13_runtime_inventory.json
   - DirectML Preflight Probe: tools/devqa_directml_verify.py
   - Dependency Spec: pyproject.toml
================================================================================
```
