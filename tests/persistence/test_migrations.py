import sqlite3

import pytest

from glyphcue.persistence import migrations
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


def test_a_failing_migration_leaves_no_partial_schema_or_false_version_record(
    monkeypatch,
):
    conn = sqlite3.connect(":memory:")
    failing_migration = (
        1,
        "CREATE TABLE will_not_persist (id INTEGER PRIMARY KEY);"
        "INSERT INTO no_such_table VALUES (1);",
    )
    monkeypatch.setattr(
        migrations, "_pending_migrations", lambda: [failing_migration]
    )

    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn)

    assert "will_not_persist" not in _table_names(conn)
    applied = conn.execute("SELECT version FROM schema_migrations").fetchall()
    assert applied == []


def test_migrations_can_proceed_normally_after_a_prior_failed_attempt(monkeypatch):
    conn = sqlite3.connect(":memory:")
    failing_migration = (
        1,
        "CREATE TABLE will_not_persist (id INTEGER PRIMARY KEY);"
        "INSERT INTO no_such_table VALUES (1);",
    )
    monkeypatch.setattr(
        migrations, "_pending_migrations", lambda: [failing_migration]
    )
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn)

    monkeypatch.undo()
    apply_migrations(conn)

    tables = _table_names(conn)
    assert "cues" in tables
    assert "language_layers" in tables
