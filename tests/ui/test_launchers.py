"""The desktop launchers must stay pointed at the current UI entrypoint.

These exist because a local, untracked launcher drifted: it kept working
against an older shape of the app while the real entrypoint moved, and
nothing caught it. Both launchers are now tracked, and these tests fail
if either stops naming the module the app actually starts from, or if
the dev/QA one stops being the only one that reveals developer controls.
"""

from pathlib import Path

import glyphcue.__main__ as package_entrypoint
from glyphcue.ui.app import DEV_OCR_PROFILE_SELECTOR_ENV_VAR, main

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


def test_only_the_dev_qa_launcher_reveals_the_developer_profile_selector():
    normal, dev_qa = _read(_NORMAL), _read(_DEV_QA)

    assert DEV_OCR_PROFILE_SELECTOR_ENV_VAR not in normal
    assert f"{DEV_OCR_PROFILE_SELECTOR_ENV_VAR}=1" in dev_qa


def test_the_dev_qa_launcher_does_not_change_the_default_profile():
    """Revealing the selector is all it does. Nothing here may preselect
    Experimental Hybrid -- the dropdown still opens on Production, and a
    run uses Hybrid only if a human picks it."""
    dev_qa = _read(_DEV_QA)

    assert "EXPERIMENTAL_HYBRID" not in dev_qa
    assert "experimental_hybrid" not in dev_qa
