from __future__ import annotations

import sys
from pathlib import Path


def normalize_source_id(path: str | Path) -> str:
    """Normalizes a local media path into a stable, canonical source identity.

    On Windows, ensures forward slashes and lowercased paths for case-insensitive
    consistency. On POSIX systems, uses resolved posix path.
    """
    resolved = Path(path).resolve()
    return resolved.as_posix().lower() if sys.platform == "win32" else resolved.as_posix()