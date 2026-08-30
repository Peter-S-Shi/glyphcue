import sqlite3

from glyphcue.persistence.migrations import apply_migrations


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def test_apply_migrations_creates_expected_tables():
    conn = sqlite3.connect(":memory:")

    apply_migrations(conn)

    tables = _table_names(conn)
    assert "schema_migrations" in tables
    assert "cues" in tables
    assert "language_layers" in tables


def test_apply_migrations_is_idempotent():
    conn = sqlite3.connect(":memory:")

    apply_migrations(conn)
    apply_migrations(conn)

    applied = conn.execute("SELECT version FROM schema_migrations").fetchall()
    versions = [row[0] for row in applied]
    assert versions == sorted(set(versions))
    assert len(versions) == len(set(versions))
