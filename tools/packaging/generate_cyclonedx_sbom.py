"""CycloneDX 1.6 JSON SBOM Generator for GlyphCue Release Packaging.

Consumes payload_manifest.json and outputs valid CycloneDX 1.6 JSON (specVersion: '1.6').
First-party and unresolved components carry NOASSERTION license expressions per
Wayfinder Issue #24 and #26 charter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def generate_cyclonedx_sbom(manifest_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    """Generate CycloneDX 1.6 JSON from payload_manifest.json."""
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest_data.get("files", [])

    # Group files into components
    component_map: dict[str, dict[str, Any]] = {}

    for f in files:
        role = f.get("role", "file")
        source = f.get("source_artifact", "unknown")
        lic = f.get("license", "UNKNOWN")
        v_status = f.get("verification_status", "unresolved")

        # Determine logical component key
        if role == "cpython_embeddable_runtime":
            comp_key = "python-embeddable-runtime"
            comp_name = "cpython-embeddable"
            comp_version = "3.12.10"
            comp_type = "framework"
            license_expr = "Python-2.0"
        elif role == "first_party_application_source":
            comp_key = "glyphcue-core"
            comp_name = "glyphcue"
            comp_version = "0.1.0"
            comp_type = "application"
            license_expr = "NOASSERTION"
        elif role == "first_party_database_migration":
            comp_key = "glyphcue-migrations"
            comp_name = "glyphcue-persistence-migrations"
            comp_version = "0.1.0"
            comp_type = "data"
            license_expr = "NOASSERTION"
        elif role == "onnx_model_weights":
            comp_key = "ppocr-onnx-models"
            comp_name = "paddleocr-onnx-models"
            comp_version = "v6"
            comp_type = "data"
            license_expr = "NOASSERTION"  # Redistribution rights unconfirmed
        elif role == "qt_runtime_plugin":
            comp_key = "pyside6-qt-plugins"
            comp_name = "pyside6-plugins"
            comp_version = "6.11.2"
            comp_type = "library"
            license_expr = "LGPL-3.0-only"
        elif role == "vendored_python_dependency":
            pkg = source.split(":")[-1] if ":" in source else source
            comp_key = f"wheel-{pkg}"
            comp_name = pkg
            comp_version = "vendored"
            comp_type = "library"
            license_expr = "NOASSERTION" if v_status == "unresolved" else "Third-Party-Declared"
        elif role == "first_party_launcher_pe":
            comp_key = "glyphcue-launcher"
            comp_name = "GlyphCue-Launcher"
            comp_version = "0.1.0"
            comp_type = "application"
            license_expr = "NOASSERTION"
        else:
            comp_key = f"other-{role}"
            comp_name = role
            comp_version = "1.0.0"
            comp_type = "library"
            license_expr = "NOASSERTION"

        if comp_key not in component_map:
            component_map[comp_key] = {
                "type": comp_type,
                "name": comp_name,
                "version": comp_version,
                "licenses": [{"expression": license_expr}],
                "properties": [
                    {"name": "glyphcue:role", "value": role},
                    {"name": "glyphcue:source_artifact", "value": source},
                    {"name": "glyphcue:verification_status", "value": v_status},
                ],
                "hashes": [],
            }

        component_map[comp_key]["hashes"].append(
            {"alg": "SHA-256", "content": f["sha256"]}
        )

    # Convert to CycloneDX 1.6 list
    cdx_components = []
    for k, v in sorted(component_map.items()):
        # Representative single component entry
        cdx_components.append({
            "type": v["type"],
            "name": v["name"],
            "version": v["version"],
            "licenses": v["licenses"],
            "properties": v["properties"],
        })

    # Deterministic serial number derived from manifest SHA
    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    serial_urn = f"urn:uuid:{manifest_hash[:8]}-{manifest_hash[8:12]}-{manifest_hash[12:16]}-{manifest_hash[16:20]}-{manifest_hash[20:32]}"

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": serial_urn,
        "version": 1,
        "metadata": {
            "timestamp": "2026-09-05T12:00:00Z",
            "tools": [
                {
                    "vendor": "GlyphCue Packaging Scaffold",
                    "name": "generate_cyclonedx_sbom.py",
                    "version": "1.0.0",
                }
            ],
            "component": {
                "type": "application",
                "name": "GlyphCue",
                "version": "0.1.0",
                "licenses": [{"expression": "NOASSERTION"}],
                "description": "Desktop Subtitle Workflow Application with Hardware-Accelerated OCR",
            },
        },
        "components": cdx_components,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(sbom, indent=2), encoding="utf-8")

    return sbom


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate CycloneDX 1.6 JSON from payload_manifest.json")
    parser.add_argument("manifest", type=Path, help="Path to payload_manifest.json")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output CycloneDX sbom.json path")
    args = parser.parse_args()

    out = args.output or (args.manifest.parent / "sbom.json")
    res = generate_cyclonedx_sbom(args.manifest, out)
    print(f"Generated CycloneDX 1.6 SBOM: {out}")
    print(f"SpecVersion: {res['specVersion']}, Components count: {len(res['components'])}")
