from __future__ import annotations

import sqlite3
from pathlib import Path

from glyphcue.persistence.migrations import apply_migrations


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) a GlyphCue SQLite database, fully migrated."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread stays at its default (True) deliberately: a
    # background job (e.g. the Milestone 4 OCR evidence job) must open
    # its own connection on its own worker thread rather than reusing a
    # connection created on the caller's thread. See
    # ObservationRepository / build_ocr_evidence_job for the pattern.
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    return conn
