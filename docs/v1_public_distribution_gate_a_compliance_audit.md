# GlyphCue v1.0.0 Public Distribution Gate — Gate A/B: Redistribution & Licensing Compliance Audit and Minimum Real Payload

**Document type:** Authoritative public-safe compliance matrix
**Target Issue:** #30 — GlyphCue v1.0.0 Public Distribution Gate
**Branch:** `release/1.0.0-public-distribution`, based exactly on M13-closed `main` @ `4adbb6c4679b40220c07b01fb46969722138fd35`
**Status:** Gate A **PASS**. Gate B (minimum real public-distribution payload) implemented and verified against a freshly rebuilt real `app_root`/installer — see §6. Both Owner governance questions RESOLVED (§5). Not yet tagged, not yet published as a GitHub Release, PR #31 not yet merged.
**Date:** 2026-09-06 (revised twice same day — see "Revision" note below, then §6 for the Gate B closure)

**Revision note:** This document's original §4.1/§6 recommended removing `libx264-*.dll`/`libx265-*.dll` from the shipped payload as a sufficient fix. That remediation is **wrong and has been struck below**: FFmpeg's own licensing policy is that enabling `--enable-gpl` at configure time makes the GPL apply to the FFmpeg build **as a whole**, not only to the specific GPL-only codec it enables — confirmed via FFmpeg's own legal page ("If those parts get used the GPL applies to all of FFmpeg"; its own LGPL-compliance checklist requires compiling **without** `--enable-gpl` from the start). Deleting the external `libx264`/`libx265` DLL files after compilation does not relicense the already-GPL-configured `avcodec`/`avformat`/`avutil`/etc. binaries back to LGPL, and risks breaking their dynamic dependencies. §4.1 is now revised to record a genuinely verified LGPL-only replacement path instead, empirically validated under `build_artifacts/`.

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
| **🔴 PyAV's own bundled FFmpeg build** (`app_root/lib/av.libs/avcodec-62-*.dll`, `avformat-62-*.dll`, etc. — a **second, independent** FFmpeg build shipped alongside Qt's own) | PyAV `18.1.0` Windows wheel's vendored FFmpeg | PyAV project (`pyav.org`) | PyAV's own code: BSD-3-Clause (confirmed, `av-18.1.0.dist-info/METADATA`). **The vendored FFmpeg binaries are a separate matter — verified by direct binary inspection, not inferred from PyAV's BSD license**: `app_root/lib/av.libs/` physically contains `libx264-165-*.dll` and `libx265-*.dll`. **libx264 and libx265 are GPL-2.0-or-later encoders.** Their presence means this specific FFmpeg build was compiled with `--enable-gpl --enable-libx264 --enable-libx265`. **Per FFmpeg's own licensing policy, enabling `--enable-gpl` makes the entire compiled build — `avcodec-62.dll`, `avformat-62.dll`, `avutil-60.dll`, `avdevice-62.dll`, `avfilter-11.dll`, `swscale-9.dll`, `swresample-6.dll`, not merely the separate `libx264`/`libx265` files — a GPL-2.0-or-later work as a whole.** | **BLOCKING as currently packaged** — shipping a GPL-licensed FFmpeg build inside a proprietary/unlicensed application (see governance question #1, §5) risks obligating the combined work under GPL, per FFmpeg's own published redistribution guidance | **Verified dead code**: `grep -rn "av\.open\|add_stream\|\.encode(\|container\.mux" src/glyphcue/` shows GlyphCue's only PyAV usage (`src/glyphcue/adapters/pyav_media_source.py`) is `av.open(path)` in **read-only decode mode** — GlyphCue never encodes video and never calls into libx264/libx265 at all. | **Fix (revised, see §4.1): replace all 7 core FFmpeg DLLs with a verified LGPL-only build**, not merely delete the two external codec DLLs — deleting only `libx264`/`libx265` does **not** relicense the remaining, already-GPL-configured core libraries back to LGPL. A verified, pinned, drop-in-compatible LGPL replacement has been identified and empirically validated; see §4.1. |
| **ONNX Runtime (DirectML build)** | `onnxruntime-directml` `1.24.4`, `onnxruntime.dll` | PyPI wheel, Microsoft | MIT License (confirmed, `onnxruntime_directml-1.24.4.dist-info/METADATA`) | **Yes** | Retain MIT notice | Inside installed app |
| **DirectML.dll** | bundled inside `onnxruntime_directml-1.24.4` wheel, SHA-256 `b7397211...9482a8d7` | Microsoft, `microsoft/DirectML` GitHub repo | **Verified via `github.com/microsoft/DirectML/blob/master/LICENSE`**: MIT License | **Yes** | Retain MIT notice | Inside installed app |
| **PaddlePaddle (framework)** | `paddlepaddle` `3.3.1` | PyPI wheel, PaddlePaddle project | Apache License 2.0 (confirmed, `paddlepaddle-3.3.1.dist-info/METADATA`) | **Yes** | Apache-2.0 NOTICE + license text | Inside installed app |
| **PaddleOCR / PaddleX (code)** | `paddleocr` `3.7.0`, `paddlex` `3.7.2` | PyPI wheels, PaddlePaddle project | Apache-2.0 (confirmed, both `.dist-info/METADATA`) | **Yes** | Apache-2.0 NOTICE | Inside installed app |
| **RapidOCR (code)** | `rapidocr` `3.9.2` | PyPI wheel, `RapidAI/RapidOCR` | Apache-2.0 (confirmed, `rapidocr-3.9.2.dist-info/METADATA` — `License-Expression: Apache-2.0`) | **Yes** | Apache-2.0 NOTICE | Inside installed app |
| **OpenCV** | `opencv-python` `5.0.0.93`, `opencv-contrib-python` `4.10.0.84`, `opencv-python-headless` `5.0.0.93` | PyPI wheels | Apache License 2.0 (confirmed per current OpenCV licensing — OpenCV relicensed from BSD to Apache-2.0 specifically for its patent grant clause on contributed code) | **Yes**. Patented/non-free algorithms (e.g. SURF) are excluded from these public wheel builds by upstream policy; SIFT is included (patent expired 2020/2022) | Apache-2.0 NOTICE | Inside installed app |
| **`crc32c`** | `2.9` | PyPI wheel | LGPL-2.1-or-later (confirmed, `crc32c-2.9.dist-info/METADATA`) | **Yes, under LGPL** — small, standard dynamically-loaded `.pyd`, same dynamic-linking pattern as PySide6 | LGPL notice | Inside installed app |
| **`certifi`** | `2026.7.22` | PyPI wheel | MPL-2.0 (file-level weak copyleft) | **Yes** | MPL-2.0 notice for the certifi module itself (no obligation extends to GlyphCue's own code — MPL is file-level) | Inside installed app |
| **All other vendored wheels** (79 of 85 frozen artifacts) | see `docs/m13_build_base_identity.json` | PyPI | MIT / BSD-2/3-Clause / Apache-2.0 / PSF-2.0 / 0BSD / MIT-0 / MIT-CMU — all confirmed permissive, no copyleft, via direct `.dist-info/METADATA` scan of every installed wheel | **Yes** | Standard notice retention (**corrected placement, see note below**) | Inside installed app (a consolidated NOTICE accompanying the distributed application) — a GitHub repository entry alone does not satisfy an MIT/BSD/Apache notice obligation, since most end users of the installed binary never visit the repository |

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

### 4.1 🔴 GPL-configured FFmpeg build shipped (BLOCKING as packaged) — corrected finding and verified fix

Confirmed by direct binary inspection (not by trusting PyAV's own BSD-3-Clause package metadata, which covers only PyAV's Python wrapper code, not its vendored FFmpeg binary): `build_artifacts/phase_f/f3_corrective/app_root/lib/av.libs/` contains `libx264-165-*.dll` and `libx265-*.dll`. These are GPL-2.0-or-later video encoders. Their presence means PyAV `18.1.0`'s Windows wheel vendors an FFmpeg build compiled with `--enable-gpl` — a **materially different build** from Qt Multimedia's own FFmpeg (confirmed LGPL-clean per Qt's own attribution page). This is exactly the risk `docs/asr_licensing_research.md` predicted in general terms on 2026-09-04 ("never infer the FFmpeg license from PyAV's BSD metadata... audit the exact shipped DLLs"); this audit is the concrete confirmation.

**Correction (this revision):** the original version of this section recommended simply deleting `libx264-*.dll`/`libx265-*.dll` from the shipped payload. **That is insufficient and has been withdrawn.** FFmpeg's own legal page states plainly: *"FFmpeg incorporates several optional parts and optimizations that are covered by the GNU General Public License (GPL) version 2 or later. If those parts get used the GPL applies to all of FFmpeg"* — and FFmpeg's own LGPL-compliance checklist requires compiling **without** `--enable-gpl` from the start, not stripping GPL components after the fact. Once `avcodec-62.dll`/`avformat-62.dll`/etc. are compiled under a GPL-enabled configuration, they are GPL-2.0-or-later works as a whole; deleting the separate `libx264`/`libx265` DLL files does not relicense them back to LGPL, and could additionally break their dynamic import dependencies (unverified either way — moot, since the approach is licensing-invalid regardless).

**Verified unused (this part of the original finding stands):** `grep -rn` over `src/glyphcue/` shows GlyphCue's only PyAV call site (`src/glyphcue/adapters/pyav_media_source.py`) opens media in read-only decode mode (`av.open(path)`) and never encodes, never calls `add_stream`/`.encode()`/`container.mux`. libx264/libx265 are encoder-only libraries — GlyphCue cannot be using them for anything. This confirms a genuine LGPL-only FFmpeg replacement is functionally sufficient (no encoder codepath is needed), it just cannot be achieved by deletion alone.

**Verified fix: a pinned, drop-in-compatible LGPL-only FFmpeg build, empirically validated.**

| Property | Value |
|---|---|
| Source project | `BtbN/FFmpeg-Builds` (a long-standing, widely-used community Windows FFmpeg build project that explicitly publishes separate GPL and LGPL variants for exactly this purpose) |
| Release tag | `autobuild-2026-09-06-13-06` |
| Asset | `ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-shared-8.1.zip` |
| Source URL | `https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-09-06-13-06/ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-shared-8.1.zip` |
| Archive SHA-256 (downloaded and verified this session) | `0f86693cd5b8bcc61296cdbfd38c98817dd5491fa81a28b44b7e0a86965043fb` |
| FFmpeg version | `n8.1.2-50-g1a748fe2cd-20260906` |
| License, verified directly from the archive's own `LICENSE.txt` | GNU LESSER GENERAL PUBLIC LICENSE, Version 3 |
| Configure flags, verified directly by running the archive's own `ffmpeg.exe -version` | `--enable-version3 ... --disable-libx264 --disable-libx265` — no `--enable-gpl` anywhere in the reported configuration string |
| SO-version match to PyAV 18.1.0's vendored build | Exact: `avutil-60`, `avcodec-62`, `avformat-62`, `avdevice-62`, `avfilter-11`, `swscale-9`, `swresample-6` — identical version numbers to the GPL-configured build already vendored by the PyAV 18.1.0 Windows wheel |

**This is not a swap of PyAV as a product dependency and not a change to GlyphCue's media architecture** — PyAV 18.1.0 (the exact same wheel, same Python API, same `pyav_media_source.py` integration) is retained. Only its vendored FFmpeg *binary* is replaced at packaging time.

**Empirical validation performed** (staged and executed only under `build_artifacts/v1_gate_a/`, never touching the real shipped `app_root` or the dev `.venv`):

1. Staged an isolated copy of the installed `av` + `av.libs` package under `build_artifacts/v1_gate_a/lgpl_pyav_test/site-packages/`.
2. Replaced the 7 core FFmpeg DLLs' contents with the LGPL build above, keeping PyAV's original (delvewheel-mangled) filenames so `_core.pyd`'s references still resolve, and additionally placed the same DLLs under their plain filenames (`avutil-60.dll`, etc.) so the LGPL build's own inter-library imports (which reference each other by plain name, unlike PyAV's mangled names) resolve too. Verified via a small PE import-table parser (`build_artifacts/v1_gate_a/lgpl_pyav_test/pe_imports.py`, written this session, no external dependency) exactly which DLL names each binary imports, rather than guessing.
3. Confirmed via the same import-table parser that **none** of the LGPL build's 7 DLLs import `libx264`, `libx265`, `libvpx`, `libwebp`, `libopus`, `libmp3lame`, `libdav1d`, `libSvtAv1Enc`, `libvpl`, the AMR codec libs, `libsharpyuv`, `libiconv`, `libgcc_s_seh`, `libwinpthread`, `zlib1`, or `libstdc++` — they are fully statically self-contained, meaning all 18 of the old build's now-superfluous codec/runtime DLLs become safely removable in a real packaging implementation.
4. **PyAV import: PASS.** Loaded the staged `av` package (confirmed via `av.__file__` pointing at the staged path, not the real venv) with zero import errors.
5. **Representative MP4 decode: PASS.** Opened the canonical synthetic fixture (`glyphcue_synthetic_fixture_v1.mp4`, the same fixture `docs/m13_synthetic_fixture_golden.json` and Phase E's E1 performance evidence use) via `av.open()` and decoded 30 frames.
6. **PTS/frame extraction equivalence: PASS, exact.** Compared against a baseline decode of the same 30 frames using the original, unmodified (GPL-configured) PyAV installation: frame count, full PTS sequence, and SHA-256 of each decoded frame's raw RGB24 byte array are **byte-identical** between the GPL-configured baseline and the LGPL-swapped build. Per this task's own bounded-verification rule ("only if decoded frame bytes materially differ, run one bounded downstream OCR smoke"), **no OCR smoke was required** — the decode path is proven byte-for-byte equivalent, a stronger result than an OCR-output equivalence check would have given.
7. All evidence, scripts, and the downloaded/extracted LGPL archive are preserved under `build_artifacts/v1_gate_a/` (gitignored, machine-local) for reproducibility.

**Packaging guard added this session (not yet wired into the real build):** [`tools/packaging/verify_no_gpl_ffmpeg_codecs.py`](../tools/packaging/verify_no_gpl_ffmpeg_codecs.py) provides `assert_no_gpl_ffmpeg_codec_libraries(app_root)`, a fail-closed check that raises if any forbidden GPL-only codec library filename (`libx264`, `libx265`, `libxvid`, `librubberband`) is found anywhere in a packaged `app_root`, plus the pinned `LGPL_FFMPEG_PROVENANCE` record above as a constant for the real packaging implementation to consume. A regression test (`tools/packaging/validate_scaffold.py::test_gpl_ffmpeg_codec_guard_fails_closed_on_forbidden_libraries`) proves the guard fires on a forbidden file and passes on a clean tree, and the guard was run against the real `build_artifacts/phase_f/f3_corrective/app_root` this session, correctly flagging both `libx264-165-*.dll` and `libx265-*.dll` there today.

**Not yet done (explicitly out of this session's scope, per instruction not to freeze/rebuild the public installer):** wiring this guard and the DLL-swap into `execute_phase_b.py`/`execute_phase_c.py`'s actual packaging pipeline, and re-running it against a real rebuilt `app_root`. That remains a minimum action for Gate A closure (§6), not yet executed.

### 4.2 🟡 Unused GPL-tier-adjacent Qt Addon modules shipped (non-blocking, recommend trimming)

Qt WebEngine, Qt Charts, and Qt Data Visualization binaries are physically present (confirmed by file listing) because `PySide6-Addons` is unpacked wholesale with no module pruning, even though GlyphCue's source never imports any of them. Verified via Qt's own current licensing documentation that these are LGPL-available in Qt 6.11 (not GPL-only, correcting an initial Qt5-era hypothesis) — so this is **not a license blocker**. It is, however, unnecessary payload bulk and an unnecessary attribution surface (Qt WebEngine alone carries dozens of Chromium sub-component notices). Recommend stripping unused Qt modules from the packaging step before public distribution.

### 4.3 🟡 Two independent FFmpeg builds shipped (non-blocking, recommend documenting or consolidating)

Qt Multimedia and PyAV each vendor their own separate FFmpeg build (different versions: Qt's is FFmpeg-7.1.x-class per its own docs; PyAV's `av.libs` set carries different internal version suffixes). This is not itself a violation — both are separate dynamically-loaded DLL sets — but it doubles the FFmpeg attribution surface and payload size. Once 4.1 is fixed (removing GPL codecs from PyAV's copy), both remaining FFmpeg builds are LGPL and can be documented together in one NOTICE entry.

### 4.4 No third-party NOTICE / attribution document currently ships or exists at all — and it must accompany the distributed application, not only the repository

Despite 84 of 85 frozen wheels carrying proper `.dist-info/licenses/` folders (standard PEP 639 wheel license bundling) and the CycloneDX SBOM already recording license metadata for all 116 components, **no consolidated NOTICE file, README section, or in-app "About/Licenses" surface currently exists anywhere** — not in the repository and not in the installed application — to actually present these obligations to an end user. `ROADMAP.md` §20 already lists "third-party dependency/license attribution" as a required release-documentation item; it has not yet been produced.

**Notice placement, corrected:** a GitHub repository README or release-notes entry is **not** sufficient on its own to satisfy MIT/BSD/Apache-2.0-style "include this notice in copies of the Software" obligations, because the people who receive a *copy of the software* are installer end users, most of whom never visit the source repository at all. The required third-party notices must **accompany the distributed application itself** — e.g. a `THIRD-PARTY-NOTICES.txt` shipped inside `app_root` alongside `GlyphCue.exe`, or an in-app "About → Licenses" surface — with the repository/release-notes copy treated as a courtesy mirror, not the compliance copy. This is a concrete, scoped action for Gate A closure (§6), not a research question.

---

## 5. Governance Questions for the Owner

### 5.1 No project LICENSE file exists — **RESOLVED: MIT**

Confirmed at the time of this audit: no `LICENSE`, `LICENSE.md`, `LICENSE.txt`, or `README.md` existed at the repository root. **Correction to the original wording:** the absence of a project LICENSE does **not** stop the Owner, as copyright holder, from distributing the compiled binary — the Owner owns the copyright in GlyphCue's own source and needs no license grant from themself to ship it. What an undeclared LICENSE actually means is narrower and different: **no downstream party is explicitly granted any source-code rights** (no stated permission to view, modify, redistribute, or build derivative works from GlyphCue's own source) — by default copyright law, all such rights are reserved absent an explicit grant. It was, however, still a real, live decision for the Owner, and it affects how the §4.4 third-party NOTICE document is framed.

**Owner decision (final):** GlyphCue's own source code is licensed under the **MIT License**, consistent with the Owner's Vocabulary App MIT posture. A root `LICENSE` file has been added to the repository and is copied into the installed application at `app_root\LICENSE` (see `docs/v1_public_release_dependency_provenance.json`).

### 5.2 Signing policy inconsistency across the Owner's own projects — **RESOLVED: self-signed with disclosure accepted**

Current GlyphCue macro docs (`ROADMAP.md` §20, `docs/m13_phase_d/PHASE_D_RELAY.md`) treated **formal production/public-trust signing** as a hard release gate, separate from and blocking public distribution. The Owner had stated that two sibling projects — Vocabulary App and ListenTrace — ship self-signed or unsigned Windows binaries with honest SmartScreen disclosure instead. This was a real inconsistency across the Owner's own release governance, not a GlyphCue-specific technical requirement (nothing in GlyphCue's actual payload — Inno Setup installer, app-local Python runtime — technically requires a production certificate to function).

**Owner decision (final):** the existing self-signed Authenticode development certificate (`CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root`, thumbprint `DEDF7D0881E3A172CC018B63CCCF69FC51333AFC`) is **accepted for v1.0.0 public distribution**, with explicit SmartScreen / not-publicly-trusted disclosure to end users. This is the narrowest cross-repo-consistent policy this audit recommended: it aligns GlyphCue with the precedent already set by Vocabulary App and ListenTrace rather than inventing a stricter bar unique to GlyphCue. **Formal production/public-trust signing is not a v1.0.0 blocker.** The explicit SmartScreen/not-publicly-trusted disclosure text for the README/release notes and installer still needs drafting as a follow-up (see `docs/v1_public_release_dependency_provenance.json`'s `owner_governance_decisions.signing_policy_decision.not_yet_done`) — recording the decision here does not by itself produce that user-facing copy.

---

## 6. Gate A/B Classification

## **PASS** (Gate A research accepted; Gate B minimum real payload implemented and verified)

Both previously-blocking items are now resolved and empirically verified against a freshly rebuilt, real public-release candidate `app_root` and installer — not merely staged under `build_artifacts/`:

1. **LGPL-only FFmpeg replacement wired into the real packaging pipeline** (`execute_phase_b.py`/`execute_phase_c.py`, via `tools/packaging/lgpl_ffmpeg_replacement.py`): archive hash verified before extraction, all 7 core FFmpeg DLLs deterministically replaced, all 18 superseded GPL-build auxiliary DLLs removed, `assert_no_gpl_ffmpeg_codec_libraries()` and the strengthened `assert_lgpl_ffmpeg_core_identities()` (exact SHA-256 content match, not filename-only) both fail-closed gates in the pipeline.
2. **Both Owner governance questions resolved** (§5.1 MIT license, §5.2 self-signed-with-disclosure) — recorded in `docs/v1_public_release_dependency_provenance.json`.
3. **Third-party notices compliance surface** (`legal/THIRD-PARTY-NOTICES.txt` + `legal/third_party_licenses/`) generated and verified present inside the actual installed application, not only the repository.
4. **FFmpeg LGPL corresponding-source package** prepared as a standalone, attachable GitHub Release asset (real FFmpeg source + BtbN build scripts + LGPLv3 text, not a link to a mutable upstream page).

### Fresh rebuild verification results (real `app_root` and installer, not a staged mock)

- No GPL-only codec library filename present: **PASS**
- All 7 core FFmpeg DLLs match the pinned LGPL build's SHA-256 exactly: **PASS**
- Runtime sanity (PySide6, PyAV, ONNX Runtime DirectML provider active, RapidOCR construction): **PASS**
- Manifest-to-disk reconciliation (21,811 files, 0 unindexed, 0 missing) + `integrity_gate`/`untracked_file_gate`/`provenance_gate_experiment_scope` all `PASS`: **PASS**
- `LICENSE`, `legal/THIRD-PARTY-NOTICES.txt`, and `legal/third_party_licenses/` (including full LGPL-3.0 and Apache-2.0 texts) confirmed present in the installed payload: **PASS**
- PyAV import + canonical fixture decode, run under the rebuilt `app_root`'s own embedded CPython 3.12 (not the dev venv): frame count, PTS sequence, and decoded frame bytes (SHA-256 of raw RGB24 arrays) **byte-identical** to the original GPL-configured baseline: **PASS**
- Installer signed with the existing self-signed development certificate, Authenticode `Valid`: **PASS**

**Final frozen candidate installer:** `GlyphCue-Setup-1.0.0.exe`, SHA-256 (signed) `F88C2FE2C6D226BD2FFF5ECFDC7E7F64DC32917B8C00597FB17D42B9A7244446`, Authenticode `Valid`. Standalone corresponding-source archive: `GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`, SHA-256 `FC59A64DB0B932A63FB7432C57CFE850BA3CAA07F73E9BEC4437416E3240D3CC`.

### Remaining before tagging/publishing v1.0.0 (not performed this session, per instruction)

1. Draft the explicit SmartScreen/not-publicly-trusted disclosure text for the README/release notes and installer (the signing *policy* is resolved; the user-facing disclosure *copy* is not yet written).
2. **(Recommended, non-blocking)** Strip unused Qt Addon modules (WebEngine, Charts, DataVisualization) — explicitly deferred, not performed this pass, to avoid unnecessarily broadening the payload delta.
3. **(Recommended, non-blocking)** Archive dated snapshots of the PaddlePaddle PP-OCRv6 release announcement and RapidOCR's ModelScope license page as durable evidence for the five frozen model assets (§3).
4. Attach the FFmpeg LGPL corresponding-source package, the installer, and `SHA256SUMS.txt`/`provenance.json` to an actual GitHub v1.0.0 Release (not created this session).
5. Tag and publish `v1.0.0` only after Owner/ChatGPT distribution review of the candidate installer identity above.

None of the above requires touching OCR/runtime architecture, retesting Phase D/E/F, F1-F4, or a B/C dual reseal — no targeted check this session exposed a contradiction requiring one.
