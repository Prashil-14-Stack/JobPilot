import sqlite3

import pytest

from app.storage.database_adapter import DatabaseAdapter


def test_sqlite_adapter_preserves_queries_and_rows():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    db = DatabaseAdapter(connection, "sqlite")

    db.execute("CREATE TABLE sample (id INTEGER, name TEXT)")
    db.execute("INSERT INTO sample VALUES (?, ?)", (1, "JobPilot"))

    row = db.execute("SELECT id, name FROM sample").fetchone()

    assert row[0] == 1
    assert row["name"] == "JobPilot"
    assert dict(row) == {"id": 1, "name": "JobPilot"}

    db.close()


def test_adapter_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unsupported database backend"):
        DatabaseAdapter(object(), "unknown")
