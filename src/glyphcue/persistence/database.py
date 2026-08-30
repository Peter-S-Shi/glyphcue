from __future__ import annotations

import sqlite3
from pathlib import Path

from glyphcue.persistence.migrations import apply_migrations


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) a GlyphCue SQLite database, fully migrated."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(conn)
    return conn
