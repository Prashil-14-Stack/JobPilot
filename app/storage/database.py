import sqlite3
from pathlib import Path
from typing import Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data" / "jobs"
DATABASE_PATH = DATA_DIR / "jobpilot.db"


class JobDatabase:
    """
    SQLite persistence layer for JobPilot.

    SQLite is the source of truth for discovered jobs and their
    processing/analysis state.
    """

    def __init__(self, database_path: Path = DATABASE_PATH):
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.connection = sqlite3.connect(
            self.database_path
        )

        self.connection.row_factory = sqlite3.Row

        self.initialize()

    # --------------------------------------------------
    # Database initialization
    # --------------------------------------------------

    def initialize(self) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                source TEXT NOT NULL,
                source_job_id TEXT,

                title TEXT,
                company TEXT,

                location TEXT,
                country TEXT,
                remote_type TEXT,

                source_url TEXT,
                apply_url TEXT,

                description TEXT,
                content_mode TEXT DEFAULT 'FULL_CONTENT',

                canonical_role TEXT,
                matched_search_variant TEXT,
                search_task_id TEXT,

                posted_date TEXT,
                discovered_at TEXT,

                visa_status TEXT,
                visa_evidence TEXT,
                work_authorization_requirement TEXT,

                relevance_score REAL,
                relevance_level TEXT,

                match_reasons TEXT,
                missing_requirements TEXT,
                matched_skills TEXT,
                matched_experience TEXT,

                raw_provider_data TEXT,

                content_hash TEXT,

                first_seen_at TEXT,
                last_seen_at TEXT,

                processing_status TEXT DEFAULT 'NEW',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                UNIQUE(source, source_job_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                source TEXT NOT NULL,
                source_job_id TEXT,

                title TEXT,
                company TEXT,

                location TEXT,
                country TEXT,
                remote_type TEXT,

                source_url TEXT,
                apply_url TEXT,

                description TEXT,
                content_mode TEXT DEFAULT 'FULL_CONTENT',

                canonical_role TEXT,
                matched_search_variant TEXT,
                search_task_id TEXT,

                posted_date TEXT,
                discovered_at TEXT,

                visa_status TEXT,
                visa_evidence TEXT,
                work_authorization_requirement TEXT,

                relevance_score REAL,
                relevance_level TEXT,

                match_reasons TEXT,
                missing_requirements TEXT,
                matched_skills TEXT,
                matched_experience TEXT,

                raw_provider_data TEXT,

                content_hash TEXT,

                first_seen_at TEXT,
                last_seen_at TEXT,

                processing_status TEXT DEFAULT 'NEW',

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                UNIQUE(source, source_job_id)
            )
            """
        )

        # --------------------------------------------------
        # Contacts table
        # --------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                contact_id TEXT NOT NULL UNIQUE,

                first_name TEXT,
                last_name TEXT,
                full_name TEXT,

                email TEXT,
                position TEXT,

                company TEXT,
                company_domain TEXT,

                linkedin_url TEXT,

                email_confidence INTEGER,
                email_verification_status TEXT,

                source TEXT DEFAULT 'Hunter',

                first_seen_at TEXT,
                last_seen_at TEXT,

                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_source
            ON jobs(source)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_source
            ON jobs(source)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_processing_status
            ON jobs(processing_status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_content_hash
            ON jobs(content_hash)
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS company_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                company TEXT NOT NULL UNIQUE,
                normalized_company TEXT NOT NULL,

                domain TEXT,
                status TEXT NOT NULL,
                confidence INTEGER DEFAULT 0,

                source TEXT,
                reason TEXT,

                first_resolved_at TEXT,
                last_resolved_at TEXT,

                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        # --------------------------------------------------
        # Schema migration: content_mode
        # --------------------------------------------------

        cursor.execute(
            """
            PRAGMA table_info(jobs)
            """
        )

        columns = {
            row[1]
            for row in cursor.fetchall()
        }

        if "content_mode" not in columns:
            cursor.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN content_mode TEXT
                DEFAULT 'FULL_CONTENT'
                """
            )

        # --------------------------------------------------
        # Schema migration: review_status
        # --------------------------------------------------

        cursor.execute(
            """
            PRAGMA table_info(jobs)
            """
        )

        columns = {
            row[1]
            for row in cursor.fetchall()
        }

        if "review_status" not in columns:
            cursor.execute(
                """
                ALTER TABLE jobs
                ADD COLUMN review_status TEXT
                DEFAULT 'PENDING'
                """
            )

        self.connection.commit()

    # --------------------------------------------------
    # Connection management
    # --------------------------------------------------

    def close(self) -> None:
        self.connection.close()

    # --------------------------------------------------
    # Basic lookup
    # --------------------------------------------------

    def get_job(
        self,
        source: str,
        source_job_id: str
    ) -> Optional[sqlite3.Row]:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM jobs
            WHERE source = ?
              AND source_job_id = ?
            """,
            (
                source,
                source_job_id
            )
        )

        return cursor.fetchone()

    def get_unique_companies(self) -> list[str]:
        """
        Return unique non-empty company names from the jobs table.
        """

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT DISTINCT company
            FROM jobs
            WHERE company IS NOT NULL
              AND TRIM(company) != ''
            ORDER BY company
            """
        )

        return [
            row["company"]
            for row in cursor.fetchall()
        ]

    # --------------------------------------------------
    # Counts
    # --------------------------------------------------

    def count_jobs(self) -> int:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM jobs
            """
        )

        return cursor.fetchone()[0]

    def count_by_status(self) -> dict[str, int]:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT
                processing_status,
                COUNT(*) AS count
            FROM jobs
            GROUP BY processing_status
            ORDER BY processing_status
            """
        )

        return {
            row["processing_status"]: row["count"]
            for row in cursor.fetchall()
        }


if __name__ == "__main__":

    print("=" * 60)
    print("JOBPILOT SQLITE DATABASE")
    print("=" * 60)

    database = JobDatabase()

    print(f"Database: {database.database_path}")
    print(f"Total jobs: {database.count_jobs()}")
    print(f"Status counts: {database.count_by_status()}")

    database.close()