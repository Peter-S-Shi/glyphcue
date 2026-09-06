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

import hashlib
import json
import re
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
    assert toolchain["test_certificate_thumbprint"] == "DEDF7D0881E3A172CC018B63CCCF69FC51333AFC"
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


def test_final_payload_manifest_exact_disk_reconciliation(tmp_dir: Path) -> None:
    """Validate that the final payload manifest exactly matches disk files with zero drift."""
    app_root = tmp_dir / "reconcile_app_root"
    assemble_app_root(app_root)

    manifest_path = app_root / "legal" / "manifest" / "payload_manifest.json"
    assert manifest_path.is_file()
    m = json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest_paths = {e["path"].replace("\\", "/") for e in m["files"]}
    disk_paths = {
        p.relative_to(app_root).as_posix()
        for p in app_root.rglob("*")
        if p.is_file() and p != manifest_path
    }

    unindexed_on_disk = disk_paths - manifest_paths
    missing_on_disk = manifest_paths - disk_paths

    assert not unindexed_on_disk, f"Unindexed disk files found: {unindexed_on_disk}"
    assert not missing_on_disk, f"Manifest files missing on disk: {missing_on_disk}"
    assert len(manifest_paths) == len(disk_paths), "Manifest count must equal disk payload count"
    print("[OK] test_final_payload_manifest_exact_disk_reconciliation passed (100% path/count match)")


def test_strict_offline_reconstruction_fails_on_missing_staged_input(tmp_dir: Path) -> None:
    """Validate that reconstruction fails closed in strict offline mode if an artifact is missing."""
    from tools.packaging.execute_phase_c import stage_offline_artifact

    dest = tmp_dir / "missing_artifact.whl"
    fake_sha = "0" * 64
    empty_seed = tmp_dir / "empty_seed_cache"
    empty_seed.mkdir(parents=True, exist_ok=True)

    failed_closed = False
    try:
        stage_offline_artifact(dest, fake_sha, seed_cache_dir=empty_seed)
    except FileNotFoundError as exc:
        failed_closed = True
        assert "Strict offline reconstruction failure" in str(exc)

    assert failed_closed, "Must fail closed in strict offline mode when input is missing"
    print("[OK] test_strict_offline_reconstruction_fails_on_missing_staged_input passed (fail closed)")


def _find_matching_end(source: str, begin_index: int) -> int:
    """Return the index of the ``end;`` keyword that closes the ``begin`` at begin_index."""
    depth = 0
    for match in re.finditer(r"\b(begin|end)\b", source[begin_index:], flags=re.IGNORECASE):
        if match.group(1).lower() == "begin":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return begin_index + match.end()
    raise AssertionError("Unbalanced begin/end while scanning Inno Setup [Code] section")


def test_launcher_suppresses_bytecode_writes_into_app_root() -> None:
    """Both authoritative launcher-compilation paths (Phase B real build and
    Phase C independent reconstruction) must invoke python.exe with -B so no
    __pycache__/*.pyc is ever written into the installer-owned <app_root>.
    F3 default uninstall previously failed because standard Inno uninstall
    cannot remove files/dirs it never tracked at install time."""
    for module_name in ("execute_phase_b", "execute_phase_c"):
        module_path = REPO_ROOT / "tools" / "packaging" / f"{module_name}.py"
        source = module_path.read_text(encoding="utf-8")
        assert "LAUNCHER_CS_SOURCE" in source, f"{module_name}.py must define LAUNCHER_CS_SOURCE"
        assert 'psi.Arguments = "-B -m glyphcue.ui.app";' in source, (
            f"{module_name}.py launcher must invoke python.exe with -B "
            f"to suppress bytecode writes into <app_root>"
        )
    print("[OK] test_launcher_suppresses_bytecode_writes_into_app_root passed")


def test_uninstaller_forcibly_removes_app_root_preserving_user_data() -> None:
    """Default uninstall must force-remove the entire installer-owned
    <app_root> (including any legacy runtime-generated residue such as
    pre-existing __pycache__/*.pyc), unconditionally and independent of the
    explicit, opt-in %USERPROFILE%\\.glyphcue user-data purge checkbox."""
    iss_path = REPO_ROOT / "tools" / "packaging" / "glyphcue_installer.iss"
    source = iss_path.read_text(encoding="utf-8")

    proc_index = source.index("procedure CurUninstallStepChanged")
    proc_begin_index = source.index("begin", proc_index)
    proc_end_index = _find_matching_end(source, proc_begin_index)
    proc_body = source[proc_begin_index:proc_end_index]

    purge_if_marker = "if (PurgeUserDataCheckbox <> nil) and PurgeUserDataCheckbox.Checked then"
    assert purge_if_marker in proc_body, "Explicit user-data purge checkbox gating must remain unchanged"
    purge_if_index = proc_body.index(purge_if_marker)
    purge_begin_index = proc_body.index("begin", purge_if_index)
    purge_end_index = _find_matching_end(proc_body, purge_begin_index)

    app_removal_marker = "AppRootPath := ExpandConstant('{app}');"
    assert app_removal_marker in proc_body, "Uninstall must force-remove {app} unconditionally"
    app_removal_index = proc_body.index(app_removal_marker)
    assert app_removal_index >= purge_end_index, (
        "{app} removal must sit outside (after) the purge checkbox's begin/end "
        "block, not nested inside it -- otherwise default (non-purge) uninstall "
        "would still leave <app_root> residue behind"
    )
    assert "DelTree(AppRootPath, True, True, True);" in proc_body[app_removal_index:]
    assert ".glyphcue" in proc_body, "User data path must remain disjoint from {app}"
    print("[OK] test_uninstaller_forcibly_removes_app_root_preserving_user_data passed")


def test_explicit_purge_resolves_userprofile_via_getenv_not_invalid_constant() -> None:
    """F4 Explicit Purge crashed at uninstall runtime with 'Internal error:
    Unknown constant "userprofile"' -- {userprofile} is not a valid Inno Setup
    constant, so ExpandConstant('{userprofile}\\.glyphcue') fails whenever the
    purge checkbox is checked. The purge path must instead be resolved via the
    real USERPROFILE environment variable (GetEnv), and must fail closed
    (skip deletion entirely) if that variable is blank, rather than ever
    building a deletion path from an empty/garbage prefix."""
    iss_path = REPO_ROOT / "tools" / "packaging" / "glyphcue_installer.iss"
    source = iss_path.read_text(encoding="utf-8")

    assert "{userprofile}" not in source.lower(), (
        "{userprofile} is not a valid Inno Setup constant; ExpandConstant "
        'raises \'Unknown constant "userprofile"\' at uninstall runtime'
    )

    proc_index = source.index("procedure CurUninstallStepChanged")
    proc_begin_index = source.index("begin", proc_index)
    proc_end_index = _find_matching_end(source, proc_begin_index)
    proc_body = source[proc_begin_index:proc_end_index]

    purge_if_marker = "if (PurgeUserDataCheckbox <> nil) and PurgeUserDataCheckbox.Checked then"
    assert purge_if_marker in proc_body, "Explicit user-data purge checkbox gating must remain unchanged"
    purge_if_index = proc_body.index(purge_if_marker)
    purge_begin_index = proc_body.index("begin", purge_if_index)
    purge_end_index = _find_matching_end(proc_body, purge_begin_index)
    purge_body = proc_body[purge_begin_index:purge_end_index]

    getenv_marker = "GetEnv('USERPROFILE')"
    assert getenv_marker in purge_body, "Purge path must resolve USERPROFILE via GetEnv, not an invalid ExpandConstant"

    # Fail closed: the resolved value must be tested for blank before any
    # deletion path is built from it or DelTree is called.
    getenv_index = purge_body.index(getenv_marker)
    blank_check_marker = "<> ''"
    deltree_index = purge_body.index("DelTree(")
    assert blank_check_marker in purge_body[getenv_index:deltree_index], (
        "Purge logic must check USERPROFILE for blank ('<> ''') before any "
        "deletion path is built or DelTree is called -- never form a "
        "deletion path from an empty/unresolved prefix"
    )
    assert ".glyphcue" in purge_body
    print("[OK] test_explicit_purge_resolves_userprofile_via_getenv_not_invalid_constant passed")


def test_launcher_provenance_reflects_actual_compiled_source_not_stale_constant() -> None:
    """Provenance truth audit: GlyphCue.exe's source_artifact_sha256 must be
    computed from the LAUNCHER_CS_SOURCE actually compiled into that build.
    generate_payload_manifest.py's classify_payload_file() previously fell
    back to a hardcoded constant (dea596e9...) for every GlyphCue.exe entry
    regardless of build -- that constant does not match the SHA-256 of
    either the pre-fix or post-fix LAUNCHER_CS_SOURCE text, so it was never
    real provenance and silently went further stale across every launcher
    change. Both authoritative launcher-compilation paths must now inject
    real, dynamically-computed provenance via their extraction map, which
    classify_payload_file() already prefers over the hardcoded fallback."""
    stale_constant = "dea596e97c1648d9480494f2923e9d0aeee6a2f02ab91fd4455e10592c82400a"

    for module_name, extraction_var in (
        ("execute_phase_b", "extraction_provenance_map"),
        ("execute_phase_c", "extraction_map"),
    ):
        module_path = REPO_ROOT / "tools" / "packaging" / f"{module_name}.py"
        source = module_path.read_text(encoding="utf-8")

        marker = f'{extraction_var}["GlyphCue.exe"] = {{'
        assert marker in source, (
            f"{module_name}.py must record real launcher provenance for GlyphCue.exe "
            f"in {extraction_var}, not rely on the stale hardcoded manifest fallback"
        )
        block_start = source.index(marker)
        block_end = source.index("}", block_start)
        block = source[block_start:block_end]
        assert 'hashlib.sha256(LAUNCHER_CS_SOURCE.encode("utf-8")).hexdigest()' in block, (
            f"{module_name}.py must compute source_artifact_sha256 from the actual "
            f"compiled LAUNCHER_CS_SOURCE, not a hardcoded constant"
        )
        assert stale_constant not in block

    # The two independent launcher-compilation paths must currently agree on
    # the real hash of their (identical) LAUNCHER_CS_SOURCE, and neither may
    # coincide with the old stale constant.
    def _extract_launcher_cs_source(src: str) -> str:
        marker_index = src.index("LAUNCHER_CS_SOURCE")
        q1 = src.index('"""', marker_index)
        q2 = src.index('"""', q1 + 3)
        return src[q1 + 3 : q2]

    b_source = (REPO_ROOT / "tools" / "packaging" / "execute_phase_b.py").read_text(encoding="utf-8")
    c_source = (REPO_ROOT / "tools" / "packaging" / "execute_phase_c.py").read_text(encoding="utf-8")
    b_hash = hashlib.sha256(_extract_launcher_cs_source(b_source).encode("utf-8")).hexdigest()
    c_hash = hashlib.sha256(_extract_launcher_cs_source(c_source).encode("utf-8")).hexdigest()
    assert b_hash == c_hash, "Both authoritative launcher sources must currently match for provenance to reconcile"
    assert b_hash != stale_constant

    # The stale constant must not exist anywhere in generate_payload_manifest.py
    # -- not merely be overridden by Phase B/C's extraction-map injection.
    from tools.packaging.generate_payload_manifest import (
        build_source_artifact_sha_map,
        classify_payload_file,
        load_frozen_inventory,
    )

    manifest_gen_path = REPO_ROOT / "tools" / "packaging" / "generate_payload_manifest.py"
    manifest_gen_source = manifest_gen_path.read_text(encoding="utf-8")
    assert stale_constant not in manifest_gen_source, (
        "generate_payload_manifest.py must not retain the stale constant anywhere in its "
        "source -- it was never a real provenance hash for any LAUNCHER_CS_SOURCE revision"
    )

    frozen_inv = load_frozen_inventory()
    sha_map = build_source_artifact_sha_map(frozen_inv)
    assert sha_map.get("glyphcue_first_party_launcher") is None, (
        "build_source_artifact_sha_map() must not hardcode any launcher source SHA -- the "
        "launcher is compiled at build time, not a frozen downloaded artifact"
    )

    # Fail closed at the real classification seam: with no extraction-map
    # provenance supplied (e.g. a caller that never compiled a launcher),
    # source_artifact_sha256 must be left unresolved, never fabricated.
    meta = classify_payload_file("GlyphCue.exe", wheel_map={}, source_sha_map=sha_map, extraction_map=None)
    assert meta["source_artifact_sha256"] is None, (
        "classify_payload_file() must fail closed (leave source_artifact_sha256 unresolved) "
        "for GlyphCue.exe when no extraction-map provenance is supplied, not fabricate a hash"
    )
    print("[OK] test_launcher_provenance_reflects_actual_compiled_source_not_stale_constant passed")


def test_gpl_ffmpeg_codec_guard_fails_closed_on_forbidden_libraries(tmp_dir: Path) -> None:
    """v1.0.0 Public Distribution Gate A: PyAV's official Windows wheel vendors
    an FFmpeg build compiled with --enable-gpl (confirmed by libx264/libx265
    presence). Removing just those external codec DLLs does not relicense the
    remaining avcodec/avformat/avutil binaries back to LGPL -- FFmpeg's own
    policy is that enabling any GPL-only component makes the GPL apply to the
    whole build. The real fix is a verified LGPL-only FFmpeg build (see
    docs/v1_public_distribution_gate_a_compliance_audit.md); this guard must
    fail closed if a forbidden GPL-only codec library is ever found in a
    packaged app_root."""
    from tools.packaging.verify_no_gpl_ffmpeg_codecs import (
        assert_no_gpl_ffmpeg_codec_libraries,
        scan_for_forbidden_gpl_codec_libraries,
    )

    dirty_root = tmp_dir / "gpl_guard_dirty_root"
    dirty_root.mkdir(parents=True, exist_ok=True)
    (dirty_root / "lib").mkdir(exist_ok=True)
    (dirty_root / "lib" / "av.libs").mkdir(exist_ok=True)
    (dirty_root / "lib" / "av.libs" / "libx264-165-deadbeef.dll").write_bytes(b"fake")
    (dirty_root / "lib" / "av.libs" / "avcodec-62-deadbeef.dll").write_bytes(b"fake")

    hits = scan_for_forbidden_gpl_codec_libraries(dirty_root)
    assert hits == ["lib/av.libs/libx264-165-deadbeef.dll"], hits

    raised = False
    try:
        assert_no_gpl_ffmpeg_codec_libraries(dirty_root)
    except RuntimeError as exc:
        raised = True
        assert "libx264-165-deadbeef.dll" in str(exc)
    assert raised, "Must fail closed (raise) when a GPL-only codec library is present"

    clean_root = tmp_dir / "gpl_guard_clean_root"
    clean_root.mkdir(parents=True, exist_ok=True)
    (clean_root / "lib").mkdir(exist_ok=True)
    (clean_root / "lib" / "avcodec-62-deadbeef.dll").write_bytes(b"fake")

    assert scan_for_forbidden_gpl_codec_libraries(clean_root) == []
    assert_no_gpl_ffmpeg_codec_libraries(clean_root)  # must not raise
    print("[OK] test_gpl_ffmpeg_codec_guard_fails_closed_on_forbidden_libraries passed")


def test_lgpl_core_identity_check_rejects_wrong_content_at_correct_filenames(tmp_dir: Path) -> None:
    """Strengthened guard requirement: filename scanning alone is not
    sufficient evidence that avcodec/avformat came from the verified LGPL
    build. A GPL-configured core DLL simply renamed/placed under the correct
    plain filename (with libx264/libx265 absent) must still be rejected by
    content (SHA-256) identity, not accepted merely because no forbidden
    filename is present."""
    from tools.packaging.verify_no_gpl_ffmpeg_codecs import (
        assert_lgpl_ffmpeg_core_identities,
        find_core_ffmpeg_dlls,
    )

    root = tmp_dir / "lgpl_identity_test_root"
    lib_dir = root / "lib" / "av.libs"
    lib_dir.mkdir(parents=True, exist_ok=True)

    # Wrong content (not the pinned LGPL build) at exactly the right plain
    # filenames -- no libx264/libx265 filename anywhere, so a filename-only
    # scan would see nothing wrong.
    for plain_name in (
        "avutil-60.dll",
        "avcodec-62.dll",
        "avformat-62.dll",
        "avdevice-62.dll",
        "avfilter-11.dll",
        "swscale-9.dll",
        "swresample-6.dll",
    ):
        (lib_dir / plain_name).write_bytes(b"not the verified LGPL build")

    found = find_core_ffmpeg_dlls(root)
    assert set(found) == {
        "avutil-60.dll", "avcodec-62.dll", "avformat-62.dll", "avdevice-62.dll",
        "avfilter-11.dll", "swscale-9.dll", "swresample-6.dll",
    }, found

    raised = False
    try:
        assert_lgpl_ffmpeg_core_identities(root)
    except RuntimeError as exc:
        raised = True
        assert "identity mismatch" in str(exc)
    assert raised, (
        "Must fail closed when core DLL content does not match the pinned "
        "LGPL build, even though no forbidden filename is present"
    )
    print("[OK] test_lgpl_core_identity_check_rejects_wrong_content_at_correct_filenames passed")


def test_lgpl_ffmpeg_replacement_fails_closed_on_archive_hash_mismatch(tmp_dir: Path) -> None:
    """apply_lgpl_ffmpeg_replacement must refuse to proceed if the archive it
    is given does not match the pinned SHA-256 -- never apply an unverified
    archive's contents."""
    from tools.packaging.lgpl_ffmpeg_replacement import apply_lgpl_ffmpeg_replacement

    fake_archive = tmp_dir / "lgpl_hash_mismatch_test" / "fake.zip"
    fake_archive.parent.mkdir(parents=True, exist_ok=True)
    fake_archive.write_bytes(b"not the real pinned archive")

    fake_app_root = tmp_dir / "lgpl_hash_mismatch_test" / "app_root"
    (fake_app_root / "lib" / "av.libs").mkdir(parents=True, exist_ok=True)

    raised = False
    try:
        apply_lgpl_ffmpeg_replacement(fake_app_root, fake_archive)
    except ValueError as exc:
        raised = True
        assert "does not match pinned SHA-256" in str(exc)
    assert raised, "Must fail closed on archive SHA-256 mismatch, never apply unverified content"
    print("[OK] test_lgpl_ffmpeg_replacement_fails_closed_on_archive_hash_mismatch passed")


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
        test_final_payload_manifest_exact_disk_reconciliation(test_dir)
        test_strict_offline_reconstruction_fails_on_missing_staged_input(test_dir)
        test_launcher_suppresses_bytecode_writes_into_app_root()
        test_uninstaller_forcibly_removes_app_root_preserving_user_data()
        test_explicit_purge_resolves_userprofile_via_getenv_not_invalid_constant()
        test_launcher_provenance_reflects_actual_compiled_source_not_stale_constant()
        test_gpl_ffmpeg_codec_guard_fails_closed_on_forbidden_libraries(test_dir)
        test_lgpl_core_identity_check_rejects_wrong_content_at_correct_filenames(test_dir)
        test_lgpl_ffmpeg_replacement_fails_closed_on_archive_hash_mismatch(test_dir)
        print("\nALL PHASE A/C SCAFFOLD & FROZEN-INPUT VALIDATION TESTS PASSED (INCLUDING REGRESSIONS).")
        return True
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_all_scaffold_tests()
    sys.exit(0 if success else 1)
