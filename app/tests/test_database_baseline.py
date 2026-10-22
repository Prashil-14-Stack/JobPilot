from app.storage.database import JobDatabase


def test_database_initializes_and_counts_jobs(tmp_path):
    db = JobDatabase(tmp_path / "test_jobs.db")
    try:
        assert db.count_jobs() == 0
        assert isinstance(db.count_by_status(), dict)
    finally:
        db.close()


def test_database_supports_job_lookup(tmp_path):
    db = JobDatabase(tmp_path / "test_jobs.db")
    try:
        row = db.get_job("test-source", "missing-job")
        assert row is None
    finally:
        db.close()


def test_database_has_shared_catalogue_tables(tmp_path):
    db = JobDatabase(tmp_path / "test_jobs.db")
    try:
        cursor = db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert {"jobs", "contacts", "company_domains"} <= tables
    finally:
        db.close()
