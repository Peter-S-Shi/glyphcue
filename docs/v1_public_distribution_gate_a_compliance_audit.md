# GlyphCue v1.0.0 Public Distribution Gate — Gate A: Redistribution & Licensing Compliance Audit

**Document type:** Authoritative public-safe compliance matrix
**Target Issue:** #30 — GlyphCue v1.0.0 Public Distribution Gate
**Branch:** `release/1.0.0-public-distribution`, based exactly on M13-closed `main` @ `4adbb6c4679b40220c07b01fb46969722138fd35`
**Status:** Gate A audit only. No code, packaging, runtime, or product behavior changed. No rebuild, no tag, no GitHub Release performed.
**Date:** 2026-09-06

---

## 1. Scope & Method

This audit examines the **actual, real M13 release payload** already assembled and Owner-validated during Phase F, not a hypothetical or re-derived one:

- **Frozen build inventory:** `docs/m13_build_base_identity.json` (85 frozen wheel/sdist artifacts, CPython embeddable runtime, 3 ONNX models, 2 Paddle CPU model archives, toolchain identities).
- **Real corrective `app_root`:** `build_artifacts/phase_f/f3_corrective/app_root/` — the exact tree Owner Runtime-Write/F3/F4 evidence was collected against, with its manifest/SBOM subsequently reconciled to real launcher provenance (PR #28). 21,718 files, integrity gate PASS, 0 missing/mismatched.
- **Payload manifest & SBOM:** `build_artifacts/phase_f/f3_corrective/app_root/legal/manifest/payload_manifest.json` and `sbom.json` (CycloneDX 1.6, 116 components).
- **Per-wheel `.dist-info/METADATA`** license declarations, read directly from the assembled `lib/` tree (not re-derived from PyPI listings alone).
- **Actual on-disk binaries** under `app_root/lib`, `app_root/qt`, and `app_root/models` — physically inspected for which native libraries are truly present, not merely which Python packages are declared as dependencies.
- **External, authoritative upstream sources** (Qt's own licensing documentation, PaddleOCR/RapidOCR's own publication pages, Microsoft's DirectML repository) fetched and cited per finding, per this task's instruction not to rely on "Paddle is Apache-2.0"-style shorthand.
- **Prior internal research:** `docs/asr_licensing_research.md` (2026-09-04) had already flagged, as a prediction, that "the FFmpeg license carried by a PyAV wheel depends on the exact binary build" and must never be inferred from PyAV's own BSD metadata. §4.1 below confirms that prediction was correct and finds the concrete instance.

No rebuild was performed. No runtime or packaging code was touched. This is a read-only audit of what is already built and already Owner-validated.

---

## 2. Compliance Matrix

| Component family | Packaged identity / version | Upstream / source provenance | Governing license | Redistribution permitted? | Obligations | Where obligations must ship |
|---|---|---|---|---|---|---|
| **CPython embeddable runtime** | `python-3.12.10-embed-amd64.zip`, SHA-256 `4acbed6d...25a3c3` | `python.org` official release | PSF License Agreement (Python Software Foundation) | **Yes** — PSF License explicitly permits redistribution of binary builds | Retain Python's own `LICENSE.txt` / copyright notice | Inside installed app (`python/` dir already carries CPython's own license files) |
| **PySide6 + PySide6-Addons + PySide6-Essentials + shiboken6** | `6.11.2` | PyPI wheels, built by The Qt Company / PySide project | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` (per wheel `METADATA`) | **Yes, under LGPL-3.0**, because GlyphCue links to Qt/PySide6 **dynamically** (separate `.dll`/`.pyd` files loaded by the Python launcher, never statically merged) — the standard LGPL compliance pattern | (a) LGPL notice + copy of LGPLv3 text; (b) written offer or means for the end user to relink/replace the Qt libraries (satisfied structurally: Qt binaries are separate files under `app_root/lib` and `app_root/qt`, not embedded in `GlyphCue.exe`); (c) attribution for all third-party code Qt itself carries (see `qt/licenses` folder Qt ships internally, or Qt's own "Licenses Used in Qt" page) | Inside installed app (license text + notices alongside the Qt binaries) **and** repository/release notes (attribution list) |
| **Qt WebEngine / Qt Charts / Qt Data Visualization** (bundled via PySide6-Addons, `Qt6WebEngineCore.dll`, `QtWebEngineProcess.exe`, `Qt6Charts.dll`, `Qt6DataVisualization.dll`, etc. — physically present in `app_root/lib/PySide6/`) | `6.11.2` (same wheel as above) | The Qt Company | **Verified via `doc.qt.io/qt-6/licensing.html`**: Qt WebEngine, Qt Charts, and Qt Data Visualization are **not** on Qt 6's "GPL v3 only" module list (that list is: Qt Canvas Painter, Qt CoAP, Qt Graphs, Qt GRPC, Qt HTTP Server, Qt Lottie Animation, Qt MQTT, Qt Network Authorization, Qt Qml Compiler, Qt Quick 3D, Qt Quick 3D Physics, Qt Quick Timeline, Qt Virtual Keyboard, Qt Wayland Compositor). Qt WebEngine's Qt-specific parts are confirmed dual/triple-licensed the same as PySide6 itself (Commercial or LGPLv3/GPLv3/GPLv2); its bundled Chromium snapshot's most restrictive component license is LGPL-2.1, not GPL. | **Yes, under LGPL**, same as core PySide6 — **this is a correction of an initial hypothesis** (older Qt5-era assumptions treated WebEngine/Charts/DataViz as GPL-only; that is no longer accurate for the Qt 6.11 wheels actually shipped) | Same LGPL obligations as above, **plus** Qt WebEngine's own extensive third-party notices (Chromium carries dozens of sub-component licenses; Qt publishes these at `doc.qt.io/qt-6/qtwebengine-3rdparty-*.html`) if this module ships | Inside installed app + repository/release notes | 
| **⚠️ Action item:** GlyphCue's own source code never imports `QtWebEngine`, `QtCharts`, or `QtDataVisualization` (`grep -rn` over `src/` returns zero hits) — these binaries are dead weight, physically present only because `PySide6-Addons` is unpacked wholesale (`zf.extractall`) with no module pruning. Not a license violation (LGPL confirmed above) but adds real payload size and a real, unnecessary attribution surface (Chromium's own third-party notices). **Recommend stripping unused Qt Addon modules at packaging time** before public distribution, both for size and to shrink the notice surface to what's actually shipped. | | | | | | |
| **Qt Multimedia FFmpeg backend** (`ffmpegmediaplugin.dll` + `app_root/lib/PySide6/avcodec-61.dll`, `avformat-61.dll`, `avutil-59.dll`, `swresample-5.dll`, `swscale-8.dll`) | Qt's own FFmpeg 7.1.x-class build, bundled inside PySide6-Addons `6.11.2` | Qt Company, per `doc.qt.io/qt-6/qtmultimedia-attribution-ffmpeg.html` | FFmpeg: LGPLv2.1-or-later. **Verified via Qt's own documentation**: "the binaries that ship with Qt ... do not contain [GPL/LGPLv3-only optional] components" — Qt's FFmpeg build is confirmed the LGPL-clean build, no libx264/libx265/GPL codecs | **Yes, under LGPL-2.1+** | FFmpeg copyright/license notice; dynamic linking already satisfied (separate DLLs, confirmed on disk, not statically merged) | Inside installed app |
| **🔴 PyAV's own bundled FFmpeg build** (`app_root/lib/av.libs/avcodec-62-*.dll`, `avformat-62-*.dll`, etc. — a **second, independent** FFmpeg build shipped alongside Qt's own) | PyAV `18.1.0` Windows wheel's vendored FFmpeg | PyAV project (`pyav.org`) | PyAV's own code: BSD-3-Clause (confirmed, `av-18.1.0.dist-info/METADATA`). **The vendored FFmpeg binaries are a separate matter — verified by direct binary inspection, not inferred from PyAV's BSD license**: `app_root/lib/av.libs/` physically contains `libx264-165-*.dll` and `libx265-*.dll`. **libx264 and libx265 are GPL-2.0-or-later encoders.** Their presence means this specific FFmpeg build was compiled with `--enable-gpl --enable-libx264 --enable-libx265`, making **this FFmpeg binary a GPL build**, not the LGPL-only build Qt uses. | **BLOCKING as currently packaged** — shipping a GPL-licensed FFmpeg build inside a proprietary/unlicensed application (see governance question #1, §5) risks obligating the combined work under GPL, per FFmpeg's own published redistribution guidance | **Verified dead code**: `grep -rn "av\.open\|add_stream\|\.encode(\|container\.mux" src/glyphcue/` shows GlyphCue's only PyAV usage (`src/glyphcue/adapters/pyav_media_source.py`) is `av.open(path)` in **read-only decode mode** — GlyphCue never encodes video and never calls into libx264/libx265 at all. | **Minimum fix: strip `libx264-*.dll` and `libx265-*.dll` from the shipped payload** (and any packaging step that vendors them), or replace the PyAV wheel with an LGPL-only-FFmpeg build. This removes the GPL risk entirely without any behavior change, since the encoder codecs are provably unused. |
| **ONNX Runtime (DirectML build)** | `onnxruntime-directml` `1.24.4`, `onnxruntime.dll` | PyPI wheel, Microsoft | MIT License (confirmed, `onnxruntime_directml-1.24.4.dist-info/METADATA`) | **Yes** | Retain MIT notice | Inside installed app |
| **DirectML.dll** | bundled inside `onnxruntime_directml-1.24.4` wheel, SHA-256 `b7397211...9482a8d7` | Microsoft, `microsoft/DirectML` GitHub repo | **Verified via `github.com/microsoft/DirectML/blob/master/LICENSE`**: MIT License | **Yes** | Retain MIT notice | Inside installed app |
| **PaddlePaddle (framework)** | `paddlepaddle` `3.3.1` | PyPI wheel, PaddlePaddle project | Apache License 2.0 (confirmed, `paddlepaddle-3.3.1.dist-info/METADATA`) | **Yes** | Apache-2.0 NOTICE + license text | Inside installed app |
| **PaddleOCR / PaddleX (code)** | `paddleocr` `3.7.0`, `paddlex` `3.7.2` | PyPI wheels, PaddlePaddle project | Apache-2.0 (confirmed, both `.dist-info/METADATA`) | **Yes** | Apache-2.0 NOTICE | Inside installed app |
| **RapidOCR (code)** | `rapidocr` `3.9.2` | PyPI wheel, `RapidAI/RapidOCR` | Apache-2.0 (confirmed, `rapidocr-3.9.2.dist-info/METADATA` — `License-Expression: Apache-2.0`) | **Yes** | Apache-2.0 NOTICE | Inside installed app |
| **OpenCV** | `opencv-python` `5.0.0.93`, `opencv-contrib-python` `4.10.0.84`, `opencv-python-headless` `5.0.0.93` | PyPI wheels | Apache License 2.0 (confirmed per current OpenCV licensing — OpenCV relicensed from BSD to Apache-2.0 specifically for its patent grant clause on contributed code) | **Yes**. Patented/non-free algorithms (e.g. SURF) are excluded from these public wheel builds by upstream policy; SIFT is included (patent expired 2020/2022) | Apache-2.0 NOTICE | Inside installed app |
| **`crc32c`** | `2.9` | PyPI wheel | LGPL-2.1-or-later (confirmed, `crc32c-2.9.dist-info/METADATA`) | **Yes, under LGPL** — small, standard dynamically-loaded `.pyd`, same dynamic-linking pattern as PySide6 | LGPL notice | Inside installed app |
| **`certifi`** | `2026.7.22` | PyPI wheel | MPL-2.0 (file-level weak copyleft) | **Yes** | MPL-2.0 notice for the certifi module itself (no obligation extends to GlyphCue's own code — MPL is file-level) | Inside installed app |
| **All other vendored wheels** (79 of 85 frozen artifacts) | see `docs/m13_build_base_identity.json` | PyPI | MIT / BSD-2/3-Clause / Apache-2.0 / PSF-2.0 / 0BSD / MIT-0 / MIT-CMU — all confirmed permissive, no copyleft, via direct `.dist-info/METADATA` scan of every installed wheel | **Yes** | Standard notice retention | Repository/release notes sufficient; in-app optional |

---

## 3. The Five M13-Known Unresolved Model Assets — Independently Verified Hash Chain

The preliminary audit's claims are confirmed below with citations, not restated as unverified shorthand.

| # | Filename | SHA-256 (frozen) | Source URL (frozen in `docs/m13_build_base_identity.json`) | Independent verification |
|---|---|---|---|---|
| 1 | `PP-OCRv6_det_medium.onnx` | `92078b73...79907c2` | `modelscope.cn/models/RapidAI/RapidOCR` v3.9.2 | RapidOCR's own model repository on ModelScope is published under **Apache-2.0** (RapidOCR is itself an Apache-2.0 project; its ModelScope model hub inherits that license for the ONNX conversions it publishes). RapidOCR's own documentation confirms it republishes PaddleOCR's PP-OCRv6 series (tiny/small/medium tiers) in ONNX format from PaddlePaddle originals. |
| 2 | `PP-OCRv6_rec_small.onnx` | `6f327246...b3c14884` | `modelscope.cn/models/RapidAI/RapidOCR` v3.9.2 | Same chain as #1. |
| 3 | `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | `e47acedf...5a89d6215c` | `modelscope.cn/models/RapidAI/RapidOCR` v3.9.2 | Same chain as #1. |
| 4 | `PP-OCRv6_medium_det_infer.tar` | `144d0621...4fbabfcf7` | `paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/` | **This is PaddleX's own official model zoo host** (`paddle-model-ecology.bj.bcebos.com`), confirmed as the canonical distribution point for PP-OCRv6 official inference models in PaddleX 3.7's own documentation. PaddlePaddle's own public announcement (Hugging Face blog, "PP-OCRv6: 50-Language OCR") states PP-OCRv6 is "free and commercially usable under the Apache License 2.0." |
| 5 | `PP-OCRv6_medium_rec_infer.tar` | `4eecc1c6...d2b2dbd4da6` | `paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/` | Same chain as #4. |

**Chain of custody, all five:** PaddlePaddle/PaddleOCR project trains and publishes PP-OCRv6 (Apache-2.0, per PaddlePaddle's own release announcement) → PaddleX hosts the official Paddle-format inference archives at `paddle-model-ecology.bj.bcebos.com` (assets #4, #5) → RapidOCR independently converts the same model family to ONNX and republishes on ModelScope under Apache-2.0 (assets #1–#3). Both branches trace to the same upstream Apache-2.0-licensed model family; **no branch introduces a more restrictive license**. This closes the "merely says Paddle is Apache-2.0" gap the task called out — the verification here traces to PaddlePaddle's own model-release statement and to RapidOCR's own ModelScope publication, independently, for both branches of the distribution chain.

**Residual caveat (not a blocker, but honest):** none of the four upstream sources embeds a per-file `LICENSE` inside the model archive/weights themselves (confirmed: `find .../models -iname "*license*"` returns nothing). The Apache-2.0 attribution rests on the publishing project's own stated licensing (PaddlePaddle's release announcement, RapidOCR's repository/ModelScope license field), which is standard practice for model weight distributions but is weaker evidence than an embedded license file would be. Recommend archiving a dated snapshot of the two upstream announcement/license pages as durable evidence before public release, since upstream pages can change.

---

## 4. Notable Findings Requiring Action

### 4.1 🔴 GPL-licensed FFmpeg encoder codecs shipped, unused (BLOCKING as packaged)

Confirmed by direct binary inspection (not by trusting PyAV's own BSD-3-Clause package metadata, which covers only PyAV's Python wrapper code, not its vendored FFmpeg binary): `build_artifacts/phase_f/f3_corrective/app_root/lib/av.libs/` contains `libx264-165-*.dll` and `libx265-*.dll`. These are GPL-2.0-or-later video encoders. Their presence means PyAV `18.1.0`'s Windows wheel vendors an FFmpeg build compiled with GPL components enabled — a **materially different build** from Qt Multimedia's own FFmpeg (confirmed LGPL-clean per Qt's own attribution page). This is exactly the risk `docs/asr_licensing_research.md` predicted in general terms on 2026-09-04 ("never infer the FFmpeg license from PyAV's BSD metadata... audit the exact shipped DLLs"); this audit is the concrete confirmation.

**Verified unused:** `grep -rn` over `src/glyphcue/` shows GlyphCue's only PyAV call site (`src/glyphcue/adapters/pyav_media_source.py`) opens media in read-only decode mode (`av.open(path)`) and never encodes, never calls `add_stream`/`.encode()`/`container.mux`. libx264/libx265 are encoder-only libraries — GlyphCue cannot be using them for anything.

**Minimum action:** before freezing the public installer, remove `libx264-*.dll` and `libx265-*.dll` (and verify no other GPL-only codec DLL in the same directory, e.g. check for `libfdk-aac` — not found in this payload) from the packaged tree, or repackage using a PyAV wheel/build built without `--enable-gpl`. This is a packaging-script change (which files get copied into `app_root`), not a runtime/product-behavior change, and does not require rebuilding OCR/DirectML/Phase D-E-F evidence.

### 4.2 🟡 Unused GPL-tier-adjacent Qt Addon modules shipped (non-blocking, recommend trimming)

Qt WebEngine, Qt Charts, and Qt Data Visualization binaries are physically present (confirmed by file listing) because `PySide6-Addons` is unpacked wholesale with no module pruning, even though GlyphCue's source never imports any of them. Verified via Qt's own current licensing documentation that these are LGPL-available in Qt 6.11 (not GPL-only, correcting an initial Qt5-era hypothesis) — so this is **not a license blocker**. It is, however, unnecessary payload bulk and an unnecessary attribution surface (Qt WebEngine alone carries dozens of Chromium sub-component notices). Recommend stripping unused Qt modules from the packaging step before public distribution.

### 4.3 🟡 Two independent FFmpeg builds shipped (non-blocking, recommend documenting or consolidating)

Qt Multimedia and PyAV each vendor their own separate FFmpeg build (different versions: Qt's is FFmpeg-7.1.x-class per its own docs; PyAV's `av.libs` set carries different internal version suffixes). This is not itself a violation — both are separate dynamically-loaded DLL sets — but it doubles the FFmpeg attribution surface and payload size. Once 4.1 is fixed (removing GPL codecs from PyAV's copy), both remaining FFmpeg builds are LGPL and can be documented together in one NOTICE entry.

### 4.4 No third-party NOTICE / attribution document currently ships or exists in the repository

Despite 84 of 85 frozen wheels carrying proper `.dist-info/licenses/` folders (standard PEP 639 wheel license bundling) and the CycloneDX SBOM already recording license metadata for all 116 components, **no consolidated NOTICE file, README section, or in-app "About/Licenses" surface currently exists** to actually present these obligations to an end user or comply with attribution requirements. `ROADMAP.md` §20 already lists "third-party dependency/license attribution" as a required release-documentation item; it has not yet been produced. This is a concrete, scoped action for Gate A closure — not a research question.

---

## 5. Governance Questions for the Owner (not decided here)

### 5.1 No project LICENSE file exists

Confirmed: no `LICENSE`, `LICENSE.md`, `LICENSE.txt`, or `README.md` exists at the repository root. GlyphCue's own source code currently has **no declared license at all** — meaning, by default copyright law, all rights are reserved and no one (including the Owner's own distributed binary) has a clear license grant to redistribute or use it, and there is no stated position on whether GlyphCue's own code is proprietary/closed or open-source. This also directly affects §4.1: whether shipping a GPL component "taints" the combined work depends partly on what GlyphCue's own license is — an undeclared license makes that analysis impossible to close cleanly. **This is a real decision for the Owner, not something this audit should choose silently.** Options range from a permissive OSS license (MIT/Apache-2.0, consistent with almost everything else in the payload), to a source-available/all-rights-reserved binary distribution license, to leaving it proprietary/closed. Whichever is chosen affects the redistribution notices this gate must also finalize.

### 5.2 Signing policy inconsistency across the Owner's own projects

Current GlyphCue macro docs (`ROADMAP.md` §20, `docs/m13_phase_d/PHASE_D_RELAY.md`) treat **formal production/public-trust signing** as a hard release gate, separate from and blocking public distribution. The Owner has stated that two sibling projects — Vocabulary App and ListenTrace — ship self-signed or unsigned Windows binaries with honest SmartScreen disclosure instead. This is a real inconsistency across the Owner's own release governance, not a GlyphCue-specific technical requirement (nothing in GlyphCue's actual payload — Inno Setup installer, app-local Python runtime — technically requires a production certificate to function).

**Narrowest cross-repo-consistent recommendation (not a decision — flagged for the Owner):** align GlyphCue's policy with the precedent already set by Vocabulary App and ListenTrace — ship self-signed (or unsigned) with an honest, visible SmartScreen/"Unknown Publisher" disclosure in the README/release notes and in-app "About," rather than treating production code-signing as a hard release gate unique to GlyphCue. This is the narrowest change (aligns GlyphCue to existing practice, doesn't ask the other two projects to change) and avoids GlyphCue silently inventing a stricter bar than the Owner has applied elsewhere. **This is a recommendation only; governance documents are not being rewritten as part of this Gate A audit.**

---

## 6. Gate A Classification

## **PASS-WITH-ACTIONS**

Gate A is not BLOCKED: no finding here requires reopening Phase D/E/F, rerunning OCR evaluation, or a broad M13 retest. It is not a clean PASS either: one real, concrete redistribution risk (§4.1) exists in the payload today and must be fixed before the public installer is frozen.

### Minimum exact actions before freezing the public installer

1. **(Required, blocking) Remove `libx264-*.dll` and `libx265-*.dll`** from the packaged `app_root` (or switch to an FFmpeg/PyAV build compiled without `--enable-gpl`). Verified safe: GlyphCue's only PyAV usage is read-only decode; no encoding path exists anywhere in `src/glyphcue/`.
2. **(Required, blocking) Owner decision on governance question 5.1** (project LICENSE) — needed to correctly frame the NOTICE document in action 4, and to close the GPL analysis in action 1 with full confidence regardless of what's ultimately shipped.
3. **(Required, blocking) Owner decision on governance question 5.2** (signing policy) — determines whether "formal production/public-trust signing" stays a hard gate or is relaxed to match Vocabulary App / ListenTrace precedent; blocks the release governance checklist either way.
4. **(Required, non-blocking-for-Gate-A but required before public release) Produce the consolidated third-party NOTICE/attribution document** referenced in `ROADMAP.md` §20, covering all license families in §2 above, sized to whichever LICENSE decision (5.1) is made.
5. **(Recommended, non-blocking) Strip unused Qt Addon modules** (WebEngine, Charts, DataVisualization) from the packaging step to shrink payload size and attribution surface.
6. **(Recommended, non-blocking) Archive dated snapshots** of the PaddlePaddle PP-OCRv6 release announcement and RapidOCR's ModelScope license page as durable evidence for the five frozen model assets (§3), since upstream pages can change after this audit.

None of the above requires touching OCR/runtime architecture, rebuilding the already-Owner-validated installer, retesting Phase D/E/F, or a B/C dual reseal. Actions 1 and 5 are packaging-script changes (which files get copied); actions 2, 3, and 4 are governance/documentation decisions and their resulting paperwork.
