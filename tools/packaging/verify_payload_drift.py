"""Payload Drift Verifier for GlyphCue Reproducible Packaging Reconstructions.

Compares two isolated reconstruction output trees (Reconstruction 1 vs Reconstruction 2)
per Wayfinder Issue #21 and #26 charter:
- Unsigned / pre-sign payload files: byte-for-byte SHA-256 equality.
- Signed PE files: verified pre-sign SHA equivalence and valid normalized Authenticode signatures.
- Inno Setup outer envelope: normalized signature & compiler timestamp handling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from tools.packaging.verify_signatures import check_pe_signature

SIGNED_PE_FILENAMES = {"GlyphCue.exe", "unins000.exe", "GlyphCue-Setup.exe"}


def hash_file(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def compare_reconstructions(
    dir1: Path,
    dir2: Path,
    pre_sign_hashes_1: dict[str, str] | None = None,
    pre_sign_hashes_2: dict[str, str] | None = None,
    expected_thumbprint: str | None = None,
    allow_mock: bool = False,
) -> dict[str, Any]:
    """Compare two installed app_root trees and return a drift report.

    For signed PEs in non-mock mode:
    - pre-sign hashes from both reconstructions must be provided and must match identically.
    - both post-sign PEs must carry valid test-certificate signatures matching the approved test root.
    """
    if not dir1.is_dir() or not dir2.is_dir():
        raise ValueError(f"Both reconstruction directories must exist: {dir1}, {dir2}")

    files1 = {p.relative_to(dir1).as_posix(): p for p in dir1.rglob("*") if p.is_file()}
    files2 = {p.relative_to(dir2).as_posix(): p for p in dir2.rglob("*") if p.is_file()}

    all_keys = sorted(set(files1.keys()) | set(files2.keys()))

    missing_in_2 = [k for k in all_keys if k not in files2]
    missing_in_1 = [k for k in all_keys if k not in files1]

    unsigned_mismatches = []
    signed_pe_entries = []
    signed_pe_failures = []
    matched_files = []

    for k in all_keys:
        if k in files1 and k in files2:
            s1, h1 = hash_file(files1[k])
            s2, h2 = hash_file(files2[k])
            filename = Path(k).name

            if filename in SIGNED_PE_FILENAMES:
                if allow_mock:
                    # In scaffold/mock test mode, record semantic equivalence
                    pe_status = "PASS"
                    pre1_sha = "MOCK_PRE_SIGN_SHA"
                    pre2_sha = "MOCK_PRE_SIGN_SHA"
                    sig1_info = {"status": "MOCK"}
                    sig2_info = {"status": "MOCK"}
                else:
                    # Real non-mock reconstruction verification:
                    # 1. Check pre-sign hash evidence
                    pre1_sha = pre_sign_hashes_1.get(k) if pre_sign_hashes_1 else None
                    pre2_sha = pre_sign_hashes_2.get(k) if pre_sign_hashes_2 else None

                    if not pre1_sha or not pre2_sha:
                        pe_status = "FAIL"
                        signed_pe_failures.append({
                            "path": k,
                            "reason": "MISSING_PRE_SIGN_EVIDENCE",
                            "pre_sign_1": pre1_sha,
                            "pre_sign_2": pre2_sha,
                        })
                    elif pre1_sha != pre2_sha:
                        pe_status = "FAIL"
                        signed_pe_failures.append({
                            "path": k,
                            "reason": "PRE_SIGN_HASH_MISMATCH",
                            "pre_sign_1": pre1_sha,
                            "pre_sign_2": pre2_sha,
                        })
                    else:
                        # 2. Check Authenticode signatures
                        sig1_info = check_pe_signature(files1[k], expected_thumbprint=expected_thumbprint)
                        sig2_info = check_pe_signature(files2[k], expected_thumbprint=expected_thumbprint)

                        if not sig1_info.get("verified_first_party") or not sig2_info.get("verified_first_party"):
                            pe_status = "FAIL"
                            signed_pe_failures.append({
                                "path": k,
                                "reason": "UNVERIFIED_SIGNATURE",
                                "sig1": sig1_info,
                                "sig2": sig2_info,
                            })
                        else:
                            pe_status = "PASS"

                signed_pe_entries.append({
                    "path": k,
                    "reconstruction_1_post_sign_sha256": h1,
                    "reconstruction_2_post_sign_sha256": h2,
                    "pre_sign_sha256_1": pre1_sha,
                    "pre_sign_sha256_2": pre2_sha,
                    "comparison_mode": "normalized_authenticode_semantic_equivalence",
                    "status": pe_status,
                })
            else:
                # Unsigned file: require strict byte-for-byte SHA equality
                if h1 == h2 and s1 == s2:
                    matched_files.append({"path": k, "sha256": h1, "size": s1})
                else:
                    unsigned_mismatches.append({
                        "path": k,
                        "recon1_size": s1,
                        "recon1_sha256": h1,
                        "recon2_size": s2,
                        "recon2_sha256": h2,
                    })

    is_reproducible = (
        len(missing_in_1) == 0
        and len(missing_in_2) == 0
        and len(unsigned_mismatches) == 0
        and len(signed_pe_failures) == 0
    )

    report = {
        "reconstruction_1_dir": str(dir1),
        "reconstruction_2_dir": str(dir2),
        "total_files_compared": len(all_keys),
        "exact_matching_unsigned_files_count": len(matched_files),
        "signed_pe_files_count": len(signed_pe_entries),
        "signed_pe_failures": signed_pe_failures,
        "missing_in_reconstruction_2": missing_in_2,
        "missing_in_reconstruction_1": missing_in_1,
        "unsigned_payload_mismatches": unsigned_mismatches,
        "signed_pe_comparisons": signed_pe_entries,
        "payload_drift_status": "PASS" if is_reproducible else "FAIL",
    }

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify payload drift between two reconstructions")
    parser.add_argument("dir1", type=Path, help="Reconstruction 1 directory")
    parser.add_argument("dir2", type=Path, help="Reconstruction 2 directory")
    parser.add_argument("--presign-1", type=Path, default=None, help="JSON file with recon 1 pre-sign hashes")
    parser.add_argument("--presign-2", type=Path, default=None, help="JSON file with recon 2 pre-sign hashes")
    parser.add_argument("--expected-thumbprint", type=str, default=None, help="Approved test cert thumbprint")
    parser.add_argument("--allow-mock", action="store_true", help="Allow mock PE comparison for scaffold self-test")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output JSON drift report path")
    args = parser.parse_args()

    p1 = json.loads(args.presign_1.read_text(encoding="utf-8")) if args.presign_1 and args.presign_1.is_file() else None
    p2 = json.loads(args.presign_2.read_text(encoding="utf-8")) if args.presign_2 and args.presign_2.is_file() else None

    res = compare_reconstructions(
        args.dir1,
        args.dir2,
        pre_sign_hashes_1=p1,
        pre_sign_hashes_2=p2,
        expected_thumbprint=args.expected_thumbprint,
        allow_mock=args.allow_mock,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"Drift report written to: {args.output}")

    print(f"Drift Status: {res['payload_drift_status']}")
    print(f"Matching unsigned files: {res['exact_matching_unsigned_files_count']}")
    print(f"Signed PE files compared: {res['signed_pe_files_count']}")
    if res["payload_drift_status"] != "PASS":
        print(f"Unsigned mismatches: {len(res['unsigned_payload_mismatches'])}")
        print(f"Signed PE failures: {len(res['signed_pe_failures'])}")
        print(f"Missing in 2: {res['missing_in_reconstruction_2']}")
        print(f"Missing in 1: {res['missing_in_reconstruction_1']}")
        sys.exit(1)
    else:
        print("PASS: Zero unexplained payload drift detected.")
        sys.exit(0)
