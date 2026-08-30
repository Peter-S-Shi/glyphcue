import ast
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "glyphcue" / "domain"

FORBIDDEN_ROOTS = {
    "pysubs2",
    "av",
    "onnxruntime",
    "PySide6",
    "sqlite3",
    "PIL",
}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_package_does_not_import_third_party_vendor_libraries():
    offenders: dict[str, set[str]] = {}
    for path in DOMAIN_DIR.rglob("*.py"):
        found = _imported_roots(path) & FORBIDDEN_ROOTS
        if found:
            offenders[str(path)] = found

    assert offenders == {}, f"domain code imports vendor types: {offenders}"
