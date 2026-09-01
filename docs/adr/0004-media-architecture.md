# ADR 0004: Media Architecture — Split Playback / Analysis / Transform Stack

**Status:** Accepted
**Date:** 2026-08-31 (Milestone 10 ADR closure; decision originates from ROADMAP.md section 3 at roadmap start, exercised starting Milestone 2)
**Milestone:** ROADMAP.md Milestone 2 — Path A Media & Job Orchestration (initial exercise); section 3 states the frozen V1 baseline

## Context

GlyphCue needs three distinct things from video files that a single library does not cleanly provide at once: smooth human playback with audio (for the user to watch their video and review Cues against it), PTS-correct algorithmic frame access (for OCR evidence collection, where an off-by-one-frame or `frame_index / fps` timestamp assumption would silently corrupt Cue timing), and occasional heavy format/container transforms (transcoding, muxing) that are not part of the core reconstruction path.

No single Python media library is simultaneously the best fit for real-time playback UX, precise low-level frame/PTS access, and general-purpose transcoding — each is a different engineering problem with different tools already built for it.

## Chosen architecture

Three separate, intentionally non-overlapping components, each behind a GlyphCue-owned boundary:

- **Human playback: Qt Multimedia (`QMediaPlayer`)**, wrapped by `PlaybackController` (`src/glyphcue/ui/playback_controller.py`). Handles Play/Pause, seek, cue-span replay, and normal audio/video output — nothing else.
- **Algorithmic frame/timestamp access: PyAV**, behind the `MediaFrameSource` protocol (`src/glyphcue/adapters/media_frame_source.py`) and its concrete `PyAvMediaFrameSource` (`src/glyphcue/adapters/pyav_media_source.py`). Handles stream inspection, decoded frames, real PTS access, frame→NumPy conversion, and selected-range decoding for OCR evidence collection.
- **Heavy media transforms: a bundled, license-audited FFmpeg CLI via `QProcess`**, behind the `MediaTransformService` protocol (`src/glyphcue/adapters/media_transform.py`). Scoped to transcoding/muxing work outside the core reconstruction path.

## Why

**Qt Multimedia for playback, not PyAV:** the UI already runs on Qt (ROADMAP.md section 3's PySide6/Qt Widgets baseline); `QMediaPlayer` gives synchronized audio/video playback, seeking, and a signal/slot integration with the rest of the UI for free. Re-implementing audio-synced playback on top of PyAV's decode primitives would duplicate work Qt already does correctly and is not GlyphCue's problem to solve.

**PyAV for algorithmic access, not `QMediaPlayer`:** `QMediaPlayer` is built for smooth human playback, not for precise, repeatable, PTS-correct frame extraction at arbitrary points — and ROADMAP.md's explicit Milestone 2 acceptance gate (real tests proving the code never assumes `timestamp = frame_number / fps`) needs a decoder that exposes real per-frame PTS directly. PyAV wraps FFmpeg's `libav*` at the frame level and gives exactly that: decoded frames, real timestamps, and selected-range decoding, independent of whatever a playback widget happens to expose.

**Two independent decoders, not one shared pipeline:** `PlaybackController`'s own docstring states the resulting contract directly — "Qt playback and PyAV analysis never share a decoding pipeline." `timeline_mapping.qt_position_seconds_to_pyav_range` exists only to bound a small lookup window around a requested position (frame boundaries rarely land on an exact float); both decoders already express time as absolute seconds on the same source timeline, so there is no frame-index/fps unit conversion between them, only a tolerance window.

**Bundled FFmpeg CLI via `QProcess` for heavy transforms, not `ffmpeg-python` or a Python transcoding library:** transcoding/muxing is occasional, coarse-grained work, not a hot path — shelling out to a bundled, version-pinned FFmpeg binary keeps the transform boundary's behavior identical to running the same FFmpeg command by hand (directly explainable, matching the Explainability Ceiling), and avoids adding a second in-process video-decoding dependency alongside PyAV for work PyAV isn't meant to do.

## What was rejected, and why

- **PyAV for playback too** — rejected because it would mean re-implementing audio-synced playback, seeking, and Qt UI signal integration on top of raw decode primitives, duplicating what `QMediaPlayer` already provides, for no accuracy benefit (playback doesn't need PTS-exact frame access, only smooth real-time output).
- **`QMediaPlayer`/`QVideoFrame` for algorithmic access** — rejected because Qt Multimedia's frame API is oriented around rendering the *next* frame for display, not repeatable, arbitrary-position, PTS-correct decoding for offline analysis; building Milestone 2's PTS-correctness guarantees on top of it would fight the API's own design intent.
- **A Python-native transcoding library instead of shelling out to FFmpeg** — rejected because it would add a second video-decoding/encoding dependency stack (with its own format-support gaps and licensing questions) for a use case FFmpeg's CLI already solves completely; `QProcess` already gives GlyphCue a supported way to invoke and monitor an external process from Qt.

## Known cost of the choice (accepted, not ignored)

- **Two decoders means two places format/codec incompatibilities can surface** — a file `QMediaPlayer` opens is not automatically guaranteed to open identically in PyAV, or vice versa. No cross-decoder compatibility corpus has been built to systematically catch this; issues would currently surface as real bugs against real user files, not as pre-verified coverage.
- **The FFmpeg-backed `MediaTransformService` has no concrete implementation yet.** Only the Protocol boundary (`src/glyphcue/adapters/media_transform.py`) and its contract test (`tests/adapters/test_contracts.py`) exist as of Milestone 10 — no `QProcess`/FFmpeg-backed class has been built or exercised in practice. This ADR records the intended architecture, not a verified implementation; closing that gap is Milestone 11/12 (Product Hardening / packaging) territory, where the bundled FFmpeg binary itself also needs to be chosen, license-audited, and packaged.
- **Windows standalone packaging must bundle both PyAV's own FFmpeg libraries and, separately, the CLI FFmpeg binary for transforms** — two copies of FFmpeg-derived code in the shipped product, a real packaging-size and licensing-audit cost accepted at roadmap start, to be resolved concretely in Milestone 11/12.

## What remains swappable

Both `MediaFrameSource` and `MediaTransformService` are Protocols; domain/application code depends on the Protocol, never on `av` or `ffmpeg` types directly. A different frame-access or transform backend could be substituted behind either boundary without changing calling code, if future evidence justified it.

## What evidence supported this choice

This decision was made at roadmap design time based on each library's stated purpose and Qt's existing role in the product shell (ROADMAP.md section 3), not from a benchmark comparison — unlike ADR 0001/0002/0003, there is no "candidate A vs. candidate B" evidence run to point to here, only the accumulated real usage across Milestones 2–9 (`PlaybackController`, `PyAvMediaFrameSource`, `timeline_mapping`) confirming the split has held up in practice without needing revision.
