from __future__ import annotations

import sqlite3
from pathlib import Path

from glyphcue.persistence.migrations import apply_migrations


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) a GlyphCue SQLite database, fully migrated."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: background jobs (e.g. the Milestone 4 OCR
    # evidence job) write to this connection from a worker thread, not
    # the thread that created it. Safe here because access is always
    # effectively serialized -- callers `.wait()` for the writing job to
    # finish before reading from this connection again elsewhere.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    return conn
