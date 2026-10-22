import pytest

from app.storage.sql_compat import adapt_sql


def test_sqlite_sql_is_unchanged():
    sql = "SELECT * FROM jobs WHERE source = ?"
    assert adapt_sql(sql, "sqlite") == sql


def test_postgres_placeholders_use_psycopg_format():
    sql = "SELECT * FROM jobs WHERE source = ? AND company = ?"
    assert adapt_sql(sql, "postgres") == (
        "SELECT * FROM jobs WHERE source = %s AND company = %s"
    )


def test_question_marks_inside_strings_are_preserved():
    sql = "SELECT '?' AS marker WHERE source = ?"
    assert adapt_sql(sql, "postgres") == (
        "SELECT '?' AS marker WHERE source = %s"
    )


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError):
        adapt_sql("SELECT 1", "unknown")
