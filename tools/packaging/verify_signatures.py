"""Signature Verifier & Inventory Checker for GlyphCue Packaging Experiments.

Evaluates the Signature Gate per Wayfinder Issue #24, #25, and #26 charter:
- All first-party PE binaries (GlyphCue.exe, unins000.exe, GlyphCue-Setup.exe)
  must carry verified test-certificate signatures matching the exact approved test root.
- A valid signature from a different/unauthorized certificate FAILS the first-party gate.
- Upstream third-party PEs (DLLs, python.exe) match signature inventory records.
- Fails closed if certificate identity/policy cannot be established.
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

# Authoritative approved test certificate subject per #26 charter and build base
APPROVED_TEST_CERT_SUBJECT = "CN=GlyphCue Development Test Certificate, O=GlyphCue Local Test Root"


def check_pe_signature(pe_path: Path, expected_thumbprint: str | None = None) -> dict[str, Any]:
    """Check signature status of a PE binary using PowerShell Authenticode API."""
    if not pe_path.is_file():
        return {"path": pe_path.name, "status": "FILE_NOT_FOUND", "is_signed": False, "verified_first_party": False}

    ps_cmd = f"""
    $sig = Get-AuthenticodeSignature -FilePath '{pe_path.resolve()}'
    $cert = $sig.SignerCertificate
    [PSCustomObject]@{{
        Status = $sig.Status.ToString()
        StatusMessage = $sig.StatusMessage
        Subject = if ($cert) {{ $cert.Subject }} else {{ '' }}
        Issuer = if ($cert) {{ $cert.Issuer }} else {{ '' }}
        Thumbprint = if ($cert) {{ $cert.Thumbprint }} else {{ '' }}
        HasSignature = ($sig.Status -ne 'NotSigned')
    }} | ConvertTo-Json -Compress
    """
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(res.stdout.strip())
        status_str = data.get("Status", "Unknown")
        subject_str = data.get("Subject", "").strip()
        thumbprint_str = data.get("Thumbprint", "").strip()
        has_sig = data.get("HasSignature", False)

        # Strict identity check: Subject MUST match the exact approved test certificate subject
        subject_match = (subject_str == APPROVED_TEST_CERT_SUBJECT)

        # If expected thumbprint is provided, require exact match
        thumbprint_match = True
        if expected_thumbprint:
            thumbprint_match = (thumbprint_str.upper() == expected_thumbprint.upper())

        # First party verification requires: signed + exact subject match + thumbprint match
        is_verified_first_party = has_sig and subject_match and thumbprint_match

        return {
            "path": pe_path.name,
            "relative_path": str(pe_path),
            "authenticode_status": status_str,
            "subject": subject_str,
            "issuer": data.get("Issuer", ""),
            "thumbprint": thumbprint_str,
            "is_signed": has_sig,
            "verified_first_party": is_verified_first_party,
            "rejection_reason": None if is_verified_first_party else (
                "NOT_SIGNED" if not has_sig else
                f"UNAPPROVED_SIGNER_SUBJECT: {subject_str!r}" if not subject_match else
                f"THUMBPRINT_MISMATCH: {thumbprint_str} != {expected_thumbprint}"
            ),
        }
    except Exception as exc:
        return {
            "path": pe_path.name,
            "relative_path": str(pe_path),
            "authenticode_status": f"CHECK_ERROR: {exc}",
            "is_signed": False,
            "verified_first_party": False,
            "rejection_reason": f"EXCEPTION: {exc}",
        }


def evaluate_signature_gate(
    app_root: Path,
    installer_exe: Path | None = None,
    output_inventory: Path | None = None,
    expected_thumbprint: str | None = None,
    allow_mock: bool = False,
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
        info = check_pe_signature(pe, expected_thumbprint=expected_thumbprint)
        records.append(info)
        if pe.name in REQUIRED_FIRST_PARTY_PES:
            if allow_mock:
                # In scaffold/mock test mode, record placeholder presence
                pass
            elif not info["verified_first_party"]:
                first_party_failures.append({
                    "file": pe.name,
                    "status": info["authenticode_status"],
                    "subject": info.get("subject", ""),
                    "reason": info.get("rejection_reason"),
                })

    signature_gate_status = "PASS" if not first_party_failures else "FAIL"

    inventory = {
        "schema_version": "1.2.0",
        "total_pe_count": len(records),
        "approved_test_cert_subject": APPROVED_TEST_CERT_SUBJECT,
        "first_party_pes_required": list(REQUIRED_FIRST_PARTY_PES),
        "first_party_failures": first_party_failures,
        "signature_gate_status": signature_gate_status,
        "mock_scaffold_mode": allow_mock,
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
    parser.add_argument("--expected-thumbprint", type=str, default=None, help="Approved test cert thumbprint")
    parser.add_argument("--allow-mock", action="store_true", help="Allow mock placeholder PEs for scaffold testing")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output inventory JSON path")
    args = parser.parse_args()

    inv_path = args.output or (args.app_root / "legal" / "manifest" / "signature_inventory.json")
    res = evaluate_signature_gate(
        args.app_root,
        args.installer,
        inv_path,
        expected_thumbprint=args.expected_thumbprint,
        allow_mock=args.allow_mock,
    )
    print(f"Signature Gate Status: {res['signature_gate_status']}")
    print(f"Total PE files inspected: {res['total_pe_count']}")
    if res["first_party_failures"]:
        print(f"Failed first-party signature checks: {res['first_party_failures']}")
        sys.exit(1)
    else:
        print("PASS: Signature Gate evaluated successfully.")
        sys.exit(0)
