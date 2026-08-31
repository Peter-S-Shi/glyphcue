import threading

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


def test_connection_can_be_used_from_a_background_thread(tmp_path):
    # Background jobs (e.g. the Milestone 4 OCR evidence job) write to a
    # connection created on the caller's thread from a worker thread --
    # sqlite3's default check_same_thread=True would raise there.
    conn = connect(tmp_path / "glyphcue.sqlite3")
    errors = []

    def write_from_thread():
        try:
            conn.execute(
                "INSERT INTO cues (id, start_time, end_time, review_state) "
                "VALUES ('c1', 0.0, 1.0, 'pending')"
            )
            conn.commit()
        except Exception as exc:  # pragma: no cover - failure path under test
            errors.append(exc)

    thread = threading.Thread(target=write_from_thread)
    thread.start()
    thread.join(timeout=5)

    assert errors == []
    row = conn.execute("SELECT id FROM cues WHERE id = 'c1'").fetchone()
    assert row == ("c1",)
