"""Create database connections for JobPilot."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from app.storage.hybrid_row import hybrid_row_factory


def create_connection(
    database_path: Path,
    database_url: str | None = None,
    backend: str | None = None,
) -> tuple[Any, str]:
    """
    Return (connection, backend).

    SQLite remains the default. PostgreSQL requires an explicit backend
    selection and a database URL.
    """
    selected_backend = (backend or "sqlite").strip().lower()

    if selected_backend == "postgres":
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError(
                "PostgreSQL selected, but DATABASE_URL is not configured."
            )

        import psycopg

        connection = psycopg.connect(
            url,
            connect_timeout=10,
            row_factory=hybrid_row_factory,
        )
        return connection, "postgres"

    if selected_backend != "sqlite":
        raise ValueError(
            f"Unsupported database backend: {selected_backend}"
        )

    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection, "sqlite"
