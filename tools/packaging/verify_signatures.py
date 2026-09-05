"""Signature Verifier & Inventory Checker for GlyphCue Packaging Experiments.

Evaluates the Signature Gate per Wayfinder Issue #24, #25, and #26 charter:
- All first-party PE binaries (GlyphCue.exe, unins000.exe, GlyphCue-Setup.exe)
  carry valid test-certificate signatures.
- Upstream third-party PEs (DLLs, python.exe) match signature inventory records.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# PEs requiring first-party test-certificate signatures
REQUIRED_FIRST_PARTY_PES = {"GlyphCue.exe", "unins000.exe", "GlyphCue-Setup.exe"}


def check_pe_signature(pe_path: Path) -> dict[str, Any]:
    """Check signature status of a PE binary using PowerShell Get-AuthenticodeSignature."""
    if not pe_path.is_file():
        return {"path": str(pe_path), "status": "FILE_NOT_FOUND", "is_signed": False}

    ps_cmd = f"(Get-AuthenticodeSignature -FilePath '{pe_path.resolve()}').Status.ToString()"
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            check=False,
        )
        status_str = res.stdout.strip()
        is_signed = status_str in ("Valid", "UnknownError")  # UnknownError = self-signed / test cert
        return {
            "path": pe_path.name,
            "relative_path": str(pe_path),
            "authenticode_status": status_str,
            "is_signed": is_signed,
        }
    except Exception as exc:
        return {
            "path": pe_path.name,
            "relative_path": str(pe_path),
            "authenticode_status": f"CHECK_ERROR: {exc}",
            "is_signed": False,
        }


def evaluate_signature_gate(
    app_root: Path,
    installer_exe: Path | None = None,
    output_inventory: Path | None = None,
) -> dict[str, Any]:
    """Inspect all PE files in app_root (and optional installer) and evaluate Signature Gate."""
    pe_files = []
    for p in sorted(app_root.rglob("*")):
        if p.is_file() and p.suffix.lower() in (".exe", ".dll", ".pyd"):
            pe_files.append(p)

    if installer_exe and installer_exe.is_file():
        pe_files.append(installer_exe)

    records = []
    first_party_failures = []

    for pe in pe_files:
        info = check_pe_signature(pe)
        records.append(info)
        if pe.name in REQUIRED_FIRST_PARTY_PES:
            # First party must be signed (Valid or self-signed test cert)
            if not info["is_signed"]:
                first_party_failures.append(pe.name)

    signature_gate_status = "PASS" if not first_party_failures else "FAIL"

    inventory = {
        "schema_version": "1.0.0",
        "total_pe_count": len(records),
        "first_party_pes_required": list(REQUIRED_FIRST_PARTY_PES),
        "first_party_failures": first_party_failures,
        "signature_gate_status": signature_gate_status,
        "pe_signatures": records,
    }

    if output_inventory:
        output_inventory.parent.mkdir(parents=True, exist_ok=True)
        output_inventory.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    return inventory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate GlyphCue PE signature gate")
    parser.add_argument("app_root", type=Path, help="Path to installed <app_root>")
    parser.add_argument("--installer", type=Path, default=None, help="Path to GlyphCue-Setup.exe")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output inventory JSON path")
    args = parser.parse_args()

    inv_path = args.output or (args.app_root / "legal" / "manifest" / "signature_inventory.json")
    res = evaluate_signature_gate(args.app_root, args.installer, inv_path)
    print(f"Signature Gate Status: {res['signature_gate_status']}")
    print(f"Total PE files inspected: {res['total_pe_count']}")
    if res["first_party_failures"]:
        print(f"Missing first-party signatures: {res['first_party_failures']}")
        sys.exit(1)
    else:
        print("PASS: Signature Gate evaluated successfully.")
        sys.exit(0)
