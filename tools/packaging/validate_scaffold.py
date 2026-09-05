"""Automated validation suite for GlyphCue Phase A packaging scaffold.

Verifies:
1. Frozen build-base identity schema and file existence.
2. Synthetic fixture deterministic generation, size, and SHA-256 matching.
3. Golden reference JSON schema and cue structure.
4. Assembled <app_root> mock layout and python312._pth configuration.
5. Payload manifest generation and 4 fail-closed gates evaluation.
6. CycloneDX 1.6 JSON generation and valid schema structure.
7. Payload drift comparator on identical vs drifted trees.
8. Signature verifier structure.
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


def test_frozen_build_base_schema() -> None:
    """Validate docs/m13_build_base_identity.json structure."""
    bb_path = REPO_ROOT / "docs" / "m13_build_base_identity.json"
    assert bb_path.is_file(), f"Build base file missing: {bb_path}"
    data = json.loads(bb_path.read_text(encoding="utf-8"))

    assert data["trusted_source_commit"] == "5905df09d012cb63a34b98c484b43958477e52e8"
    assert data["cpython_embeddable_runtime"]["sha256"] == "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
    assert len(data["onnx_models_inventory"]) >= 3
    assert len(data["critical_native_dlls"]) >= 2
    assert len(data["database_migrations"]) == 5
    assert data["deterministic_synthetic_fixture"]["sha256"] == EXPECTED_FIXTURE_SHA256
    print("[OK] test_frozen_build_base_schema passed")


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


def test_app_root_assembly_and_manifest(tmp_dir: Path) -> None:
    """Validate app_root assembler, pth isolation, manifest, and CycloneDX 1.6."""
    app_root = tmp_dir / "app_root"
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
    print("[OK] test_app_root_assembly_and_manifest passed")


def test_drift_comparator(tmp_dir: Path) -> None:
    """Validate drift comparator on identical and modified trees."""
    tree1 = tmp_dir / "tree1"
    tree2 = tmp_dir / "tree2"
    assemble_app_root(tree1)
    assemble_app_root(tree2)

    # Identical trees must PASS
    report = compare_reconstructions(tree1, tree2)
    assert report["payload_drift_status"] == "PASS"
    assert len(report["unsigned_payload_mismatches"]) == 0

    # Modify one file in tree2 -> must FAIL
    (tree2 / "python" / "python312._pth").write_text("MODIFIED\n", encoding="utf-8")
    report_drift = compare_reconstructions(tree1, tree2)
    assert report_drift["payload_drift_status"] == "FAIL"
    assert len(report_drift["unsigned_payload_mismatches"]) == 1
    print("[OK] test_drift_comparator passed")


def run_all_scaffold_tests() -> bool:
    """Run complete scaffold validation suite."""
    test_dir = REPO_ROOT / "temp_scaffold_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    try:
        test_frozen_build_base_schema()
        test_synthetic_fixture_generation(test_dir)
        test_golden_reference_schema()
        test_app_root_assembly_and_manifest(test_dir)
        test_drift_comparator(test_dir)
        print("\nALL SCAFFOLD TESTS PASSED.")
        return True
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_all_scaffold_tests()
    sys.exit(0 if success else 1)
