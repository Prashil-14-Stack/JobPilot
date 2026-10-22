"""Small SQL compatibility helpers for SQLite and PostgreSQL."""

from __future__ import annotations


def adapt_sql(sql: str, backend: str) -> str:
    """Adapt SQLite question-mark placeholders for Psycopg 3."""
    if backend == "sqlite":
        return sql

    if backend != "postgres":
        raise ValueError(f"Unsupported database backend: {backend}")

    result: list[str] = []
    in_single = False
    in_double = False
    i = 0

    while i < len(sql):
        char = sql[i]

        if char == "'" and not in_double:
            result.append(char)
            if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                result.append("'")
                i += 2
                continue
            in_single = not in_single
        elif char == '"' and not in_single:
            result.append(char)
            in_double = not in_double
        elif char == "?" and not in_single and not in_double:
            result.append("%s")
        else:
            result.append(char)

        i += 1

    return "".join(result)
