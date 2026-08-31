import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "glyphcue"
DOMAIN_DIR = SRC_DIR / "domain"
APPLICATION_DIR = SRC_DIR / "application"
JOBS_DIR = SRC_DIR / "jobs"

FORBIDDEN_ROOTS = {
    "pysubs2",
    "av",
    "onnxruntime",
    "PySide6",
    "sqlite3",
    "PIL",
    "rapidocr",
    "rapidocr_onnxruntime",
    "paddleocr",
    "paddle",
}

# jobs/ legitimately depends on PySide6 (QObject/Signal for cross-thread
# progress reporting, per ROADMAP.md Milestone 2) -- that is not an OCR
# vendor leak, so it is checked against a narrower list.
FORBIDDEN_OCR_VENDOR_ROOTS = {
    "onnxruntime",
    "rapidocr",
    "rapidocr_onnxruntime",
    "paddleocr",
    "paddle",
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


def _scan(directory: Path, forbidden: set[str]) -> dict[str, set[str]]:
    offenders: dict[str, set[str]] = {}
    for path in directory.rglob("*.py"):
        found = _imported_roots(path) & forbidden
        if found:
            offenders[str(path)] = found
    return offenders


def test_domain_package_does_not_import_third_party_vendor_libraries():
    offenders = _scan(DOMAIN_DIR, FORBIDDEN_ROOTS)
    assert offenders == {}, f"domain code imports vendor types: {offenders}"


def test_application_package_does_not_import_ocr_vendor_libraries():
    offenders = _scan(APPLICATION_DIR, FORBIDDEN_OCR_VENDOR_ROOTS)
    assert offenders == {}, f"application code imports vendor types: {offenders}"


def test_jobs_package_does_not_import_ocr_vendor_libraries():
    offenders = _scan(JOBS_DIR, FORBIDDEN_OCR_VENDOR_ROOTS)
    assert offenders == {}, f"jobs code imports vendor types: {offenders}"
