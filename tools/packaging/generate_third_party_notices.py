"""Generate the third-party compliance surface inside a packaged app_root.

Produces the consolidated third-party notice document (and copies the
underlying license texts) that must accompany the *distributed
application* (docs/v1_public_distribution_gate_a_compliance_audit.md
Section 4.4: a GitHub repository entry alone does not satisfy an MIT/BSD/
Apache-2.0 "include this notice in copies" obligation, since installer end
users generally never visit the repository). Everything this module writes
lands inside app_root/legal/, shipped with the installed application.

Two things are produced:
1. app_root/legal/THIRD-PARTY-NOTICES.txt -- one consolidated document:
   GlyphCue's own MIT notice, special-cased sections for the components the
   compliance audit called out as needing more than a one-line notice
   (PySide6/Qt + Qt Multimedia FFmpeg, the pinned LGPL-only PyAV FFmpeg
   replacement, CPython, ONNX Runtime/DirectML, the Paddle/PaddleX/
   PaddleOCR/RapidOCR/OpenCV family and the five frozen OCR model assets,
   crc32c, certifi), then a full list of every other vendored package and
   its declared license.
2. app_root/legal/third_party_licenses/<dist-info-dir>/... -- a verbatim
   copy of every vendored wheel's own bundled license file(s) (standard
   PEP 639 `*.dist-info/licenses/` folder), plus the full LGPL-3.0 and
   Apache-2.0 texts under third_party_licenses/_full_texts/, so the actual
   license texts ship with the application rather than only being linked.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

_LGPLV3_NOTICE = """\
This application includes the following software licensed under the GNU
Lesser General Public License, version 3 (LGPL-3.0-only), linked
dynamically (as separate .dll files, never statically merged into
GlyphCue.exe). Full license text: legal/third_party_licenses/_full_texts/lgpl-3.0.txt

  - PySide6 / PySide6-Addons / PySide6-Essentials / shiboken6 (Qt for
    Python) 6.11.2 -- Copyright (C) The Qt Company Ltd. and contributors.
    Source: https://pypi.org/project/PySide6/
  - The LGPL-only FFmpeg build used by PyAV's decode path -- see the
    "FFmpeg (PyAV decode path)" section below for its exact provenance.
  - Qt Multimedia's own bundled FFmpeg backend (ffmpegmediaplugin.dll) --
    Copyright (c) FFmpeg developers, distributed by The Qt Company under
    LGPL-2.1-or-later per Qt's own attribution:
    https://doc.qt.io/qt-6/qtmultimedia-attribution-ffmpeg.html
  - crc32c 2.9 -- Copyright (c) the crc32c project contributors.

You may obtain, inspect, and replace GlyphCue's copies of these libraries:
they ship as separate files under this application's install directory
(`lib\\`, `qt\\`, and `lib\\av.libs\\`), not embedded inside GlyphCue.exe.
"""

_FFMPEG_PYAV_SECTION_TEMPLATE = """\
FFmpeg (PyAV decode path)
--------------------------
GlyphCue's video decoding (via PyAV) uses FFmpeg shared libraries built and
distributed by the BtbN/FFmpeg-Builds project
(https://github.com/BtbN/FFmpeg-Builds), configured explicitly WITHOUT any
GPL-only component (--disable-libx264 --disable-libx265, no --enable-gpl),
licensed under the GNU Lesser General Public License, version 3.

  FFmpeg version:        {ffmpeg_version}
  FFmpeg source commit:  {ffmpeg_source_git_commit}
  Build source archive:  {archive_filename}
  Archive SHA-256:       {archive_sha256}
  Original download URL: {source_url}

A corresponding-source package for this exact FFmpeg build (matching
source code, license, and build/configure provenance) is published
alongside GlyphCue's installer as a GitHub Release asset, per FFmpeg's own
distribution-compliance guidance (https://www.ffmpeg.org/legal.html),
rather than only linked to a mutable upstream page.

PyAV itself (the Pythonic FFmpeg bindings GlyphCue calls) is licensed
under the BSD-3-Clause license -- Copyright (c) 2017-2026 PyAV
contributors. Source: https://github.com/PyAV-Org/PyAV
"""

_MODEL_ASSETS_SECTION = """\
OCR Model Assets (Apache License 2.0)
--------------------------------------
GlyphCue redistributes five OCR model weight files, all part of the
PaddleOCR PP-OCRv6 model family, licensed under the Apache License 2.0.
Full text: legal/third_party_licenses/_full_texts/apache-2.0.txt

Chain of custody: PaddlePaddle/PaddleOCR trains and publishes PP-OCRv6
under Apache-2.0; PaddleX hosts the official Paddle-format inference
archives; RapidOCR independently converts the same model family to ONNX
format and republishes on ModelScope, also under Apache-2.0. See
docs/v1_public_distribution_gate_a_compliance_audit.md Section 3 (in the
source repository) for the full independently-verified hash chain.

  - PP-OCRv6_det_medium.onnx
  - PP-OCRv6_rec_small.onnx
  - ch_ppocr_mobile_v2.0_cls_mobile.onnx
  - PP-OCRv6_medium_det_infer.tar (Paddle CPU fallback)
  - PP-OCRv6_medium_rec_infer.tar (Paddle CPU fallback)
"""

_APACHE_2_0_HEADER = """\
Apache License 2.0
---------------------
Applies to: PaddlePaddle, PaddleOCR, PaddleX, RapidOCR, OpenCV
(opencv-python / opencv-contrib-python / opencv-python-headless), the five
OCR model assets above, and every other vendored Python package below
whose license is listed as Apache-2.0.
Full text: legal/third_party_licenses/_full_texts/apache-2.0.txt
"""

_CPYTHON_SECTION = """\
CPython (Python interpreter runtime)
--------------------------------------
GlyphCue bundles an embeddable CPython 3.12.10 runtime under the PSF
License Agreement (Python Software Foundation), which permits
redistribution of binary builds. See python\\LICENSE.txt in this
installed application for the complete PSF license text bundled with the
official python.org embeddable distribution.
"""

_ONNXRUNTIME_DIRECTML_SECTION = """\
ONNX Runtime (DirectML build) and DirectML.dll
-------------------------------------------------
  - onnxruntime-directml 1.24.4 -- MIT License. Copyright (c) Microsoft
    Corporation. Source: https://github.com/microsoft/onnxruntime
  - DirectML.dll -- MIT License. Copyright (c) Microsoft Corporation.
    Source: https://github.com/microsoft/DirectML
"""

_CERTIFI_SECTION = """\
certifi (Mozilla CA bundle)
------------------------------
certifi 2026.7.22 is licensed under the Mozilla Public License 2.0
(file-level weak copyleft; this obligation applies only to certifi's own
files, not to GlyphCue's own source). Full text:
https://www.mozilla.org/en-US/MPL/2.0/
"""


def _copy_full_license_texts(dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in ("lgpl-3.0.txt", "apache-2.0.txt"):
        src = REPO_ROOT / "docs" / "licenses" / name
        if src.is_file():
            shutil.copy2(src, dest_dir / name)


def _copy_vendored_wheel_licenses(app_root: Path, dest_root: Path) -> list[str]:
    """Copy every vendored wheel's own bundled license file(s) into dest_root,
    one subdirectory per dist-info directory. Returns the list of dist-info
    directory names actually copied."""
    lib_dir = app_root / "lib"
    if not lib_dir.is_dir():
        return []
    copied: list[str] = []
    for dist_info_dir in sorted(lib_dir.glob("*.dist-info")):
        licenses_src = dist_info_dir / "licenses"
        if licenses_src.is_dir():
            dest = dest_root / dist_info_dir.name
            shutil.copytree(licenses_src, dest, dirs_exist_ok=True)
            copied.append(dist_info_dir.name)
    return copied


def generate_third_party_notices(app_root: Path, manifest: dict[str, Any]) -> Path:
    """Write app_root/legal/THIRD-PARTY-NOTICES.txt and the accompanying
    third_party_licenses/ tree. Returns the path to the notices file."""
    lgpl_report_path = app_root / "legal" / "manifest" / "lgpl_ffmpeg_replacement.json"
    if lgpl_report_path.is_file():
        lgpl_report = json.loads(lgpl_report_path.read_text(encoding="utf-8"))
    else:
        lgpl_report = {"ffmpeg_version": "UNKNOWN", "ffmpeg_source_git_commit": "UNKNOWN"}

    from tools.packaging.lgpl_ffmpeg_replacement import LGPL_FFMPEG_ARCHIVE

    third_party_licenses_dir = app_root / "legal" / "third_party_licenses"
    _copy_full_license_texts(third_party_licenses_dir / "_full_texts")
    copied_dist_infos = _copy_vendored_wheel_licenses(app_root, third_party_licenses_dir)

    sections: list[str] = []
    sections.append(
        "GlyphCue — Third-Party Notices\n"
        "================================\n\n"
        "GlyphCue's own source code is licensed under the MIT License (see the\n"
        "LICENSE file included with this application). This document lists the\n"
        "third-party software GlyphCue redistributes as part of its installed\n"
        "application, and the license terms and notices each requires. Verbatim\n"
        "upstream license texts are provided under\n"
        "legal/third_party_licenses/ alongside this file.\n"
    )
    sections.append(_LGPLV3_NOTICE)
    sections.append(
        _FFMPEG_PYAV_SECTION_TEMPLATE.format(
            ffmpeg_version=lgpl_report.get("ffmpeg_version", "UNKNOWN"),
            ffmpeg_source_git_commit=lgpl_report.get("ffmpeg_source_git_commit", "UNKNOWN"),
            archive_filename=LGPL_FFMPEG_ARCHIVE["archive_filename"],
            archive_sha256=LGPL_FFMPEG_ARCHIVE["archive_sha256"],
            source_url=LGPL_FFMPEG_ARCHIVE["source_url"],
        )
    )
    sections.append(_MODEL_ASSETS_SECTION)
    sections.append(_APACHE_2_0_HEADER)
    sections.append(_CPYTHON_SECTION)
    sections.append(_ONNXRUNTIME_DIRECTML_SECTION)
    sections.append(_CERTIFI_SECTION)

    lines = ["Vendored Python Package Licenses (from installed package metadata)", "-" * 68]
    seen_dist_info: set[str] = set()
    for entry in manifest.get("files", []):
        if entry.get("role") != "vendored_python_dependency":
            continue
        source_artifact = entry.get("source_artifact", "")
        if not source_artifact or source_artifact in seen_dist_info:
            continue
        seen_dist_info.add(source_artifact)
        lines.append(f"  - {source_artifact} (license: {entry.get('license', 'UNKNOWN')})")
    lines.append("")
    lines.append(f"({len(copied_dist_infos)} of these packages' own bundled license file(s) are")
    lines.append("copied verbatim under legal/third_party_licenses/<package>.dist-info/)")
    sections.append("\n".join(lines))

    content = "\n\n".join(sections)
    out_path = app_root / "legal" / "THIRD-PARTY-NOTICES.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path
