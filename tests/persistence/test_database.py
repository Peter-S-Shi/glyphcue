from glyphcue.persistence.database import connect


def test_connect_returns_migrated_connection(tmp_path):
    db_path = tmp_path / "glyphcue.sqlite3"

    conn = connect(db_path)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "cues" in tables
    assert db_path.exists()


def test_connect_enforces_foreign_keys(tmp_path):
    conn = connect(tmp_path / "glyphcue.sqlite3")

    (enabled,) = conn.execute("PRAGMA foreign_keys").fetchone()
    assert enabled == 1
