"""Fail-closed guard: no GPL-only FFmpeg codec library may ship in the packaged app_root.

Context (docs/v1_public_distribution_gate_a_compliance_audit.md): PyAV 18.1.0's
official Windows wheel vendors an FFmpeg build compiled with --enable-gpl
(confirmed by the presence of libx264/libx265, GPL-2.0-or-later encoders).
FFmpeg's own licensing policy is that enabling any GPL-only component makes
the GPL apply to the FFmpeg build as a whole -- removing just the external
codec DLLs after the fact does not relicense the remaining avcodec/avformat/
avutil binaries back to LGPL, because they were compiled under a GPL-enabled
configuration. The only real fix is packaging a verified LGPL-only FFmpeg
build in place of PyAV's vendored one (see LGPL_FFMPEG_PROVENANCE below,
validated under build_artifacts/v1_gate_a/lgpl_pyav_test/).

This module provides the fail-closed check that the real packaging pipeline
must pass before a public installer may ship: no forbidden GPL-only codec
library filename may be present anywhere in the assembled app_root.
"""

from __future__ import annotations

from pathlib import Path

# Verified, pinned identity of the LGPL-only FFmpeg build validated as a
# drop-in replacement for PyAV 18.1.0's vendored FFmpeg on Windows.
# See docs/v1_public_distribution_gate_a_compliance_audit.md Section 4.1
# (revised) for the full validation record.
LGPL_FFMPEG_PROVENANCE = {
    "project": "BtbN/FFmpeg-Builds",
    "release_tag": "autobuild-2026-09-06-13-06",
    "asset_filename": "ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-shared-8.1.zip",
    "source_url": (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
        "autobuild-2026-09-06-13-06/"
        "ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-shared-8.1.zip"
    ),
    "archive_sha256": "0f86693cd5b8bcc61296cdbfd38c98817dd5491fa81a28b44b7e0a86965043fb",
    "ffmpeg_version": "n8.1.2-50-g1a748fe2cd-20260906",
    "license": "LGPL-3.0-only (LICENSE.txt in the archive; --enable-version3, no --enable-gpl)",
    "confirmed_disabled_codecs": ["--disable-libx264", "--disable-libx265"],
    "matched_pyav_version": "18.1.0",
    "matched_soname_versions": {
        "avutil": 60,
        "avcodec": 62,
        "avformat": 62,
        "avdevice": 62,
        "avfilter": 11,
        "swscale": 9,
        "swresample": 6,
    },
    "validation_evidence_dir": "build_artifacts/v1_gate_a/lgpl_pyav_test/",
    "validation_result": (
        "PyAV 18.1.0 loaded successfully against these DLLs; decoded frame "
        "count, PTS sequence, and decoded frame bytes (SHA-256 of raw RGB24 "
        "arrays) on docs/m13_synthetic_fixture_golden.json's canonical fixture "
        "are byte-identical to the GPL-configured baseline. No downstream OCR "
        "smoke was required per the bounded-verification rule (frame bytes did "
        "not materially differ)."
    ),
}

# Filename substrings that indicate a GPL-only (or GPL-2.0+-licensed)
# FFmpeg-adjacent codec library. Matched case-insensitively against the
# filename only (not full path) so vendored copies under any directory are
# caught.
_FORBIDDEN_GPL_CODEC_FILENAME_SUBSTRINGS = (
    "libx264",
    "libx265",
    "libxvid",
    "librubberband",
)


def scan_for_forbidden_gpl_codec_libraries(app_root: Path) -> list[str]:
    """Return repo-relative paths of any forbidden GPL-only codec library found."""
    app_root = app_root.resolve()
    hits: list[str] = []
    for p in app_root.rglob("*"):
        if not p.is_file():
            continue
        lower_name = p.name.lower()
        if any(substr in lower_name for substr in _FORBIDDEN_GPL_CODEC_FILENAME_SUBSTRINGS):
            hits.append(str(p.relative_to(app_root)).replace("\\", "/"))
    return hits


def assert_no_gpl_ffmpeg_codec_libraries(app_root: Path) -> None:
    """Fail closed if any forbidden GPL-only codec library is present in app_root."""
    hits = scan_for_forbidden_gpl_codec_libraries(app_root)
    if hits:
        preview = ", ".join(hits[:5])
        raise RuntimeError(
            f"GPL-only FFmpeg codec library(ies) found in packaged app_root: {preview}. "
            f"This build cannot ship publicly under GlyphCue's LGPL-only FFmpeg policy "
            f"(see docs/v1_public_distribution_gate_a_compliance_audit.md). "
            f"Replace the vendored FFmpeg with the pinned LGPL build recorded in "
            f"LGPL_FFMPEG_PROVENANCE before packaging."
        )
