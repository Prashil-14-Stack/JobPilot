import sqlite3

from app.storage.connection_factory import create_connection


def test_factory_uses_sqlite_without_database_url(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    connection, backend = create_connection(tmp_path / "test.db")

    try:
        assert backend == "sqlite"
        assert isinstance(connection, sqlite3.Connection)
        assert connection.execute("SELECT 1").fetchone()[0] == 1
    finally:
        connection.close()


def test_factory_preserves_sqlite_row_access(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    connection, backend = create_connection(tmp_path / "test.db")

    try:
        row = connection.execute("SELECT 7 AS number").fetchone()
        assert backend == "sqlite"
        assert row[0] == 7
        assert row["number"] == 7
        assert dict(row) == {"number": 7}
    finally:
        connection.close()
