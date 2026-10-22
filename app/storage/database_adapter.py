"""Small compatibility adapter for SQLite and PostgreSQL connections."""

from __future__ import annotations

from typing import Any

from app.storage.sql_compat import adapt_sql


class DatabaseAdapter:
    """Wrap a connection with backend-aware SQL execution."""

    def __init__(self, connection: Any, backend: str):
        if backend not in {"sqlite", "postgres"}:
            raise ValueError(f"Unsupported database backend: {backend}")

        self.connection = connection
        self.backend = backend

    def cursor(self):
        return _CursorAdapter(self.connection.cursor(), self.backend)

    def execute(self, sql: str, params=()):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def commit(self) -> None:
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


class _CursorAdapter:
    def __init__(self, cursor: Any, backend: str):
        self._cursor = cursor
        self._backend = backend

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._cursor.close()
        return False

    def execute(self, sql: str, params=()):
        sql = adapt_sql(sql, self._backend)
        self._cursor.execute(sql, params)
        return self

    def executemany(self, sql: str, params):
        sql = adapt_sql(sql, self._backend)
        self._cursor.executemany(sql, params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description
