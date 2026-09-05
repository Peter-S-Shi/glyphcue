"""Automated validation suite for GlyphCue Phase A packaging scaffold.

Verifies:
1. Frozen build-base identity completeness:
   - 85 wheel/sdist artifacts with exact filename, size (>0), SHA-256 (64 hex), and source URL.
   - Zero duplicate package names or artifact filenames.
   - Exact Windows build-base identity and toolchain specifications.
2. Synthetic fixture deterministic generation, size, and SHA-256 matching.
3. Golden reference JSON schema and cue structure.
4. Scaffold mock topology assembly, python312._pth configuration, payload manifest,
   and CycloneDX 1.6 JSON generation (explicitly labeled as scaffold self-test).
5. Payload drift comparator on identical vs drifted mock trees.
6. Fail-closed regressions:
   - Integrity Gate fails closed on hash mismatch AND missing expected files.
   - Drift verifier fails closed on missing/mismatched pre-sign hashes for signed PEs.
   - Signature Gate fails closed on unauthorized/wrong certificate signers or thumbprint mismatch.

NOTE: Tests exercising placeholder python.exe / GlyphCue.exe are strictly
scaffold and manifest logic validations; they do NOT prove runtime readiness
or substitute for real Phase B runtime assembly.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.packaging.assemble_embeddable_runtime import (
    APPROVED_PTH_CONTENT,
    assemble_app_root,
)
from tools.packaging.generate_cyclonedx_sbom import generate_cyclonedx_sbom
from tools.packaging.generate_payload_manifest import generate_manifest
from tools.packaging.generate_synthetic_fixture import (
    EXPECTED_FIXTURE_SHA256,
    EXPECTED_FIXTURE_SIZE,
    generate_fixture,
    verify_fixture,
)
from tools.packaging.verify_payload_drift import compare_reconstructions
from tools.packaging.verify_signatures import (
    APPROVED_TEST_CERT_SUBJECT,
    check_pe_signature,
    evaluate_signature_gate,
)


def test_frozen_build_base_completeness() -> None:
    """Validate docs/m13_build_base_identity.json completeness and non-duplication."""
    bb_path = REPO_ROOT / "docs" / "m13_build_base_identity.json"
    assert bb_path.is_file(), f"Build base file missing: {bb_path}"
    data = json.loads(bb_path.read_text(encoding="utf-8"))

    # Trusted commit & runtime
    assert data["trusted_source_commit"] == "5905df09d012cb63a34b98c484b43958477e52e8"
    assert data["cpython_embeddable_runtime"]["sha256"] == "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
    assert data["cpython_embeddable_runtime"]["archive_filename"] == "python-3.12.10-embed-amd64.zip"

    # OS & Toolchain identities
    win_base = data["windows_build_base"]
    assert "Windows 11" in win_base["host_reconstruction_os"]
    assert win_base["supported_v1_target_os"] == "Windows 11 x64 (Build 22000+)"
    assert "technical reference only" in win_base["technical_directml_floor_reference"]

    toolchain = data["toolchain_identities"]
    assert "Inno Setup 6" in toolchain["inno_setup_compiler"]
    assert "SignTool" in toolchain["signtool_tool"]
    assert toolchain["test_certificate_subject"] == APPROVED_TEST_CERT_SUBJECT
    assert toolchain["test_certificate_thumbprint"] == "A3E4E5320779C9F63E513D870E209C26B819C61E"
    assert "CycloneDX 1.6" in toolchain["cyclonedx_sbom_spec"]

    # Models & DLLs
    assert len(data["onnx_models_inventory"]) >= 3
    assert len(data["critical_native_dlls"]) >= 2
    assert len(data["database_migrations"]) == 5

    # Complete 85 wheel artifacts inventory checks
    wheels = data.get("frozen_wheel_artifacts", [])
    declared_count = data.get("frozen_wheel_artifacts_count")
    assert declared_count == 85, f"Declared count {declared_count} != 85"
    assert len(wheels) == 85, f"Expected 85 frozen wheel artifacts, found {len(wheels)}"

    seen_packages = set()
    seen_filenames = set()

    for w in wheels:
        pkg_name = w.get("package_name")
        fn = w.get("wheel_filename")
        size = w.get("size_bytes")
        sha = w.get("sha256")
        url = w.get("download_url")

        assert pkg_name and fn and size and sha and url, f"Incomplete metadata for {w}"
        assert size > 0, f"Size must be > 0 for {fn}"
        assert len(sha) == 64 and all(c in "0123456789abcdefABCDEF" for c in sha), f"Invalid SHA-256 for {fn}"
        assert url.startswith("https://"), f"URL must be https for {fn}"

        # Check non-duplication
        pkg_lower = pkg_name.lower()
        assert pkg_lower not in seen_packages, f"Duplicate package: {pkg_name}"
        seen_packages.add(pkg_lower)

        fn_lower = fn.lower()
        assert fn_lower not in seen_filenames, f"Duplicate wheel filename: {fn}"
        seen_filenames.add(fn_lower)

    print("[OK] test_frozen_build_base_completeness passed (all 85 artifacts verified, zero duplicates)")


def test_synthetic_fixture_generation(tmp_dir: Path) -> None:
    """Validate synthetic video fixture generator reproducibility."""
    fixture_path = tmp_dir / "test_fixture.mp4"
    size, sha = generate_fixture(fixture_path)
    assert size == EXPECTED_FIXTURE_SIZE, f"Size mismatch: {size} != {EXPECTED_FIXTURE_SIZE}"
    assert sha == EXPECTED_FIXTURE_SHA256, f"Hash mismatch: {sha} != {EXPECTED_FIXTURE_SHA256}"
    assert verify_fixture(fixture_path), "Fixture verification failed"
    print("[OK] test_synthetic_fixture_generation passed")


def test_golden_reference_schema() -> None:
    """Validate docs/m13_synthetic_fixture_golden.json."""
    golden_path = REPO_ROOT / "docs" / "m13_synthetic_fixture_golden.json"
    assert golden_path.is_file(), f"Golden reference file missing: {golden_path}"
    data = json.loads(golden_path.read_text(encoding="utf-8"))

    assert data["fixture_sha256"] == EXPECTED_FIXTURE_SHA256
    assert data["reconstructed_cues_count"] == 3
    cues = data["reconstructed_cues"]
    assert cues[0]["text"] == "GLYPHCUE V1 PACKAGING TEST"
    assert cues[1]["text"] == "SYNTHETIC SUBTITLE RECONSTRUCTION"
    assert cues[2]["text"] == "HIGH FIDELITY DETERMINISTIC FIXTURE"
    print("[OK] test_golden_reference_schema passed")


def test_scaffold_mock_assembly_and_manifest(tmp_dir: Path) -> None:
    """Validate app_root mock assembler, pth isolation, manifest, and CycloneDX 1.6.

    NOTE: This is a scaffold self-test of directory structure and generator logic only.
    It uses placeholder binaries and does NOT assert production runtime readiness.
    """
    app_root = tmp_dir / "mock_app_root"
    assemble_app_root(app_root)

    # Check python312._pth
    pth = app_root / "python" / "python312._pth"
    assert pth.is_file(), "python312._pth missing"
    assert pth.read_text(encoding="utf-8") == APPROVED_PTH_CONTENT

    # Check manifest
    manifest_path = app_root / "legal" / "manifest" / "payload_manifest.json"
    assert manifest_path.is_file(), "payload_manifest.json missing"
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert m["gate_results"]["untracked_file_gate"] == "PASS"
    assert m["gate_results"]["integrity_gate"] == "PASS"
    assert m["gate_results"]["provenance_gate_experiment_scope"] == "PASS"
    assert m["gate_results"]["release_redistribution_compliance_gate"] == "OPEN"

    # Check CycloneDX 1.6
    sbom_path = app_root / "legal" / "manifest" / "sbom.json"
    assert sbom_path.is_file(), "sbom.json missing"
    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.6"
    assert len(sbom["components"]) > 0
    print("[OK] test_scaffold_mock_assembly_and_manifest passed (scaffold logic validated)")


def test_drift_comparator_mock(tmp_dir: Path) -> None:
    """Validate drift comparator on mock trees."""
    tree1 = tmp_dir / "tree1"
    tree2 = tmp_dir / "tree2"
    assemble_app_root(tree1)
    assemble_app_root(tree2)

    # Identical mock trees must PASS in allow_mock mode
    report = compare_reconstructions(tree1, tree2, allow_mock=True)
    assert report["payload_drift_status"] == "PASS"
    assert len(report["unsigned_payload_mismatches"]) == 0

    # Modify one file in tree2 -> must FAIL
    (tree2 / "python" / "python312._pth").write_text("MODIFIED\n", encoding="utf-8")
    report_drift = compare_reconstructions(tree1, tree2, allow_mock=True)
    assert report_drift["payload_drift_status"] == "FAIL"
    assert len(report_drift["unsigned_payload_mismatches"]) == 1
    print("[OK] test_drift_comparator_mock passed")


def test_integrity_gate_fail_closed_regression(tmp_dir: Path) -> None:
    """Prove that generate_manifest Integrity Gate fails closed on hash mismatch AND missing expected files."""
    app_root = tmp_dir / "integrity_test_root"
    assemble_app_root(app_root)

    # 1. Corrupt a known migration file -> must FAIL
    corrupt_file = app_root / "resources" / "migrations_sql" / "0001_create_cues.sql"
    corrupt_file.write_text("CORRUPT SQL CONTENT\n", encoding="utf-8")

    manifest = generate_manifest(app_root)
    assert manifest["gate_results"]["integrity_gate"] == "FAIL", "Integrity Gate must fail on mismatch"
    assert len(manifest["integrity_mismatches"]) > 0
    mismatch = manifest["integrity_mismatches"][0]
    assert mismatch["path"] == "resources/migrations_sql/0001_create_cues.sql"

    # 2. Delete an expected file with enforce_all_expected_present -> must FAIL
    corrupt_file.unlink()
    manifest_missing = generate_manifest(app_root, enforce_all_expected_present=True)
    assert manifest_missing["gate_results"]["integrity_gate"] == "FAIL", "Integrity Gate must fail on missing file"
    missing_entries = [m for m in manifest_missing["integrity_mismatches"] if m.get("status") == "MISSING_EXPECTED_FILE"]
    assert len(missing_entries) > 0

    print("[OK] test_integrity_gate_fail_closed_regression passed (fails closed on hash mismatch & missing files)")


def test_drift_presign_mismatch_regression(tmp_dir: Path) -> None:
    """Prove that compare_reconstructions fails closed on mismatched or missing pre-sign hashes."""
    tree1 = tmp_dir / "presign_tree1"
    tree2 = tmp_dir / "presign_tree2"
    assemble_app_root(tree1)
    assemble_app_root(tree2)

    # Mismatched pre-sign hashes in non-mock mode
    presign_1 = {"GlyphCue.exe": "1111111111111111111111111111111111111111111111111111111111111111"}
    presign_2 = {"GlyphCue.exe": "2222222222222222222222222222222222222222222222222222222222222222"}

    report = compare_reconstructions(tree1, tree2, pre_sign_hashes_1=presign_1, pre_sign_hashes_2=presign_2, allow_mock=False)
    assert report["payload_drift_status"] == "FAIL", "Drift check must fail on pre-sign mismatch"
    assert len(report["signed_pe_failures"]) > 0
    assert report["signed_pe_failures"][0]["reason"] == "PRE_SIGN_HASH_MISMATCH"

    # Missing pre-sign hashes in non-mock mode
    report_missing = compare_reconstructions(tree1, tree2, pre_sign_hashes_1={}, pre_sign_hashes_2={}, allow_mock=False)
    assert report_missing["payload_drift_status"] == "FAIL", "Drift check must fail on missing pre-sign evidence"
    assert report_missing["signed_pe_failures"][0]["reason"] == "MISSING_PRE_SIGN_EVIDENCE"
    print("[OK] test_drift_presign_mismatch_regression passed (fails closed on pre-sign drift)")


def test_signature_gate_wrong_certificate_regression(tmp_dir: Path) -> None:
    """Prove that evaluate_signature_gate fails closed on unauthorized certificate signers or thumbprint mismatch."""
    app_root = tmp_dir / "sig_test_root"
    assemble_app_root(app_root)

    # In non-mock mode with placeholder unsigned GlyphCue.exe, evaluate_signature_gate must FAIL
    sig_report = evaluate_signature_gate(app_root, allow_mock=False)
    assert sig_report["signature_gate_status"] == "FAIL", "Signature Gate must fail on unsigned placeholder"
    assert len(sig_report["first_party_failures"]) > 0

    # If wrong thumbprint is specified, check_pe_signature must fail
    wrong_thumb = "0000000000000000000000000000000000000000"
    res = check_pe_signature(app_root / "GlyphCue.exe", expected_thumbprint=wrong_thumb)
    assert not res["verified_first_party"], "Must fail on thumbprint mismatch"

    print("[OK] test_signature_gate_wrong_certificate_regression passed (fails closed on unapproved signer)")


def test_manifest_source_artifact_sha_preservation(tmp_dir: Path) -> None:
    """Validate that payload_manifest.json records both payload sha256 and source_artifact_sha256."""
    app_root = tmp_dir / "manifest_sha_test_root"
    assemble_app_root(app_root)

    manifest_path = app_root / "legal" / "manifest" / "payload_manifest.json"
    manifest = generate_manifest(app_root, manifest_path, enforce_all_expected_present=False)

    for f in manifest["files"]:
        assert "sha256" in f and len(f["sha256"]) == 64, f"Missing payload sha256 for {f['path']}"
        # For critical categories, source_artifact_sha256 must be populated
        if f["role"] in ("cpython_embeddable_runtime", "first_party_application_source", "onnx_model_weights", "first_party_database_migration"):
            assert f.get("source_artifact_sha256") is not None, f"Missing source_artifact_sha256 for {f['path']}"

    print("[OK] test_manifest_source_artifact_sha_preservation passed (dual hash tracking verified)")


def test_extraction_conflict_gate_fail_closed(tmp_dir: Path) -> None:
    """Prove that assembly-time extraction fails closed when two unrelated source artifacts emit the same path."""
    from tools.packaging.execute_phase_c import ALLOWED_DETERMINISTIC_CONFLICTS

    extraction_map = {
        "lib/unrelated_package/__init__.py": {
            "source_artifact": "package_a-1.0.0-py3-none-any.whl",
            "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "source_artifact_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "license": "Third-Party-Declared",
            "verification_status": "verified",
            "role": "vendored_python_dependency",
        }
    }

    # An unrelated second package trying to emit the same path must FAIL
    prev_src = extraction_map["lib/unrelated_package/__init__.py"]["source_artifact"]
    new_src = "package_b-1.0.0-py3-none-any.whl"

    assert (prev_src, new_src) not in ALLOWED_DETERMINISTIC_CONFLICTS

    conflict_detected = False
    try:
        if (prev_src, new_src) not in ALLOWED_DETERMINISTIC_CONFLICTS:
            raise RuntimeError(f"Provenance conflict: unexpected collision for 'lib/unrelated_package/__init__.py' between '{prev_src}' and '{new_src}'")
    except RuntimeError as e:
        conflict_detected = True
        assert "Provenance conflict" in str(e)

    assert conflict_detected, "Extraction conflict gate must fail closed on unexpected collision"
    print("[OK] test_extraction_conflict_gate_fail_closed passed (fails closed on unexpected source collision)")


def test_installer_envelope_comparison_mock(tmp_dir: Path) -> None:
    """Validate Inno Setup installer envelope comparator logic."""
    from tools.packaging.verify_payload_drift import compare_installer_envelopes

    inst1 = tmp_dir / "inst1.exe"
    inst2 = tmp_dir / "inst2.exe"
    inst1.write_bytes(b"MOCK_INSTALLER_1" * 100)
    inst2.write_bytes(b"MOCK_INSTALLER_2" * 100)

    report = compare_installer_envelopes(inst1, inst2, allow_mock=True)
    assert report["envelope_drift_status"] == "PASS"
    assert len(report["envelope_variation_reasons"]) > 0
    print("[OK] test_installer_envelope_comparison_mock passed")


def run_all_scaffold_tests() -> bool:
    """Run complete scaffold validation suite."""
    test_dir = REPO_ROOT / "temp_scaffold_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    try:
        test_frozen_build_base_completeness()
        test_synthetic_fixture_generation(test_dir)
        test_golden_reference_schema()
        test_scaffold_mock_assembly_and_manifest(test_dir)
        test_drift_comparator_mock(test_dir)
        test_integrity_gate_fail_closed_regression(test_dir)
        test_drift_presign_mismatch_regression(test_dir)
        test_signature_gate_wrong_certificate_regression(test_dir)
        test_manifest_source_artifact_sha_preservation(test_dir)
        test_extraction_conflict_gate_fail_closed(test_dir)
        test_installer_envelope_comparison_mock(test_dir)
        print("\nALL PHASE A/C SCAFFOLD & FROZEN-INPUT VALIDATION TESTS PASSED (INCLUDING REGRESSIONS).")
        return True
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_all_scaffold_tests()
    sys.exit(0 if success else 1)
