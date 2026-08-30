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


def _statements(sql: str) -> list[str]:
    """Split a migration file into individual statements.

    Deliberately not `Connection.executescript`: that method issues an
    implicit COMMIT of any pending transaction before it runs, which would
    make it impossible to keep a migration's schema change and its
    schema_migrations version record inside one atomic transaction.
    """
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply any not-yet-applied migrations to `conn`, in order.

    Safe to call multiple times: already-applied versions are skipped.

    Each migration's schema changes and its schema_migrations version
    record are committed together in a single transaction. If a migration
    fails partway through, the whole transaction is rolled back, so no
    partial schema change or false version record is left behind, and a
    later call can retry the same migration cleanly.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    conn.commit()

    applied = {
        row[0] for row in conn.execute("SELECT version FROM schema_migrations")
    }

    for version, sql in _pending_migrations():
        if version in applied:
            continue
        try:
            conn.execute("BEGIN")
            for statement in _statements(sql):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
