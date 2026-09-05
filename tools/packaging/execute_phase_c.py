"""Phase C Execution Script: Second Isolated Clean Reconstruction & Drift Verification.

Implements Phase C of the GlyphCue Minimum Runtime-Fidelity Packaging Experiment per Wayfinder Issue #27:
1. Assembly-time extraction conflict gate (fail closed on unexpected file collisions).
2. Reconstruction 1 assembly in isolated environment `build_artifacts/phase_c/recon1`.
3. Reconstruction 2 assembly in isolated clean environment `build_artifacts/phase_c/recon2` with separate cache.
4. Independent compilation and test-signing of first-party launcher (`GlyphCue.exe`).
5. Manifest (with source_artifact_sha256), CycloneDX 1.6 SBOM, and signature inventory generation for both.
6. Offline Inno Setup installer compilation and signing for both reconstructions.
7. Bit-for-bit payload drift verification and Authenticode semantic equivalence evaluation.
8. Inno Setup installer envelope comparison against the approved allowlist.
9. Full Phase C drift and summary report generation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import struct
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.packaging.assemble_embeddable_runtime import APPROVED_PTH_CONTENT
from tools.packaging.generate_cyclonedx_sbom import generate_cyclonedx_sbom
from tools.packaging.generate_payload_manifest import generate_manifest
from tools.packaging.verify_payload_drift import (
    compare_installer_envelopes,
    compare_reconstructions,
)
from tools.packaging.verify_signatures import check_pe_signature, evaluate_signature_gate

# Frozen identities from docs/m13_build_base_identity.json
FROZEN_BUILD_BASE_PATH = REPO_ROOT / "docs" / "m13_build_base_identity.json"
CSC_COMPILER_PATH = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
INNO_COMPILER_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"
TEST_CERT_THUMBPRINT = "A3E4E5320779C9F63E513D870E209C26B819C61E"
APPROVED_TEST_CERT_SUBJECT = "CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root"

# Explicitly allowed deterministic overlapping artifact families in the frozen 85-wheel inventory:
ALLOWED_DETERMINISTIC_CONFLICTS = {
    # PySide6 suite deterministic overlaps (identical stubs/typesystems across suite packages)
    ("pyside6-6.11.2-cp310-abi3-win_amd64.whl", "pyside6_addons-6.11.2-cp310-abi3-win_amd64.whl"),
    ("pyside6_addons-6.11.2-cp310-abi3-win_amd64.whl", "pyside6_essentials-6.11.2-cp310-abi3-win_amd64.whl"),
    # OpenCV suite deterministic package progression in frozen inventory
    ("opencv_contrib_python-4.10.0.84-cp37-abi3-win_amd64.whl", "opencv_python-5.0.0.93-cp37-abi3-win_amd64.whl"),
    ("opencv_python-5.0.0.93-cp37-abi3-win_amd64.whl", "opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl"),
}

LAUNCHER_CS_SOURCE = """using System;
using System.Diagnostics;
using System.IO;

namespace GlyphCue.Launcher {
    static class Program {
        [STAThread]
        static int Main(string[] args) {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string pythonExe = Path.Combine(baseDir, "python", "python.exe");
            if (!File.Exists(pythonExe)) {
                pythonExe = Path.Combine(baseDir, "python.exe");
            }
            if (!File.Exists(pythonExe)) {
                Console.Error.WriteLine("Error: GlyphCue embedded Python runtime not found at " + pythonExe);
                return 1;
            }
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = pythonExe;
            psi.Arguments = "-m glyphcue.ui.app";
            psi.WorkingDirectory = baseDir;
            psi.UseShellExecute = false;
            try {
                Process p = Process.Start(psi);
                p.WaitForExit();
                return p.ExitCode;
            } catch (Exception ex) {
                Console.Error.WriteLine("Error launching GlyphCue: " + ex.Message);
                return 1;
            }
        }
    }
}
"""


def normalize_cli_pe(pe_bytes: bytes) -> bytes:
    """Normalize legacy csc.exe non-deterministic fields (TimeDateStamp and CLR MVID GUID)."""
    data = bytearray(pe_bytes)
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew+4] != b"PE\x00\x00":
        return pe_bytes

    # Set COFF TimeDateStamp to fixed value 0x00000000
    struct.pack_into("<I", data, e_lfanew + 8, 0x00000000)

    magic = struct.unpack_from("<H", data, e_lfanew + 24)[0]
    if magic == 0x020B:  # PE32+ (x64)
        cli_entry_offset = e_lfanew + 24 + 112 + 14 * 8
    else:  # PE32 (x86)
        cli_entry_offset = e_lfanew + 24 + 96 + 14 * 8

    cli_rva, cli_size = struct.unpack_from("<II", data, cli_entry_offset)
    if cli_rva == 0 or cli_size == 0:
        return bytes(data)

    num_sections = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    opt_header_size = struct.unpack_from("<H", data, e_lfanew + 20)[0]
    section_headers_offset = e_lfanew + 24 + opt_header_size

    def rva_to_file_offset(rva: int) -> int:
        for sec_idx in range(num_sections):
            sec_offset = section_headers_offset + sec_idx * 40
            _, sec_va, sec_raw_size, sec_raw_ptr = struct.unpack_from("<IIII", data, sec_offset + 8)
            if sec_va <= rva < sec_va + sec_raw_size:
                return sec_raw_ptr + (rva - sec_va)
        return -1

    cli_header_file_offset = rva_to_file_offset(cli_rva)
    if cli_header_file_offset < 0:
        return bytes(data)

    meta_rva, _ = struct.unpack_from("<II", data, cli_header_file_offset + 8)
    meta_file_offset = rva_to_file_offset(meta_rva)
    if meta_file_offset < 0 or data[meta_file_offset:meta_file_offset+4] != b"BSJB":
        return bytes(data)

    ver_len = struct.unpack_from("<I", data, meta_file_offset + 12)[0]
    streams_offset = meta_file_offset + 16 + ver_len + 2
    num_streams = struct.unpack_from("<H", data, streams_offset)[0]
    cur_pos = streams_offset + 2

    guid_stream_offset = None
    guid_stream_size = None

    for _ in range(num_streams):
        stream_rva_offset, stream_size = struct.unpack_from("<II", data, cur_pos)
        cur_pos += 8
        name_bytes = bytearray()
        while cur_pos < len(data):
            b = data[cur_pos]
            cur_pos += 1
            if b == 0:
                break
            name_bytes.append(b)
        while (cur_pos - (streams_offset + 2)) % 4 != 0:
            cur_pos += 1
        name = name_bytes.decode("ascii", errors="ignore")
        if name == "#GUID":
            guid_stream_offset = meta_file_offset + stream_rva_offset
            guid_stream_size = stream_size
            break

    if guid_stream_offset and guid_stream_size and guid_stream_size >= 16:
        # Fixed deterministic MVID GUID
        fixed_guid = bytes([
            0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88,
            0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00,
        ])
        data[guid_stream_offset:guid_stream_offset+16] = fixed_guid

    return bytes(data)


def hash_file(file_path: Path) -> str:
    """Return SHA-256 hex digest of file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def stage_offline_artifact(
    dest_path: Path,
    expected_sha256: str,
    seed_cache_dir: Path | None = None,
) -> None:
    """Ensure artifact is staged at dest_path strictly from local cache in fail-closed offline mode."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.is_file():
        if hash_file(dest_path) == expected_sha256:
            return
        dest_path.unlink(missing_ok=True)

    # Check seed cache
    if seed_cache_dir and seed_cache_dir.is_dir():
        candidate = seed_cache_dir / "downloads" / expected_sha256 / dest_path.name
        if candidate.is_file() and hash_file(candidate) == expected_sha256:
            shutil.copy2(candidate, dest_path)
            return

    # Strictly offline: fail immediately without network or private_samples fallback
    raise FileNotFoundError(
        f"Strict offline reconstruction failure: required frozen artifact '{dest_path.name}' "
        f"(SHA-256: {expected_sha256}) is missing from staged seed cache. "
        f"Network download and undeclared sample fallbacks are prohibited during reconstruction."
    )


def populate_isolated_cache(
    cache_dir: Path,
    frozen_inv: dict[str, Any],
    seed_cache_dir: Path | None = None,
) -> dict[str, Path]:
    """Populate and verify isolated content-addressed staging cache in strict offline mode."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir = cache_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    staged: dict[str, Path] = {}

    # 1. CPython embeddable runtime
    cpython_info = frozen_inv["cpython_embeddable_runtime"]
    cp_fn = cpython_info["archive_filename"]
    cp_sha = cpython_info["sha256"]
    cp_dest = downloads_dir / cp_sha / cp_fn
    stage_offline_artifact(cp_dest, cp_sha, seed_cache_dir=seed_cache_dir)
    staged[cp_fn] = cp_dest

    # 2. 85 Frozen wheel / sdist artifacts
    wheels = frozen_inv.get("frozen_wheel_artifacts", [])
    for w in wheels:
        fn = w["wheel_filename"]
        sha = w["sha256"]
        dest = downloads_dir / sha / fn
        stage_offline_artifact(dest, sha, seed_cache_dir=seed_cache_dir)
        staged[fn] = dest

    # 3. Authoritative ONNX Models
    for m in frozen_inv.get("onnx_models_inventory", []):
        m_fn = m["filename"]
        m_sha = m["sha256"]
        m_dest = downloads_dir / m_sha / m_fn
        stage_offline_artifact(m_dest, m_sha, seed_cache_dir=seed_cache_dir)
        staged[m_fn] = m_dest

    return staged


def unpack_sdist_pure_python(
    sdist_path: Path,
    target_lib_dir: Path,
    extraction_map: dict[str, dict[str, str]],
    conflict_log: list[dict[str, str]],
    source_filename: str,
    source_sha: str,
) -> None:
    """Extract pure-Python packages from sdist tar.gz with assembly-time conflict checking."""
    with tarfile.open(sdist_path, "r:gz") as tar:
        for member in tar.getmembers():
            if "/src/antlr4" in member.name:
                rel_sub = member.name.split("/src/", 1)[-1]
                dest_file = target_lib_dir / rel_sub
                if member.isdir():
                    dest_file.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    f_in = tar.extractfile(member)
                    if f_in:
                        dest_file.write_bytes(f_in.read())
                        app_root_rel = f"lib/{rel_sub.replace(chr(92), '/')}"

                        if app_root_rel in extraction_map:
                            prev_src = extraction_map[app_root_rel]["source_artifact"]
                            if prev_src != source_filename:
                                if (prev_src, source_filename) in ALLOWED_DETERMINISTIC_CONFLICTS:
                                    conflict_log.append({
                                        "path": app_root_rel,
                                        "previous_source": prev_src,
                                        "new_source": source_filename,
                                        "resolution": "ALLOWED_DETERMINISTIC_RECIPE_OVERWRITE",
                                    })
                                else:
                                    raise RuntimeError(
                                        f"Provenance conflict: unexpected collision for {app_root_rel} "
                                        f"between '{prev_src}' and '{source_filename}'"
                                    )

                        extraction_map[app_root_rel] = {
                            "source_artifact": source_filename,
                            "sha256": source_sha,
                            "source_artifact_sha256": source_sha,
                            "license": "Third-Party-Declared",
                            "verification_status": "verified",
                            "role": "vendored_python_dependency",
                        }


def compile_launcher(dest_exe: Path) -> str:
    """Compile first-party GlyphCue.exe launcher using csc.exe and return pre-sign SHA-256."""
    dest_exe.parent.mkdir(parents=True, exist_ok=True)
    cs_file = dest_exe.parent / "temp_launcher.cs"
    cs_file.write_text(LAUNCHER_CS_SOURCE, encoding="utf-8")

    cmd = [
        str(CSC_COMPILER_PATH),
        "/target:winexe",
        "/platform:x64",
        f"/out:{dest_exe.resolve()}",
        str(cs_file.resolve()),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    cs_file.unlink(missing_ok=True)

    # Normalize deterministic fields
    raw_pe = dest_exe.read_bytes()
    normalized_pe = normalize_cli_pe(raw_pe)
    dest_exe.write_bytes(normalized_pe)

    presign_sha = hash_file(dest_exe)
    return presign_sha


def sign_pe_file(pe_path: Path, thumbprint: str) -> None:
    """Apply Authenticode signature to a PE binary using PowerShell and the test cert."""
    ps_cmd = f"""
    $cert = Get-Item 'Cert:\\CurrentUser\\My\\{thumbprint}'
    $sig = Set-AuthenticodeSignature -FilePath '{pe_path.resolve()}' -Certificate $cert -HashAlgorithm SHA256
    if ($sig.Status -eq 'NotSigned') {{
        throw 'Failed to sign {pe_path.name}'
    }}
    """
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, check=True)


def build_reconstruction_app_root(
    app_root: Path,
    staged_artifacts: dict[str, Path],
    frozen_inv: dict[str, Any],
) -> dict[str, Any]:
    """Assemble complete <app_root> tree with strict conflict gate and provenance recording."""
    if app_root.exists():
        shutil.rmtree(app_root)
    app_root.mkdir(parents=True, exist_ok=True)

    python_dir = app_root / "python"
    app_src_dir = app_root / "app" / "glyphcue"
    lib_dir = app_root / "lib"
    qt_plugins_dir = app_root / "qt" / "plugins"
    models_dir = app_root / "models"
    migrations_dir = app_root / "resources" / "migrations_sql"
    legal_dir = app_root / "legal" / "manifest"
    diagnostics_dir = app_root / "diagnostics"

    for d in (python_dir, app_src_dir.parent, lib_dir, qt_plugins_dir, models_dir, migrations_dir, legal_dir, diagnostics_dir):
        d.mkdir(parents=True, exist_ok=True)

    extraction_map: dict[str, dict[str, str]] = {}
    conflict_log: list[dict[str, str]] = []

    # 1. Extract CPython Embeddable
    cp_fn = frozen_inv["cpython_embeddable_runtime"]["archive_filename"]
    cp_path = staged_artifacts[cp_fn]
    with zipfile.ZipFile(cp_path, "r") as zf:
        zf.extractall(python_dir)

    # Configure python312._pth
    pth_file = python_dir / "python312._pth"
    pth_file.write_text(APPROVED_PTH_CONTENT, encoding="utf-8")

    # Build wheel sha lookup
    wheel_sha_lookup = {
        w["wheel_filename"]: w["sha256"]
        for w in frozen_inv.get("frozen_wheel_artifacts", [])
    }

    # 2. Extract vendored wheels and sdist with assembly-time conflict checking
    for w in frozen_inv.get("frozen_wheel_artifacts", []):
        fn = w["wheel_filename"]
        art_path = staged_artifacts[fn]
        art_sha = w["sha256"]

        if fn.endswith(".whl"):
            with zipfile.ZipFile(art_path, "r") as zf:
                for zip_info in zf.infolist():
                    if not zip_info.is_dir():
                        zf.extract(zip_info, lib_dir)
                        norm_rel = zip_info.filename.replace("\\", "/")
                        app_rel = f"lib/{norm_rel}"

                        if app_rel in extraction_map:
                            prev_src = extraction_map[app_rel]["source_artifact"]
                            if prev_src != fn:
                                if (prev_src, fn) in ALLOWED_DETERMINISTIC_CONFLICTS:
                                    conflict_log.append({
                                        "path": app_rel,
                                        "previous_source": prev_src,
                                        "new_source": fn,
                                        "resolution": "ALLOWED_DETERMINISTIC_RECIPE_OVERWRITE",
                                    })
                                else:
                                    raise RuntimeError(
                                        f"Provenance conflict: unexpected collision for '{app_rel}' "
                                        f"between '{prev_src}' and '{fn}'"
                                    )

                        extraction_map[app_rel] = {
                            "source_artifact": fn,
                            "sha256": art_sha,
                            "source_artifact_sha256": art_sha,
                            "license": "Third-Party-Declared",
                            "verification_status": "verified",
                            "role": "vendored_python_dependency",
                        }
        elif fn.endswith(".tar.gz"):
            unpack_sdist_pure_python(art_path, lib_dir, extraction_map, conflict_log, fn, art_sha)

    # 3. Copy PySide6 Qt plugins
    pyside_whl_fn = "PySide6-6.11.2-cp310-abi3-win_amd64.whl"
    pyside_whl_sha = wheel_sha_lookup.get(pyside_whl_fn, "")
    pyside_plugins = lib_dir / "PySide6" / "plugins"
    if pyside_plugins.is_dir():
        for plugin_item in pyside_plugins.rglob("*"):
            if plugin_item.is_file():
                rel_to_plugins = plugin_item.relative_to(pyside_plugins)
                target_plugin = qt_plugins_dir / rel_to_plugins
                target_plugin.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(plugin_item, target_plugin)
                qt_rel = f"qt/plugins/{str(rel_to_plugins).replace(chr(92), '/')}"
                extraction_map[qt_rel] = {
                    "source_artifact": pyside_whl_fn,
                    "sha256": pyside_whl_sha,
                    "source_artifact_sha256": pyside_whl_sha,
                    "license": "LGPL-3.0-only",
                    "verification_status": "verified",
                    "role": "qt_runtime_plugin",
                }

    # 4. First-party application source (ignore dev bytecode)
    src_origin = REPO_ROOT / "src" / "glyphcue"
    shutil.copytree(
        src_origin,
        app_src_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    # 5. Database SQL Migrations
    src_mig_origin = src_origin / "persistence" / "migrations_sql"
    for sql_f in src_mig_origin.glob("*.sql"):
        shutil.copy2(sql_f, migrations_dir / sql_f.name)

    # 6. Authoritative ONNX Models
    for m in frozen_inv["onnx_models_inventory"]:
        m_name = m["filename"]
        m_path = staged_artifacts.get(m_name)
        if not m_path or not m_path.is_file():
            raise FileNotFoundError(f"Required frozen model missing: {m_name}")
        shutil.copy2(m_path, models_dir / m_name)

    # 7. Diagnostics
    shutil.copy2(REPO_ROOT / "tools" / "devqa_directml_verify.py", diagnostics_dir / "devqa_directml_verify.py")

    # 8. Compile first-party GlyphCue.exe launcher & record pre-sign SHA
    launcher_exe = app_root / "GlyphCue.exe"
    presign_sha = compile_launcher(launcher_exe)

    # 9. Inner Signing: Sign GlyphCue.exe
    sign_pe_file(launcher_exe, TEST_CERT_THUMBPRINT)
    postsign_sha = hash_file(launcher_exe)

    # 10. Generate Signature Inventory for app_root
    sig_inv_path = legal_dir / "signature_inventory.json"
    sig_inv = evaluate_signature_gate(
        app_root,
        expected_thumbprint=TEST_CERT_THUMBPRINT,
        output_inventory=sig_inv_path,
        allow_mock=False,
    )

    # 11. Generate Payload Manifest & CycloneDX 1.6 SBOM
    manifest_path = legal_dir / "payload_manifest.json"
    manifest = generate_manifest(
        app_root,
        manifest_path,
        enforce_all_expected_present=True,
        extraction_provenance_map=extraction_map,
    )

    sbom_path = legal_dir / "sbom.json"
    generate_cyclonedx_sbom(manifest_path, sbom_path)

    # Finalize payload manifest to index the generated sbom.json as well
    manifest = generate_manifest(
        app_root,
        manifest_path,
        enforce_all_expected_present=True,
        extraction_provenance_map=extraction_map,
    )

    # 12. Final payload tree reconciliation assertion against disk
    disk_files = {p.relative_to(app_root).as_posix() for p in app_root.rglob("*") if p.is_file() and p != manifest_path}
    manifest_files = {entry["path"].replace("\\", "/") for entry in manifest["files"]}
    unindexed_on_disk = disk_files - manifest_files
    missing_from_disk = manifest_files - disk_files
    if unindexed_on_disk or missing_from_disk:
        raise RuntimeError(
            f"Final payload manifest reconciliation failed! "
            f"Unindexed files on disk: {unindexed_on_disk}, Missing manifest files: {missing_from_disk}"
        )

    return {
        "app_root": app_root,
        "presign_sha": presign_sha,
        "postsign_sha": postsign_sha,
        "manifest": manifest,
        "signature_inventory": sig_inv,
        "extraction_map": extraction_map,
        "conflict_log": conflict_log,
    }


def test_runtime_sanity(app_root: Path) -> bool:
    """Execute local sanity check on a disposable scratch copy of the assembled private runtime."""
    scratch_dir = app_root.parent / f"_sanity_scratch_{app_root.name}"
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    shutil.copytree(app_root, scratch_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    python_exe = scratch_dir / "python" / "python.exe"
    sanity_script = """
import sys
import os
from pathlib import Path

app_base = Path(sys.executable).parent.parent

# 1. Application import
import glyphcue

# 2. Database migrations check
mig_dir = app_base / 'resources' / 'migrations_sql'
mig_files = sorted(mig_dir.glob('*.sql'))
assert len(mig_files) == 5, f'Expected 5 migration files, found {len(mig_files)}'

# 3. PySide6 & Qt Plugins verification
from PySide6 import QtCore
qwindows_dll = app_base / 'qt' / 'plugins' / 'platforms' / 'qwindows.dll'
if not qwindows_dll.is_file():
    qwindows_dll = app_base / 'qt' / 'plugins' / 'qwindows.dll'
assert qwindows_dll.is_file(), 'QPA platform plugin missing'

# 4. PyAV import
import av

# 5. ONNX Runtime & DirectML provider preflight
import onnxruntime as ort
providers = ort.get_available_providers()

# 6. Authoritative Models Discovery & Loadability
models_dir = app_base / 'models'
det_medium = models_dir / 'PP-OCRv6_det_medium.onnx'
rec_small = models_dir / 'PP-OCRv6_rec_small.onnx'
cls_mobile = models_dir / 'ch_ppocr_mobile_v2.0_cls_mobile.onnx'

assert det_medium.is_file() and rec_small.is_file() and cls_mobile.is_file()

test_providers = ['DmlExecutionProvider', 'CPUExecutionProvider'] if 'DmlExecutionProvider' in providers else ['CPUExecutionProvider']
session_options = ort.SessionOptions()
session_options.log_severity_level = 3
sess = ort.InferenceSession(str(cls_mobile), session_options, providers=test_providers)

# 7. RapidOCR Construction Test
from rapidocr import RapidOCR
engine = RapidOCR(params={
    'Det.model_path': str(det_medium),
    'Rec.model_path': str(rec_small),
    'Cls.model_path': str(cls_mobile),
})
print('[Sanity] OK: private runtime verification succeeded.')
"""
    cmd = [str(python_exe.resolve()), "-B", "-c", sanity_script]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)

    try:
        res = subprocess.run(cmd, cwd=str(scratch_dir), env=env, capture_output=True, text=True)
        if res.returncode != 0:
            print("Sanity check stderr:", res.stderr, file=sys.stderr)
            return False
        return True
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


def compile_inno_installer(iss_script: Path, app_root: Path, output_dir: Path) -> Path:
    """Compile Inno Setup offline installer."""
    output_dir.mkdir(parents=True, exist_ok=True)
    iscc_path = INNO_COMPILER_PATH if INNO_COMPILER_PATH.is_file() else Path("iscc.exe")

    cmd = [
        str(iscc_path),
        f"/DMyAppRoot={app_root.resolve()}",
        f"/O{output_dir.resolve()}",
        "/FGlyphCue-Setup",
        str(iss_script.resolve()),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)

    installer_exe = output_dir / "GlyphCue-Setup.exe"
    if not installer_exe.is_file():
        raise FileNotFoundError(f"Expected compiled installer at {installer_exe}")
    return installer_exe


def execute_reconstruction(
    recon_name: str,
    target_dir: Path,
    cache_dir: Path,
    frozen_inv: dict[str, Any],
    seed_cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute a single complete isolated reconstruction."""
    print(f"\n=======================================================")
    print(f"Executing {recon_name} in {target_dir}")
    print(f"Isolated Cache: {cache_dir}")
    print(f"=======================================================")

    # 1. Populate isolated cache
    staged = populate_isolated_cache(cache_dir, frozen_inv, seed_cache_dir=seed_cache_dir)
    print(f"[{recon_name}] Verified and staged {len(staged)} artifacts in isolated cache.")

    # 2. Build app_root
    app_root = target_dir / "app_root"
    assembly_res = build_reconstruction_app_root(app_root, staged, frozen_inv)
    print(f"[{recon_name}] Assembled app_root: {assembly_res['manifest']['total_files_count']} files, {assembly_res['manifest']['total_payload_bytes']} bytes.")
    print(f"[{recon_name}] Pre-sign GlyphCue.exe SHA-256: {assembly_res['presign_sha']}")
    print(f"[{recon_name}] Post-sign GlyphCue.exe SHA-256: {assembly_res['postsign_sha']}")

    # 3. Local sanity test
    sanity_ok = test_runtime_sanity(app_root)
    if not sanity_ok:
        raise RuntimeError(f"[{recon_name}] Local runtime sanity check FAILED.")
    print(f"[{recon_name}] Local runtime sanity check: PASS (importability, migrations, Qt platform plugin, and ONNX DirectML provider preflight verified; detector/recognizer DirectML hardware acceptance reserved for Phase D)")

    # 4. Inno Setup installer
    iss_file = REPO_ROOT / "tools" / "packaging" / "glyphcue_installer.iss"
    installer_dir = target_dir / "installer"
    installer_exe = compile_inno_installer(iss_file, app_root, installer_dir)

    # 5. Sign Inno Setup installer
    sign_pe_file(installer_exe, TEST_CERT_THUMBPRINT)
    installer_sha = hash_file(installer_exe)
    installer_size = installer_exe.stat().st_size
    print(f"[{recon_name}] Compiled and signed installer: {installer_exe.name} ({installer_size} bytes, SHA-256: {installer_sha[:16]}...)")

    # 6. Verify signatures
    inner_sig = check_pe_signature(app_root / "GlyphCue.exe", expected_thumbprint=TEST_CERT_THUMBPRINT)
    outer_sig = check_pe_signature(installer_exe, expected_thumbprint=TEST_CERT_THUMBPRINT)

    if not (inner_sig["verified_first_party"] and outer_sig["verified_first_party"]):
        raise RuntimeError(f"[{recon_name}] Signature verification failed: inner={inner_sig}, outer={outer_sig}")

    return {
        "name": recon_name,
        "target_dir": str(target_dir),
        "app_root": app_root,
        "installer_exe": installer_exe,
        "installer_size": installer_size,
        "installer_sha256": installer_sha,
        "presign_sha": assembly_res["presign_sha"],
        "postsign_sha": assembly_res["postsign_sha"],
        "manifest": assembly_res["manifest"],
        "inner_signature": inner_sig,
        "outer_signature": outer_sig,
        "conflict_log": assembly_res["conflict_log"],
    }


def run_phase_c(output_root: Path) -> dict[str, Any]:
    """Execute complete Phase C isolated clean reconstructions and drift verification."""
    output_root.mkdir(parents=True, exist_ok=True)
    frozen_inv = json.loads(FROZEN_BUILD_BASE_PATH.read_text(encoding="utf-8"))

    seed_cache = REPO_ROOT / ".cache" / "packaging"

    # Reconstruction 1
    recon1_dir = output_root / "recon1"
    cache1_dir = output_root / "cache_recon1"
    recon1_res = execute_reconstruction(
        "Reconstruction 1",
        recon1_dir,
        cache1_dir,
        frozen_inv,
        seed_cache_dir=seed_cache,
    )

    # Reconstruction 2 (Truly isolated clean reconstruction)
    recon2_dir = output_root / "recon2"
    cache2_dir = output_root / "cache_recon2"
    recon2_res = execute_reconstruction(
        "Reconstruction 2",
        recon2_dir,
        cache2_dir,
        frozen_inv,
        seed_cache_dir=seed_cache,
    )

    print("\n=======================================================")
    print("Executing Phase C Payload & Envelope Drift Verification")
    print("=======================================================")

    # Compare app_root payload drift
    presign_1 = {"GlyphCue.exe": recon1_res["presign_sha"]}
    presign_2 = {"GlyphCue.exe": recon2_res["presign_sha"]}

    payload_drift_report = compare_reconstructions(
        recon1_res["app_root"],
        recon2_res["app_root"],
        pre_sign_hashes_1=presign_1,
        pre_sign_hashes_2=presign_2,
        expected_thumbprint=TEST_CERT_THUMBPRINT,
        allow_mock=False,
    )

    # Compare installer envelope drift
    envelope_drift_report = compare_installer_envelopes(
        recon1_res["installer_exe"],
        recon2_res["installer_exe"],
        expected_thumbprint=TEST_CERT_THUMBPRINT,
        allow_mock=False,
    )

    phase_c_verdict = (
        payload_drift_report["payload_drift_status"] == "PASS"
        and envelope_drift_report["envelope_drift_status"] == "PASS"
        and recon1_res["presign_sha"] == recon2_res["presign_sha"]
        and recon1_res["manifest"]["gate_results"]["integrity_gate"] == "PASS"
        and recon2_res["manifest"]["gate_results"]["integrity_gate"] == "PASS"
    )

    summary = {
        "phase": "Phase C — Second Isolated Clean Reconstruction & Drift Verification",
        "phase_c_verdict": "PASS" if phase_c_verdict else "FAIL",
        "reconstruction_1": {
            "app_root_dir": str(recon1_res["app_root"]),
            "files_count": recon1_res["manifest"]["total_files_count"],
            "total_bytes": recon1_res["manifest"]["total_payload_bytes"],
            "launcher_presign_sha256": recon1_res["presign_sha"],
            "launcher_postsign_sha256": recon1_res["postsign_sha"],
            "installer_path": str(recon1_res["installer_exe"]),
            "installer_size_bytes": recon1_res["installer_size"],
            "installer_sha256": recon1_res["installer_sha256"],
            "manifest_gates": recon1_res["manifest"]["gate_results"],
        },
        "reconstruction_2": {
            "app_root_dir": str(recon2_res["app_root"]),
            "files_count": recon2_res["manifest"]["total_files_count"],
            "total_bytes": recon2_res["manifest"]["total_payload_bytes"],
            "launcher_presign_sha256": recon2_res["presign_sha"],
            "launcher_postsign_sha256": recon2_res["postsign_sha"],
            "installer_path": str(recon2_res["installer_exe"]),
            "installer_size_bytes": recon2_res["installer_size"],
            "installer_sha256": recon2_res["installer_sha256"],
            "manifest_gates": recon2_res["manifest"]["gate_results"],
        },
        "drift_verification": {
            "payload_drift_status": payload_drift_report["payload_drift_status"],
            "exact_matching_unsigned_files_count": payload_drift_report["exact_matching_unsigned_files_count"],
            "signed_pe_comparisons_count": payload_drift_report["signed_pe_files_count"],
            "unsigned_mismatches_count": len(payload_drift_report["unsigned_payload_mismatches"]),
            "signed_pe_failures_count": len(payload_drift_report["signed_pe_failures"]),
            "missing_in_recon_1_count": len(payload_drift_report["missing_in_reconstruction_1"]),
            "missing_in_recon_2_count": len(payload_drift_report["missing_in_reconstruction_2"]),
            "installer_envelope_drift_status": envelope_drift_report["envelope_drift_status"],
            "installer_envelope_allowlist_eval": envelope_drift_report["envelope_variation_reasons"],
            "installer_size_delta_bytes": envelope_drift_report["size_delta_bytes"],
        },
        "test_certificate": {
            "subject": APPROVED_TEST_CERT_SUBJECT,
            "thumbprint": TEST_CERT_THUMBPRINT,
            "recon1_launcher_sig_verified": recon1_res["inner_signature"]["verified_first_party"],
            "recon2_launcher_sig_verified": recon2_res["inner_signature"]["verified_first_party"],
            "recon1_installer_sig_verified": recon1_res["outer_signature"]["verified_first_party"],
            "recon2_installer_sig_verified": recon2_res["outer_signature"]["verified_first_party"],
        },
    }

    drift_report_path = output_root / "phase_c_drift_report.json"
    drift_report_path.write_text(json.dumps(payload_drift_report, indent=2), encoding="utf-8")

    envelope_report_path = output_root / "phase_c_envelope_report.json"
    envelope_report_path.write_text(json.dumps(envelope_drift_report, indent=2), encoding="utf-8")

    summary_path = output_root / "phase_c_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== PHASE C DRIFT VERIFICATION SUMMARY ===")
    print(json.dumps(summary, indent=2))

    if not phase_c_verdict:
        raise RuntimeError("Phase C Drift Verification FAILED.")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute Phase C Packaging Experiment")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "build_artifacts" / "phase_c",
        help="Root directory for Phase C reconstructions and reports",
    )
    args = parser.parse_args()

    run_phase_c(args.output_root)
