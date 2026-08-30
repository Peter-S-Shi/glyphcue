from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from importlib import resources

_MIGRATIONS_PACKAGE = "glyphcue.persistence.migrations_sql"
_FILENAME_PATTERN = re.compile(r"^(\d+)_.*\.sql$")


def _pending_migrations() -> list[tuple[int, str]]:
    migrations: list[tuple[int, str]] = []
    package = resources.files(_MIGRATIONS_PACKAGE)
    for entry in package.iterdir():
        match = _FILENAME_PATTERN.match(entry.name)
        if not match:
            continue
        version = int(match.group(1))
        migrations.append((version, entry.read_text(encoding="utf-8")))
    migrations.sort(key=lambda item: item[0])
    return migrations


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply any not-yet-applied migrations to `conn`, in order.

    Safe to call multiple times: already-applied versions are skipped.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {
        row[0] for row in conn.execute("SELECT version FROM schema_migrations")
    }

    for version, sql in _pending_migrations():
        if version in applied:
            continue
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )

    conn.commit()
