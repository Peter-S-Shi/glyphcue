"""Deterministic replacement of PyAV's vendored GPL-configured FFmpeg build
with a verified LGPL-only build, for the v1.0.0 Public Distribution Gate.

Context (docs/v1_public_distribution_gate_a_compliance_audit.md Section 4.1):
PyAV 18.1.0's official Windows wheel vendors an FFmpeg build compiled with
--enable-gpl (confirmed by libx264/libx265 presence). FFmpeg's own licensing
policy makes the entire compiled build GPL-2.0-or-later as a whole once
--enable-gpl is used -- stripping the external codec DLLs afterward does not
relicense the core avcodec/avformat/etc. binaries back to LGPL. This module
performs the verified fix instead: swap the 7 core FFmpeg DLLs for a pinned,
independently-verified LGPL-only build with matching SO-version numbers, and
remove the now-superfluous GPL-build auxiliary codec/runtime DLLs.

This is packaging-time only. PyAV 18.1.0 itself, GlyphCue's media
architecture, and glyphcue.adapters.pyav_media_source are unchanged.
"""

from __future__ import annotations

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

# Pinned, independently-verified LGPL-only FFmpeg build. See
# docs/v1_public_distribution_gate_a_compliance_audit.md Section 4.1 and
# docs/v1_public_release_dependency_provenance.json for the full verification
# record (archive LICENSE.txt confirmed LGPLv3; ffmpeg.exe -version confirmed
# --disable-libx264 --disable-libx265 with no --enable-gpl in the reported
# configure string).
LGPL_FFMPEG_ARCHIVE = {
    "source_url": (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
        "autobuild-2026-09-06-13-06/"
        "ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-shared-8.1.zip"
    ),
    "archive_filename": "ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-shared-8.1.zip",
    "archive_sha256": "0f86693cd5b8bcc61296cdbfd38c98817dd5491fa81a28b44b7e0a86965043fb",
    "extracted_root_dirname": "ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-shared-8.1",
    "ffmpeg_source_git_commit": "1a748fe2cd",
    "ffmpeg_version": "n8.1.2-50-g1a748fe2cd-20260906",
}

# Expected SHA-256 of each of the 7 core FFmpeg DLLs *from the pinned LGPL
# archive itself* -- the strong identity check. Filename-pattern matching
# alone (e.g. "no libx264 present") is not sufficient evidence that
# avcodec/avformat actually came from this build; a GPL-configured core
# build with the codec DLLs simply deleted would still pass a filename-only
# check. This dict is what verify_no_gpl_ffmpeg_codecs.py's
# assert_lgpl_ffmpeg_core_identities() checks the *installed* DLLs against.
EXPECTED_LGPL_CORE_DLL_SHA256 = {
    "avutil-60.dll": "9b41bf41515bac464b2360cd0eb8bdbf60a2fd2d2e57b56b890c45449e4b0cf0",
    "avcodec-62.dll": "43c1b8c0095b40b6ef4866a702997f689c0759b3043a34f49c7d76848e221485",
    "avformat-62.dll": "9c76c9f6b847152b9ef93f4f9964f5633eb27838c60778e04928f4499ae94767",
    "avdevice-62.dll": "e83f4c1930c210be9b7c1558ac798418452fcc383b550dd55a10c4ba0eb41bb1",
    "avfilter-11.dll": "744fdd880e3ab08d28a8181c70df6e42c59c9f5c2775107545964a4cef64583e",
    "swscale-9.dll": "1c58300c596d53ff5ac55ece65008bc74c9d28464442bf3bdb676049c1d476aa",
    "swresample-6.dll": "927752b1918e7e99c39003e03609e507e3d649cf20916911800b9ecaaeecbf1c",
}

# Auxiliary DLLs the GPL-configured PyAV wheel vendors that the LGPL build
# does not need (confirmed by PE import-table inspection: none of the 7 LGPL
# core DLLs import any of these -- they are fully statically self-contained).
# Removing these both eliminates the GPL-tier codecs (libx264/libx265) and
# sheds now-dead weight.
SUPERSEDED_AUXILIARY_DLL_PREFIXES = (
    "libx264",
    "libx265",
    "libvpx",
    "libwebp",
    "libwebpmux",
    "libopus",
    "libmp3lame",
    "libdav1d",
    "libsvtav1enc",
    "libvpl",
    "libopencore-amrnb",
    "libopencore-amrwb",
    "libsharpyuv",
    "libiconv",
    "libgcc_s_seh",
    "libwinpthread",
    "zlib1",
    "libstdc++",
)


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_and_verify_lgpl_ffmpeg_archive(cache_dir: Path) -> Path:
    """Download (if not already cached) and verify the pinned LGPL FFmpeg archive."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / LGPL_FFMPEG_ARCHIVE["archive_filename"]

    if dest.is_file() and hash_file(dest) == LGPL_FFMPEG_ARCHIVE["archive_sha256"]:
        return dest

    req = urllib.request.Request(
        LGPL_FFMPEG_ARCHIVE["source_url"],
        headers={"User-Agent": "GlyphCue-v1-Public-Distribution/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out_f:
        shutil.copyfileobj(resp, out_f)

    actual_sha = hash_file(dest)
    if actual_sha != LGPL_FFMPEG_ARCHIVE["archive_sha256"]:
        dest.unlink(missing_ok=True)
        raise ValueError(
            f"LGPL FFmpeg archive SHA-256 mismatch: expected "
            f"{LGPL_FFMPEG_ARCHIVE['archive_sha256']}, got {actual_sha}. "
            f"Refusing to extract an unverified archive."
        )
    return dest


def _find_av_libs_dir(app_root: Path) -> Path:
    candidates = [app_root / "lib" / "av.libs", app_root / "app" / "lib" / "av.libs"]
    for c in candidates:
        if c.is_dir():
            return c
    found = list(app_root.rglob("av.libs"))
    if len(found) == 1 and found[0].is_dir():
        return found[0]
    raise FileNotFoundError(
        f"Could not locate exactly one 'av.libs' directory under {app_root} "
        f"(PyAV's vendored FFmpeg location) -- found: {found}"
    )


def apply_lgpl_ffmpeg_replacement(app_root: Path, archive_path: Path) -> dict[str, Any]:
    """Replace PyAV's vendored GPL-configured FFmpeg core DLLs with the pinned
    LGPL-only build inside app_root, and remove the now-superseded auxiliary
    codec/runtime DLLs. Fails closed on any provenance or identity mismatch.

    Returns a report dict suitable for recording in the v1.0.0 public-release
    provenance inventory.
    """
    actual_archive_sha = hash_file(archive_path)
    if actual_archive_sha != LGPL_FFMPEG_ARCHIVE["archive_sha256"]:
        raise ValueError(
            f"LGPL FFmpeg archive at {archive_path} does not match pinned SHA-256 "
            f"(expected {LGPL_FFMPEG_ARCHIVE['archive_sha256']}, got {actual_archive_sha}). "
            f"Refusing to apply replacement from unverified archive."
        )

    av_libs_dir = _find_av_libs_dir(app_root)

    extract_dir = archive_path.parent / "_extracted"
    if extract_dir.is_dir():
        shutil.rmtree(extract_dir)
    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(extract_dir)

    lgpl_bin_dir = extract_dir / LGPL_FFMPEG_ARCHIVE["extracted_root_dirname"] / "bin"
    if not lgpl_bin_dir.is_dir():
        raise FileNotFoundError(
            f"Expected LGPL FFmpeg bin directory not found after extraction: {lgpl_bin_dir}"
        )

    replaced: dict[str, str] = {}
    for plain_name, expected_sha in EXPECTED_LGPL_CORE_DLL_SHA256.items():
        src = lgpl_bin_dir / plain_name
        if not src.is_file():
            raise FileNotFoundError(f"Expected LGPL FFmpeg DLL missing from archive: {plain_name}")
        actual_sha = hash_file(src)
        if actual_sha != expected_sha:
            raise ValueError(
                f"LGPL FFmpeg DLL {plain_name} does not match pinned SHA-256 "
                f"(expected {expected_sha}, got {actual_sha}). Archive contents "
                f"do not match the verified provenance record."
            )

        # Deterministically locate the delvewheel-mangled filename PyAV's
        # compiled extension actually references (e.g.
        # "avutil-60-<hash>.dll"), matched by exact plain-name prefix so
        # "avcodec-62" never matches "avdevice-62"-style DLLs.
        stem = plain_name[: -len(".dll")]
        mangled_matches = [
            p for p in av_libs_dir.glob(f"{stem}-*.dll") if p.name != plain_name
        ]
        if len(mangled_matches) != 1:
            raise RuntimeError(
                f"Expected exactly one delvewheel-mangled match for {stem}-*.dll "
                f"in {av_libs_dir}, found {len(mangled_matches)}: {mangled_matches}"
            )
        mangled_path = mangled_matches[0]

        shutil.copy2(src, mangled_path)
        shutil.copy2(src, av_libs_dir / plain_name)
        replaced[plain_name] = mangled_path.name

    removed: list[str] = []
    for p in sorted(av_libs_dir.iterdir()):
        if not p.is_file():
            continue
        lower_name = p.name.lower()
        if any(lower_name.startswith(prefix) for prefix in SUPERSEDED_AUXILIARY_DLL_PREFIXES):
            p.unlink()
            removed.append(p.name)

    shutil.rmtree(extract_dir, ignore_errors=True)

    return {
        "av_libs_dir": str(av_libs_dir.relative_to(app_root)),
        "archive_sha256": actual_archive_sha,
        "replaced_core_dlls": replaced,
        "removed_auxiliary_dlls": removed,
        "ffmpeg_version": LGPL_FFMPEG_ARCHIVE["ffmpeg_version"],
        "ffmpeg_source_git_commit": LGPL_FFMPEG_ARCHIVE["ffmpeg_source_git_commit"],
    }
