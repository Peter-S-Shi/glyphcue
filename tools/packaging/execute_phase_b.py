"""Phase B Execution Script: Primary Runtime Assembly & First Installer Build.

Implements Phase B of the GlyphCue Minimum Runtime-Fidelity Packaging Experiment:
1. Content-addressed local staging cache population with strict SHA-256 verification.
2. Real CPython 3.12.10 embeddable runtime assembly with python312._pth isolation.
3. Real first-party GlyphCue.exe launcher compilation using csc.exe.
4. Pre-sign evidence recording and inner-to-outer test signing.
5. Local runtime sanity check (import & initialization without system Python).
6. Payload manifest (payload_manifest.json) and CycloneDX 1.6 SBOM (sbom.json) generation.
7. Inno Setup 6 offline installer compilation and outer signature application.
8. Complete Phase B artifact & verification reporting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
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
from tools.packaging.verify_signatures import check_pe_signature, evaluate_signature_gate

# Frozen identities from docs/m13_build_base_identity.json
FROZEN_BUILD_BASE_PATH = REPO_ROOT / "docs" / "m13_build_base_identity.json"
CSC_COMPILER_PATH = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
INNO_COMPILER_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"
TEST_CERT_THUMBPRINT = "A3E4E5320779C9F63E513D870E209C26B819C61E"
APPROVED_TEST_CERT_SUBJECT = "CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root"

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


def hash_file(file_path: Path) -> str:
    """Return SHA-256 hex digest of file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def download_and_verify(url: str, dest_path: Path, expected_sha256: str) -> None:
    """Download a file to dest_path and verify its SHA-256 hash."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.is_file():
        actual_sha = hash_file(dest_path)
        if actual_sha == expected_sha256:
            return

    req = urllib.request.Request(url, headers={"User-Agent": "GlyphCue-Packaging-Experiment/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest_path, "wb") as out_f:
        shutil.copyfileobj(resp, out_f)

    actual_sha = hash_file(dest_path)
    if actual_sha != expected_sha256:
        dest_path.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 mismatch for {dest_path.name}: expected {expected_sha256}, got {actual_sha}"
        )


def populate_staging_cache(cache_dir: Path, frozen_inv: dict[str, Any]) -> dict[str, Path]:
    """Populate content-addressed staging cache for all frozen artifacts (wheels, runtime, models)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir = cache_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    downloaded_artifacts: dict[str, Path] = {}

    # 1. CPython embeddable runtime
    cpython_info = frozen_inv["cpython_embeddable_runtime"]
    cp_fn = cpython_info["archive_filename"]
    cp_sha = cpython_info["sha256"]
    cp_url = cpython_info["source_url"]
    cp_dest = downloads_dir / cp_sha / cp_fn
    print(f"Downloading & verifying CPython runtime: {cp_fn}...")
    download_and_verify(cp_url, cp_dest, cp_sha)
    downloaded_artifacts[cp_fn] = cp_dest

    # 2. Frozen wheels & sdist
    wheels = frozen_inv.get("frozen_wheel_artifacts", [])
    print(f"Populating cache with {len(wheels)} frozen dependency artifacts...")
    for idx, w in enumerate(wheels, 1):
        fn = w["wheel_filename"]
        sha = w["sha256"]
        url = w["download_url"]
        dest = downloads_dir / sha / fn
        download_and_verify(url, dest, sha)
        downloaded_artifacts[fn] = dest
        if idx % 15 == 0 or idx == len(wheels):
            print(f"  [{idx}/{len(wheels)}] Verified {fn}")

    # 3. Authoritative ONNX Models
    # Model download URLs (authoritative upstream ModelScope / PaddleOCR release URLs)
    model_urls = {
        "PP-OCRv6_det_medium.onnx": "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv6/det/PP-OCRv6_det_medium.onnx",
        "PP-OCRv6_rec_small.onnx": "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv6/rec/PP-OCRv6_rec_small.onnx",
        "ch_ppocr_mobile_v2.0_cls_mobile.onnx": "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv2/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    }
    print("Verifying and staging authoritative ONNX models...")
    for m in frozen_inv.get("onnx_models_inventory", []):
        m_fn = m["filename"]
        m_sha = m["sha256"]
        m_dest = downloads_dir / m_sha / m_fn
        # Check if already staged in downloads_dir or local private_samples
        if not m_dest.is_file():
            # Check local private_samples
            local_candidate = REPO_ROOT / "private_samples" / "phase0b" / "rapid_models" / m_fn
            if local_candidate.is_file() and hash_file(local_candidate) == m_sha:
                m_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_candidate, m_dest)
            elif m_fn in model_urls:
                download_and_verify(model_urls[m_fn], m_dest, m_sha)
            else:
                raise FileNotFoundError(f"Authoritative model {m_fn} with SHA {m_sha} not found and no URL defined")

        actual_sha = hash_file(m_dest)
        if actual_sha != m_sha:
            raise ValueError(f"Model hash mismatch for {m_fn}: expected {m_sha}, got {actual_sha}")
        downloaded_artifacts[m_fn] = m_dest
        print(f"  [OK] Model verified: {m_fn} (SHA-256: {m_sha[:12]}...)")

    return downloaded_artifacts


def unpack_sdist_pure_python(
    sdist_path: Path,
    target_lib_dir: Path,
    extraction_map: dict[str, dict[str, str]],
    source_filename: str,
    source_sha: str,
) -> None:
    """Extract pure-Python packages from an sdist tar.gz archive into lib directory and record extraction map."""
    import tarfile

    with tarfile.open(sdist_path, "r:gz") as tar:
        for member in tar.getmembers():
            # For antlr4-python3-runtime: files are under antlr4-python3-runtime-4.9.3/src/antlr4/...
            if "/src/antlr4" in member.name:
                # Strip prefix up to /src/
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
                        extraction_map[app_root_rel] = {
                            "source_artifact": source_filename,
                            "sha256": source_sha,
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
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    cs_file.unlink(missing_ok=True)

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
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, check=True)


def build_real_app_root(
    app_root: Path,
    downloaded_artifacts: dict[str, Path],
    frozen_inv: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the complete real <app_root> tree from verified artifacts with assembly-time provenance."""
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

    extraction_provenance_map: dict[str, dict[str, str]] = {}

    # 1. Extract CPython Embeddable
    cp_fn = frozen_inv["cpython_embeddable_runtime"]["archive_filename"]
    cp_path = downloaded_artifacts[cp_fn]
    print(f"Extracting CPython embeddable runtime to {python_dir}...")
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

    # 2. Extract vendored wheels and sdist with assembly-time extraction map
    print(f"Unpacking vendored dependencies into {lib_dir}...")
    for fn, art_path in downloaded_artifacts.items():
        if fn == cp_fn or fn.endswith(".onnx"):
            continue
        art_sha = wheel_sha_lookup.get(fn, "")
        if fn.endswith(".whl"):
            with zipfile.ZipFile(art_path, "r") as zf:
                for zip_info in zf.infolist():
                    if not zip_info.is_dir():
                        zf.extract(zip_info, lib_dir)
                        norm_rel = zip_info.filename.replace("\\", "/")
                        app_rel = f"lib/{norm_rel}"
                        extraction_provenance_map[app_rel] = {
                            "source_artifact": fn,
                            "sha256": art_sha,
                            "license": "Third-Party-Declared",
                            "verification_status": "verified",
                            "role": "vendored_python_dependency",
                        }
        elif fn.endswith(".tar.gz"):
            unpack_sdist_pure_python(art_path, lib_dir, extraction_provenance_map, fn, art_sha)

    # Link / copy PySide6 Qt plugins
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
                extraction_provenance_map[qt_rel] = {
                    "source_artifact": pyside_whl_fn,
                    "sha256": pyside_whl_sha,
                    "license": "LGPL-3.0-only",
                    "verification_status": "verified",
                    "role": "qt_runtime_plugin",
                }

    # 3. First-party application source
    src_origin = REPO_ROOT / "src" / "glyphcue"
    shutil.copytree(src_origin, app_src_dir)

    # 4. Database SQL Migrations
    src_mig_origin = src_origin / "persistence" / "migrations_sql"
    for sql_f in src_mig_origin.glob("*.sql"):
        shutil.copy2(sql_f, migrations_dir / sql_f.name)

    # 5. Authoritative ONNX Models
    for m in frozen_inv["onnx_models_inventory"]:
        m_name = m["filename"]
        m_path = downloaded_artifacts.get(m_name)
        if not m_path or not m_path.is_file():
            raise FileNotFoundError(f"Required frozen model missing: {m_name}")
        shutil.copy2(m_path, models_dir / m_name)

    # 6. Diagnostics
    shutil.copy2(REPO_ROOT / "tools" / "devqa_directml_verify.py", diagnostics_dir / "devqa_directml_verify.py")

    # 7. Compile first-party GlyphCue.exe launcher & record pre-sign SHA
    launcher_exe = app_root / "GlyphCue.exe"
    print("Compiling real first-party GlyphCue.exe launcher...")
    presign_sha = compile_launcher(launcher_exe)
    print(f"Pre-sign GlyphCue.exe SHA-256: {presign_sha}")

    # 8. Inner Signing: Sign GlyphCue.exe
    print("Applying Authenticode test signature to GlyphCue.exe...")
    sign_pe_file(launcher_exe, TEST_CERT_THUMBPRINT)
    postsign_sha = hash_file(launcher_exe)
    print(f"Post-sign GlyphCue.exe SHA-256: {postsign_sha}")

    # 9. Generate Payload Manifest & CycloneDX 1.6 SBOM (with fail-closed enforce_all_expected_present=True)
    manifest_path = legal_dir / "payload_manifest.json"
    manifest = generate_manifest(
        app_root,
        manifest_path,
        enforce_all_expected_present=True,
        extraction_provenance_map=extraction_provenance_map,
    )

    sbom_path = legal_dir / "sbom.json"
    generate_cyclonedx_sbom(manifest_path, sbom_path)

    # 10. Generate Signature Inventory for app_root
    sig_inv_path = legal_dir / "signature_inventory.json"
    sig_inv = evaluate_signature_gate(
        app_root,
        expected_thumbprint=TEST_CERT_THUMBPRINT,
        output_inventory=sig_inv_path,
        allow_mock=False,
    )

    return {
        "app_root": app_root,
        "presign_sha": presign_sha,
        "postsign_sha": postsign_sha,
        "manifest": manifest,
        "signature_inventory": sig_inv,
        "extraction_map": extraction_provenance_map,
    }


def test_runtime_sanity(app_root: Path) -> bool:
    """Execute local sanity check of assembled private embeddable runtime."""
    python_exe = app_root / "python" / "python.exe"
    sanity_script = """
import sys
import os
from pathlib import Path

print('[Sanity] Python executable:', sys.executable)
print('[Sanity] Python version:', sys.version)
print('[Sanity] sys.path entries:', sys.path)

app_base = Path(sys.executable).parent.parent

# 1. Application import
import glyphcue
print('[Sanity] OK: imported glyphcue from', glyphcue.__file__)

# 2. Database migrations check
mig_dir = app_base / 'resources' / 'migrations_sql'
mig_files = sorted(mig_dir.glob('*.sql'))
print(f'[Sanity] OK: found {len(mig_files)} SQL migration files in {mig_dir}')
assert len(mig_files) == 5, f'Expected 5 migration files, found {len(mig_files)}'

# 3. PySide6 & Qt Plugins verification
from PySide6 import QtCore
print('[Sanity] OK: imported PySide6 from', QtCore.__file__)

qwindows_dll = app_base / 'qt' / 'plugins' / 'platforms' / 'qwindows.dll'
if not qwindows_dll.is_file():
    qwindows_dll = app_base / 'qt' / 'plugins' / 'qwindows.dll'
print('[Sanity] QPA Platform plugin exists:', qwindows_dll.is_file(), 'at', qwindows_dll)

# 4. PyAV import
import av
print('[Sanity] OK: imported av (PyAV) version:', av.__version__)

# 5. ONNX Runtime & DirectML session initialization
import onnxruntime as ort
print('[Sanity] OK: imported onnxruntime version:', ort.__version__)
providers = ort.get_available_providers()
print('[Sanity] Available execution providers:', providers)

# 6. Authoritative Models Discovery & Loadability
models_dir = app_base / 'models'
det_medium = models_dir / 'PP-OCRv6_det_medium.onnx'
rec_small = models_dir / 'PP-OCRv6_rec_small.onnx'
cls_mobile = models_dir / 'ch_ppocr_mobile_v2.0_cls_mobile.onnx'

assert det_medium.is_file(), f'Missing det_medium model: {det_medium}'
assert rec_small.is_file(), f'Missing rec_small model: {rec_small}'
assert cls_mobile.is_file(), f'Missing cls_mobile model: {cls_mobile}'
print('[Sanity] OK: all 3 authoritative models discovered:', [m.name for m in (det_medium, rec_small, cls_mobile)])

# Test ONNX Runtime session creation with DmlExecutionProvider / CPUExecutionProvider fallback
test_providers = ['DmlExecutionProvider', 'CPUExecutionProvider'] if 'DmlExecutionProvider' in providers else ['CPUExecutionProvider']
session_options = ort.SessionOptions()
session_options.log_severity_level = 3  # Warning level
sess = ort.InferenceSession(str(cls_mobile), session_options, providers=test_providers)
print(f'[Sanity] OK: ONNX session created successfully for {cls_mobile.name} with provider {sess.get_providers()}')

# 7. RapidOCR Construction Test
from rapidocr import RapidOCR
engine = RapidOCR(params={
    'Det.model_path': str(det_medium),
    'Rec.model_path': str(rec_small),
    'Cls.model_path': str(cls_mobile),
})
print('[Sanity] OK: RapidOCR engine constructed successfully with authoritative models')

print('[Sanity] ALL CRITICAL RUNTIME SEAMS & MODELS INITIALIZED SUCCESSFULLY.')
"""
    cmd = [str(python_exe.resolve()), "-c", sanity_script]
    env = os.environ.copy()
    # Clear external Python environment variables to ensure total isolation
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)

    res = subprocess.run(cmd, cwd=str(app_root), env=env, capture_output=True, text=True)
    print("--- Local Runtime Sanity Check Output ---")
    print(res.stdout)
    if res.returncode != 0:
        print("Sanity check stderr:", res.stderr, file=sys.stderr)
        return False
    return True


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
    print(f"Compiling Inno Setup installer via {iscc_path}...")
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(res.stdout)

    installer_exe = output_dir / "GlyphCue-Setup.exe"
    if not installer_exe.is_file():
        raise FileNotFoundError(f"Expected installer not produced: {installer_exe}")

    # Sign the outer installer
    print(f"Applying outer Authenticode signature to {installer_exe.name}...")
    sign_pe_file(installer_exe, TEST_CERT_THUMBPRINT)

    return installer_exe


def run_phase_b(
    staging_dir: Path = REPO_ROOT / "build_artifacts" / "phase_b",
) -> dict[str, Any]:
    """Execute complete Phase B pipeline."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = REPO_ROOT / ".cache" / "packaging"

    frozen_inv = json.loads(FROZEN_BUILD_BASE_PATH.read_text(encoding="utf-8"))

    # 1. Populate staging cache
    downloaded = populate_staging_cache(cache_dir, frozen_inv)

    # 2. Assemble app_root
    app_root = staging_dir / "app_root"
    assembly_res = build_real_app_root(app_root, downloaded, frozen_inv)

    # 3. Local sanity check
    sanity_pass = test_runtime_sanity(app_root)
    if not sanity_pass:
        raise RuntimeError("Local runtime sanity check FAILED on assembled <app_root>")

    # 4. Compile Inno Setup installer
    iss_file = REPO_ROOT / "tools" / "packaging" / "glyphcue_installer.iss"
    installer_dir = staging_dir / "installer"
    installer_exe = compile_inno_installer(iss_file, app_root, installer_dir)

    installer_size = installer_exe.stat().st_size
    installer_sha = hash_file(installer_exe)

    # 5. Evaluate Phase B complete signature status
    # Outer installer + inner GlyphCue.exe verified; unins000.exe lifecycle deferred to Phase D
    outer_sig = check_pe_signature(installer_exe, expected_thumbprint=TEST_CERT_THUMBPRINT)
    inner_sig = check_pe_signature(app_root / "GlyphCue.exe", expected_thumbprint=TEST_CERT_THUMBPRINT)

    if not (outer_sig["verified_first_party"] and inner_sig["verified_first_party"]):
        raise RuntimeError(f"First-party signature verification failed: inner={inner_sig}, outer={outer_sig}")

    report = {
        "phase": "Phase B — Primary Runtime Assembly & First Installer Build",
        "app_root_dir": str(app_root),
        "app_root_files_count": assembly_res["manifest"]["total_files_count"],
        "app_root_total_bytes": assembly_res["manifest"]["total_payload_bytes"],
        "launcher_presign_sha256": assembly_res["presign_sha"],
        "launcher_postsign_sha256": assembly_res["postsign_sha"],
        "manifest_gate_results": assembly_res["manifest"]["gate_results"],
        "signature_gate_status": "PASS",
        "signatures_verified": {
            "GlyphCue.exe": inner_sig,
            "GlyphCue-Setup.exe": outer_sig,
            "unins000.exe": "DEFERRED_PHASE_D_LIFECYCLE",
        },
        "runtime_sanity_check": "PASS" if sanity_pass else "FAIL",
        "installer_path": str(installer_exe),
        "installer_size_bytes": installer_size,
        "installer_sha256": installer_sha,
        "test_cert_thumbprint": TEST_CERT_THUMBPRINT,
    }

    report_file = staging_dir / "phase_b_report.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n=== PHASE B EXECUTION REPORT ===")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute Phase B Packaging Experiment")
    parser.add_argument("--staging-dir", type=Path, default=REPO_ROOT / "build_artifacts" / "phase_b")
    args = parser.parse_args()

    rep = run_phase_b(args.staging_dir)

