# GlyphCue

**Local-first Windows subtitle reconstruction workbench.**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Platform Windows](https://img.shields.io/badge/platform-Windows%20x64-0078D6.svg)](https://www.microsoft.com/windows)
[![UI PySide6](https://img.shields.io/badge/UI-PySide6%20(Qt6)-41CD52.svg)](https://www.qt.io/)
[![Acceleration DirectML](https://img.shields.io/badge/acceleration-DirectML%20%7C%20ONNX-FF6F00.svg)](https://onnxruntime.ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/tests-967%20passed-brightgreen.svg)](tests/)

---

## Overview

GlyphCue transforms noisy, burned-in video subtitles and fragmented rolling captions into clean, structured, verified subtitle files.

Burning subtitles into video pixels strips away timing, layout, and textual integrity. Traditional video-OCR approaches attempt frame-by-frame text extraction, which creates high-frequency timing jitter, OCR character noise bursts, and severe degradation on bilingual or stacked subtitle tracks. Automated speech recognition tools also produce fragmented, rolling text windows with redundant duplicate phrases.

GlyphCue bridges the gap between raw optical evidence and structured subtitle cues through selective frame difference gating, DirectML hardware-accelerated neural OCR, multi-frame temporal consensus, script-range layer isolation, conservative duplicate cleaning, and explainable review routing.

---

## Core Capabilities

### 1. Hardcoded Video Subtitle Reconstruction (Path A)
- **Selective OCR Gating**: Gated by a mean-absolute pixel difference change detector, reducing neural inference calls compared to naive per-frame scanning (~4x end-to-end throughput gain).
- **Hardware-Accelerated Inference**: Native ONNX Runtime DirectML engine operating at a measured **1.387× realtime ratio** (median across timed benchmark runs on RTX 3060), with a self-contained offline CPU fallback (`PaddleOcrEngine`).
- **Multi-Frame Consensus**: State-run temporal clustering and majority-vote character reconciliation mitigate single-frame OCR glitches and timing boundary noise.

### 2. Multilingual & Bilingual Track Separation
- **Script-Range Attribution**: Distinguishes overlapping subtitle layers (such as simultaneous Japanese and Chinese, or English and Japanese) via fixed-point Unicode script clustering.
- **Shared-Timing Multi-Layer Representation**: Reconstructs structured cues sharing timestamp boundaries with dedicated Language Layers (`Cue` ➔ `LanguageLayer[1..N]`), preventing foreign-language lines from interleaving into unreadable composite strings.

### 3. Rolling & Fragmented Caption Normalization (Path B)
- **Temporal State-Machine Processing**: Ingests rolling, fragmented, or messy auto-caption transcripts (SRT, VTT, TXT) and consolidates sliding-window phrase repeats into discrete, coherent sentences.
- **CJK-Sensitive Word & Punctuation Handling**: Preserves natural phrasing for Japanese, Chinese, and Latin text without artificial whitespace insertion or boundary corruption.

### 4. Post-Reconstruction Cue Quality Recovery & Review Routing
- **Integrated Cue Cleaner V0.6.1**: Conservative post-processing collapses burst-split duplicates and cleans edge artifacts without discarding complementary evidence.
- **Monotonic Review Priority Scoring**: Automatically calculates an explainable quality score for each reconstructed cue, routing uncertain timestamps, low OCR confidence, or ambiguous attribution directly to human reviewers.

### 5. Local-First Persistence & Atomic Multi-Format Export
- **Local-First & Offline**: Video decoding, neural OCR inference, and SQLite persistence execute entirely on the local workstation with zero cloud dependencies or telemetry.
- **Atomic File Serialization**: Exports reviewed subtitle tracks to `.srt`, `.vtt`, `.ass`, and plain `.txt` via temporary-file-and-rename semantics, preventing file corruption or accidental source overwrites.

---

## Pipeline Architecture

```text
               ┌─────────────────────────────────────────────────────────┐
               │                     Input Sources                       │
               │  • Burned-in Video (.mp4/.mkv)   • Rolling Subtitles    │
               └───────────┬─────────────────────────────────┬───────────┘
                           │ (Path A: Video)                 │ (Path B: Timed Text)
                           ▼                                 ▼
               ┌────────────────────────┐        ┌───────────────────────┐
               │ Frame Decoding & ROI   │        │ Parser & Normalizer   │
               │ PyAV / FFmpeg LGPL     │        │ pysubs2 + Sanitizer   │
               └───────────┬────────────┘        └───────────┬───────────┘
                           │                                 │
                           ▼                                 │
               ┌────────────────────────┐                    │
               │ Selective OCR Gating   │                    │
               │ Frame Δ Trigger Policy │                    │
               └───────────┬────────────┘                    │
                           │                                 │
                           ▼                                 │
               ┌────────────────────────┐                    │
               │ Neural OCR Engine      │                    │
               │ DirectML GPU / CPU ONNX│                    │
               └───────────┬────────────┘                    │
                           │                                 │
                           ▼                                 │
               ┌────────────────────────┐                    │
               │ Script-Range Separation│                    │
               │ Multilingual Layering  │                    │
               └───────────┬────────────┘                    │
                           │                                 │
                           ▼                                 │
               ┌────────────────────────┐                    │
               │ Multi-Frame Consensus  │                    │
               │ Temporal State Runs    │                    │
               └───────────┬────────────┘                    │
                           │                                 │
                           └────────────────┬────────────────┘
                                            ▼
                               ┌─────────────────────────┐
                               │ Reconstructed Cues      │
                               │ Local SQLite Database   │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │ Conservative Cleaner    │
                               │ Cue Cleaner V0.6.1      │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │ Review Priority Engine  │
                               │ Monotonic Quality Score │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │ Atomic Multi-Format I/O │
                               │ SRT / VTT / ASS / TXT   │
                               └─────────────────────────┘
```

---

## Engineering Highlights & Technical Decisions

| Technical Domain | Engineering Approach | Real Repository Evidence |
|---|---|---|
| **Hardware Acceleration & Fail-Closed Fallback** | Native `onnxruntime-directml` acceleration on Windows D3D12 devices (measured median `1.387×` realtime ratio) paired with an automatic, fully offline `PaddleOcrEngine` CPU fallback using bundled model assets. | [`docs/adr/0001-ocr-runtime-selection.md`](docs/adr/0001-ocr-runtime-selection.md) |
| **Selective OCR Invocation** | Pixel-difference frame gating filters non-subtitle movement and static pauses, yielding a ~4x end-to-end processing throughput gain over dense scanning. | [`docs/adr/0002-selective-ocr-strategy.md`](docs/adr/0002-selective-ocr-strategy.md) |
| **Multi-Frame Consensus** | Custom temporal state-run clustering algorithms vote on character sequences across stable frame runs, suppressing single-frame OCR noise. | [`docs/adr/0003-consensus-reconstruction-approach.md`](docs/adr/0003-consensus-reconstruction-approach.md) |
| **Cooperative Concurrency** | Qt Signal + worker thread contract (`Job`/`JobContext`) enforcing cooperative cancellation, terminal state guarantees, and responsive UI. | [`docs/adr/0004-media-architecture.md`](docs/adr/0004-media-architecture.md) |
| **Multilingual Attribution** | Hand-crafted Unicode script range analysis separating mixed CJK/Latin layers into structured language layers sharing Cue timing. | [`docs/adr/0005-multilingual-timing-simplification.md`](docs/adr/0005-multilingual-timing-simplification.md) |
| **Reproducible Packaging** | Dual clean reconstructions verified across 21,811 payload files with 0 unsigned drift, CycloneDX SBOM, and pinned LGPL FFmpeg DLLs. | [`docs/m13_dependency_and_packaging_audit.md`](docs/m13_dependency_and_packaging_audit.md) |
| **Comprehensive Regression Baseline** | 967 unit, integration, and UI tests (plus 1 skipped, 1 xfailed) guarding state persistence, migration replay, cleaner invariants, and export contracts. | [`tests/`](tests/) |

---

## Evaluation & Quick Start

### Option A: Standalone Windows Installer (Recommended for Users)

1. Download the verified `GlyphCue-Setup-1.0.0.exe` from [GitHub Releases](https://github.com/Peter-S-Shi/glyphcue/releases/tag/v1.0.0).
2. Run the installer.
   > **Note on Windows SmartScreen**: The installer is signed with a local Authenticode development certificate (`CN=GlyphCue Development Test Certificate`). When prompted by Windows SmartScreen, click **More info** → **Run anyway**.
3. Launch **GlyphCue** from the Start Menu or desktop shortcut.
4. Load a video file, select your target subtitle region of interest (ROI), and click **Start Reconstruction**.
5. Inspect generated cues, run **Clean Cues**, review high-priority flags, and export to `.srt` or `.vtt`.

### Option B: Developer Environment Setup

#### Prerequisites
- **OS**: Windows 10/11 x64 (Build 22000+)
- **Python**: 3.12 (64-bit)
- **Git**

#### Installation

```powershell
# 1. Clone repository
git clone https://github.com/Peter-S-Shi/glyphcue.git
cd glyphcue

# 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install core package and development dependencies
pip install -e ".[dev]"

# 4. (Optional) Install Windows DirectML hardware acceleration dependencies
pip install -e ".[directml]"

# 5. Run test suite
pytest -v
```

#### Launching the Application

```powershell
python -m glyphcue
```

---

## Build vs. Integrate Separation

GlyphCue enforces a strict architectural distinction between third-party components and first-party algorithms:

- **Mature Integrated Dependencies**:
  - **PySide6 (Qt6)**: Cross-platform windowing, threading primitives, and rendering canvas.
  - **PyAV (FFmpeg)**: Video container demuxing, stream extraction, and color space decoding.
  - **ONNX Runtime & PaddleOCR**: Deep learning inference runtimes for text detection and character recognition.
  - **pysubs2**: Low-level parsing and formatting for subtitle containers.
- **GlyphCue Proprietary Contributions**:
  - Frame-difference selective OCR scheduling policy.
  - Temporal multi-frame consensus and majority-vote grouping.
  - Fixed-point Unicode script-range layer separator for bilingual tracks.
  - Temporal state-machine rolling caption normalizer.
  - Monotonic Review Priority routing engine.
  - Cooperative background job cancellation lifecycle harness.

For detailed technical analysis, see [`BUILD_VS_INTEGRATE.md`](BUILD_VS_INTEGRATE.md) and [`FAILURE_MODE_REPORT.md`](FAILURE_MODE_REPORT.md).

---

## Technical Documentation Map

- **Product Architecture**: [`GLYPHCUE_PRODUCT_ARCHITECTURE.md`](GLYPHCUE_PRODUCT_ARCHITECTURE.md) — Authoritative macro-architecture, system contracts, and module boundaries.
- **Design Specifications**: [`DESIGN.md`](DESIGN.md) — UI interaction patterns, state management, and schema designs.
- **Architectural Decision Records**: [`docs/adr/`](docs/adr/) — Historical technical rationale for OCR engines, selective frame policies, and media architectures.
- **Product Roadmap & History**: [`ROADMAP.md`](ROADMAP.md) — Milestone progression and Stop-Building closure.
- **Current Project Status**: [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — Active verification status, gate closures, and release readiness.

---

## Licensing & Compliance

- **GlyphCue Source Code**: Licensed under the [MIT License](LICENSE).
- **FFmpeg Distribution**: Packaged using a pinned LGPL-3.0 shared library build. Corresponding source code is available in the official release package (`GlyphCue-v1.0.0-FFmpeg-LGPL-Corresponding-Source.zip`).
- **OCR Model Weights**: Distributed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
- **Third-Party Notices**: Attribution and third-party license texts are documented in [`docs/licenses/`](docs/licenses/) and [`docs/v1_public_release_dependency_provenance.json`](docs/v1_public_release_dependency_provenance.json).
