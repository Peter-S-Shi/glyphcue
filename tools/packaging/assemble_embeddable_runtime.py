"""Embeddable CPython Runtime Assembler for GlyphCue Release Packaging.

Assembles the complete <app_root> directory tree according to the approved
Wayfinder Issue #25 topology and #26 charter specifications.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.packaging.generate_cyclonedx_sbom import generate_cyclonedx_sbom
from tools.packaging.generate_payload_manifest import generate_manifest

# Approved python312._pth configuration lines per #25
APPROVED_PTH_CONTENT = """python312.zip
.
../app
../lib
"""


def extract_zip(zip_path: Path, target_dir: Path) -> None:
    """Extract a zip archive into target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)


def unpack_wheel_to_lib(wheel_path: Path, lib_dir: Path, qt_plugins_dir: Path) -> None:
    """Unpack a .whl file into lib_dir and relocate Qt plugins if present."""
    lib_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel_path, "r") as zf:
        zf.extractall(lib_dir)

    # If PySide6 was unpacked, check for plugins to link/move to qt/plugins
    pyside_plugins = lib_dir / "PySide6" / "plugins"
    if pyside_plugins.is_dir():
        qt_plugins_dir.mkdir(parents=True, exist_ok=True)
        for item in pyside_plugins.iterdir():
            target_plugin = qt_plugins_dir / item.name
            if not target_plugin.exists():
                if item.is_dir():
                    shutil.copytree(item, target_plugin)
                else:
                    shutil.copy2(item, target_plugin)


def assemble_app_root(
    output_dir: Path,
    cpython_zip: Path | None = None,
    wheels_dir: Path | None = None,
    src_dir: Path | None = None,
    models_dir: Path | None = None,
    sentinel_v1: bool = False,
) -> Path:
    """Assemble the <app_root> distribution directory."""
    app_root = output_dir.resolve()
    app_root.mkdir(parents=True, exist_ok=True)

    # Subdirectories per #25 topology
    python_dir = app_root / "python"
    app_src_dir = app_root / "app" / "glyphcue"
    lib_dir = app_root / "lib"
    qt_plugins_dir = app_root / "qt" / "plugins"
    models_target_dir = app_root / "models"
    migrations_target_dir = app_root / "resources" / "migrations_sql"
    legal_dir = app_root / "legal" / "manifest"
    diagnostics_dir = app_root / "diagnostics"

    for d in (
        python_dir,
        app_src_dir.parent,
        lib_dir,
        qt_plugins_dir,
        models_target_dir,
        migrations_target_dir,
        legal_dir,
        diagnostics_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)

    # 1. CPython Embeddable
    if cpython_zip and cpython_zip.is_file():
        extract_zip(cpython_zip, python_dir)
    else:
        # Create minimal placeholder structure if archive is not yet downloaded
        (python_dir / "python.exe").touch(exist_ok=True)
        (python_dir / "python312.dll").touch(exist_ok=True)
        (python_dir / "python312.zip").touch(exist_ok=True)

    # Configure python312._pth
    pth_file = python_dir / "python312._pth"
    pth_file.write_text(APPROVED_PTH_CONTENT, encoding="utf-8")

    # 2. Vendored Wheels
    if wheels_dir and wheels_dir.is_dir():
        for whl in sorted(wheels_dir.glob("*.whl")):
            unpack_wheel_to_lib(whl, lib_dir, qt_plugins_dir)

    # 3. First-party application source
    source_root = src_dir or (REPO_ROOT / "src" / "glyphcue")
    if source_root.is_dir():
        if app_src_dir.exists():
            shutil.rmtree(app_src_dir)
        shutil.copytree(source_root, app_src_dir)

    # 4. Database SQL Migrations
    src_migrations = source_root / "persistence" / "migrations_sql"
    if src_migrations.is_dir():
        for sql_file in src_migrations.glob("*.sql"):
            shutil.copy2(sql_file, migrations_target_dir / sql_file.name)

    # 5. ONNX Models
    models_source = models_dir or REPO_ROOT
    if models_source.is_dir():
        for model_file in models_source.glob("*.onnx"):
            shutil.copy2(model_file, models_target_dir / model_file.name)

    # 6. Diagnostics Probe
    probe_src = REPO_ROOT / "tools" / "devqa_directml_verify.py"
    if probe_src.is_file():
        shutil.copy2(probe_src, diagnostics_dir / probe_src.name)

    # 7. First-party launcher binary placeholder / stub
    launcher_exe = app_root / "GlyphCue.exe"
    if not launcher_exe.exists():
        # Create launcher placeholder binary
        launcher_exe.write_bytes(b"MZ\x90\x00" + b"\x00" * 512)

    # 8. Sentinel file for V-1 upgrade testing (proves stale-file removal)
    if sentinel_v1:
        sentinel_file = diagnostics_dir / "v1_sentinel.txt"
        sentinel_file.write_text("V-1-EXPERIMENTAL-PREDECESSOR-SENTINEL\n", encoding="utf-8")

    # 9. Generate Manifest & CycloneDX 1.6 SBOM
    manifest_path = legal_dir / "payload_manifest.json"
    generate_manifest(app_root, manifest_path)

    sbom_path = legal_dir / "sbom.json"
    generate_cyclonedx_sbom(manifest_path, sbom_path)

    return app_root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble GlyphCue embeddable runtime tree")
    parser.add_argument("output_dir", type=Path, help="Target <app_root> directory")
    parser.add_argument("--cpython-zip", type=Path, default=None, help="Path to python-3.12.10-embed-amd64.zip")
    parser.add_argument("--wheels-dir", type=Path, default=None, help="Directory with vendored wheels")
    parser.add_argument("--src-dir", type=Path, default=None, help="Path to src/glyphcue")
    parser.add_argument("--models-dir", type=Path, default=None, help="Path to directory containing ONNX models")
    parser.add_argument("--sentinel-v1", action="store_true", help="Add V-1 upgrade sentinel file")
    args = parser.parse_args()

    root = assemble_app_root(
        args.output_dir,
        args.cpython_zip,
        args.wheels_dir,
        args.src_dir,
        args.models_dir,
        args.sentinel_v1,
    )
    print(f"Assembled <app_root> at: {root}")
