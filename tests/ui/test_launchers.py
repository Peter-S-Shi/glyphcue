"""The desktop launchers must stay pointed at the current UI entrypoint.

These exist because a local, untracked launcher drifted: it kept working
against an older shape of the app while the real entrypoint moved, and
nothing caught it. Both launchers are now tracked, and these tests fail
if either stops naming the module the app actually starts from.

M11 Legacy Pipeline Retirement Corrective Gate (2026-09-04) removed the
developer OCR Profile selector and its env var entirely: neither
launcher can reveal a profile picker or select EXPERIMENTAL_HYBRID
anymore, so both now go through the single PRODUCTION_TRIGGER pipeline
unconditionally -- see `test_neither_launcher_can_select_the_retired_hybrid_pipeline`.
"""

from pathlib import Path

import glyphcue.__main__ as package_entrypoint
from glyphcue.ui.app import main

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NORMAL = _REPO_ROOT / "Launch-GlyphCue.bat"
_DEV_QA = _REPO_ROOT / "Launch-GlyphCue-DevQA.bat"
_ENTRYPOINT_MODULE = "-m glyphcue"


def _read(path: Path) -> str:
    assert path.exists(), f"{path.name} is missing"
    return path.read_text(encoding="utf-8")


def test_the_package_entrypoint_is_the_current_ui_app():
    # `-m glyphcue` is what both launchers invoke, so this is the link
    # between them and the real product shell.
    assert package_entrypoint.main is main


def test_both_launchers_start_the_same_current_entrypoint():
    for path in (_NORMAL, _DEV_QA):
        assert _ENTRYPOINT_MODULE in _read(path), f"{path.name} does not run {_ENTRYPOINT_MODULE}"


def test_launchers_use_repository_relative_paths_only():
    # %~dp0 is this file's own directory, so a checkout can live anywhere.
    for path in (_NORMAL, _DEV_QA):
        content = _read(path)
        assert "%~dp0" in content
        assert ":\\" not in content.replace("%~dp0", ""), (
            f"{path.name} appears to hard-code an absolute path"
        )


def test_neither_launcher_can_select_the_retired_hybrid_pipeline():
    # The dev/QA launcher's only remaining difference from the normal one
    # is running on console python for visible progress/errors -- it must
    # never again be able to reveal a profile picker or reach
    # EXPERIMENTAL_HYBRID, on either launcher, by any wording.
    for path in (_NORMAL, _DEV_QA):
        content = _read(path)
        assert "EXPERIMENTAL_HYBRID" not in content
        assert "experimental_hybrid" not in content
        assert "OCR_PROFILE_SELECTOR" not in content.upper()
