import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from app.storage.database import JobDatabase


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONTENT_HASH_VERSION = "v2"

NORMALIZED_JOBS_PATH = (
    PROJECT_ROOT
    / "data"
    / "jobs"
    / "normalized_jobs.json"
)


class JobStore:
    """
    Handles ingestion of normalized jobs into SQLite.

    Responsibilities:
    - Insert NEW jobs
    - Detect EXISTING jobs
    - Detect UPDATED jobs
    - Preserve SQLite as the source of truth
    """

    # Fields that represent the discovered/source job itself.
    #
    # AI analysis fields are intentionally excluded from the hash.
    # This prevents an AI analysis update from making the source job
    # appear to have changed.
    CONTENT_FIELDS = [
        "title",
        "company",
        "location", 
        "country",
        "remote_type",
        "source_url",
        "apply_url",
        "description",  
        "highlights",
        "posted_date",
    ]

    # Fields that can safely be populated from normalized data.
    SOURCE_FIELDS = [
        "title",
        "company",
        "location",
        "country",
        "remote_type",
        "source_url",
        "apply_url",
        "description",
        "content_mode",
        "canonical_role",
        "matched_search_variant",
        "search_task_id",
        "posted_date",
        "visa_status",
        "visa_evidence",
        "work_authorization_requirement",
    ]

    def __init__(
        self,
        database: JobDatabase | None = None,
        normalized_jobs_path: Path = NORMALIZED_JOBS_PATH,
    ):
        self.database = database or JobDatabase()
        self.normalized_jobs_path = Path(normalized_jobs_path)

    # --------------------------------------------------
    # Utility
    # --------------------------------------------------

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def serialize(value: Any) -> str:
        """
        Convert Python values into stable JSON strings for SQLite.
        """

        if value is None:
            return ""

        if isinstance(value, (dict, list)):
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )

        return str(value)

    # --------------------------------------------------
    # Content hashing
    # --------------------------------------------------

    def calculate_content_hash(
        self,
        job: dict[str, Any],
    ) -> str:
        """
        Calculate a deterministic hash of source/job content.

        The hash version is included so that changes to the hashing
        definition can be handled explicitly.
        """

        content = {
            "hash_version": CONTENT_HASH_VERSION
        }

        for field in self.CONTENT_FIELDS:
            content[field] = job.get(field)

        serialized = json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()
    # --------------------------------------------------
    # Load normalized jobs
    # --------------------------------------------------

    def load_normalized_jobs(self) -> list[dict[str, Any]]:
        if not self.normalized_jobs_path.exists():
            raise FileNotFoundError(
                f"Normalized jobs file not found: "
                f"{self.normalized_jobs_path}"
            )

        with self.normalized_jobs_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        jobs = data.get("jobs", [])

        if not isinstance(jobs, list):
            raise ValueError(
                "Expected 'jobs' to be a list "
                "in normalized_jobs.json"
            )

        return jobs

    # --------------------------------------------------
    # Insert new job
    # --------------------------------------------------

    def insert_job(
        self,
        job: dict[str, Any],
        content_hash: str,
        now: str,
    ) -> None:

        cursor = self.database.connection.cursor()

        cursor.execute(
            """
            INSERT INTO jobs (
                source,
                source_job_id,

                title,
                company,

                location,
                country,
                remote_type,

                source_url,
                apply_url,

                description,
                content_mode,
                canonical_role,
                matched_search_variant,
                search_task_id,

                posted_date,
                discovered_at,

                visa_status,
                visa_evidence,
                work_authorization_requirement,

                relevance_score,
                relevance_level,

                match_reasons,
                missing_requirements,
                matched_skills,
                matched_experience,

                raw_provider_data,

                content_hash,

                first_seen_at,
                last_seen_at,

                processing_status,

                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                job.get("source"),
                job.get("source_job_id"),

                job.get("title"),
                job.get("company"),

                job.get("location"),
                job.get("country"),
                job.get("remote_type"),

                job.get("source_url"),
                job.get("apply_url"),

                job.get("description"),

                (
                    "METADATA_ONLY"
                    if job.get("source") == "Indeed"
                    else "FULL_CONTENT"
                ),

                job.get("canonical_role"),
                job.get("matched_search_variant"),
                job.get("search_task_id"),

                job.get("posted_date"),
                job.get("normalized_at"),

                job.get("visa_status"),
                job.get("visa_evidence"),
                job.get("work_authorization_requirement"),

                job.get("relevance_score"),
                job.get("relevance_level"),

                self.serialize(
                    job.get("match_reasons")
                ),
                self.serialize(
                    job.get("missing_requirements")
                ),
                self.serialize(
                    job.get("matched_skills")
                ),
                self.serialize(
                    job.get("matched_experience")
                ),

                self.serialize(
                    job.get("raw_data")
                ),

                content_hash,

                now,
                now,

                "NEW",

                now,
                now,
            ),
        )
    # --------------------------------------------------
    # Update existing job
    # --------------------------------------------------

    def update_job(
        self,
        job: dict[str, Any],
        content_hash: str,
        now: str,
    ) -> None:

        cursor = self.database.connection.cursor()

        cursor.execute(
            """
            UPDATE jobs

            SET
                title = ?,
                company = ?,
                location = ?,
                country = ?,
                remote_type = ?,

                source_url = ?,
                apply_url = ?,

                description = ?,

                canonical_role = ?,
                matched_search_variant = ?,
                search_task_id = ?,

                posted_date = ?,
                discovered_at = ?,

                visa_status = ?,
                visa_evidence = ?,
                work_authorization_requirement = ?,

                raw_provider_data = ?,

                content_hash = ?,

                last_seen_at = ?,

                processing_status = 'UPDATED',

                updated_at = ?

            WHERE source = ?
              AND source_job_id = ?
            """,
            (
                job.get("title"),
                job.get("company"),
                job.get("location"),
                job.get("country"),
                job.get("remote_type"),

                job.get("source_url"),
                job.get("apply_url"),

                job.get("description"),

                job.get("canonical_role"),
                job.get("matched_search_variant"),
                job.get("search_task_id"),

                job.get("posted_date"),
                job.get("normalized_at"),

                job.get("visa_status"),
                job.get("visa_evidence"),
                job.get("work_authorization_requirement"),

                self.serialize(
                    job.get("raw_data")
                ),

                content_hash,

                now,
                now,

                job.get("source"),
                job.get("source_job_id"),
            ),
        )
    # --------------------------------------------------
    # Update deterministic scoring
    # --------------------------------------------------

    def update_job_score(
        self,
        source: str,
        source_job_id: str,
        score_result: dict[str, Any],
    ) -> None:

        cursor = self.database.connection.cursor()

        cursor.execute(
            """
            UPDATE jobs
            SET
                relevance_score = ?,
                relevance_level = ?,
                matched_skills = ?,
                updated_at = ?
            WHERE source = ?
              AND source_job_id = ?
            """,
            (
                score_result.get("relevance_score"),
                score_result.get("relevance_level"),
                self.serialize(
                    score_result.get("matched_keywords")
                ),
                self.utc_now(),
                source,
                source_job_id,
            ),
        )
    # --------------------------------------------------
    # Process one job
    # --------------------------------------------------

    def process_job(
        self,
        job: dict[str, Any],
    ) -> str:

        source = job.get("source")
        source_job_id = job.get("source_job_id")

        # Stable identity is mandatory for incremental ingestion.
        if not source or not source_job_id:
            return "SKIPPED_NO_IDENTITY"

        content_hash = self.calculate_content_hash(job)

        existing = self.database.get_job(
            source=source,
            source_job_id=source_job_id,
        )

        now = self.utc_now()

        if existing is None:

            self.insert_job(
                job=job,
                content_hash=content_hash,
                now=now,
            )

            return "NEW"

        existing_hash = existing["content_hash"]

        if existing_hash == content_hash:

            cursor = self.database.connection.cursor()

            cursor.execute(
                """
                UPDATE jobs
                SET
                    last_seen_at = ?,
                    processing_status = 'EXISTING'
                WHERE source = ?
                  AND source_job_id = ?
                """,
                (
                    now,
                    source,
                    source_job_id,
                ),
            )

            return "EXISTING"

        self.update_job(
            job=job,
            content_hash=content_hash,
            now=now,
        )

        return "UPDATED"

    # --------------------------------------------------
    # Ingest all jobs
    # --------------------------------------------------

    def ingest(self) -> dict[str, int]:

        jobs = self.load_normalized_jobs()

        counts = {
            "NEW": 0,
            "EXISTING": 0,
            "UPDATED": 0,
            "SKIPPED_NO_IDENTITY": 0,
        }

        for job in jobs:

            status = self.process_job(job)

            counts[status] += 1

        self.database.connection.commit()

        return counts

    # --------------------------------------------------
    # Job review queue
    # --------------------------------------------------

    def dismiss_job(
        self,
        job_id: int,
    ) -> bool:
        """Persist a user's decision to dismiss a job."""

        cursor = self.database.connection.cursor()

        cursor.execute(
            """
            UPDATE jobs
            SET review_status = 'DISMISSED',
                updated_at = ?
            WHERE id = ?
            """,
            (
                self.utc_now(),
                job_id,
            ),
        )

        self.database.connection.commit()

        return cursor.rowcount > 0

    def get_pending_review_jobs(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return the next eligible jobs for the review queue."""

        cursor = self.database.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM jobs
            WHERE COALESCE(review_status, 'PENDING') = 'PENDING'
            ORDER BY
                CASE
                    WHEN posted_date IS NULL OR posted_date = ''
                    THEN 1
                    ELSE 0
                END,
                relevance_score DESC,
                discovered_at DESC,
                id DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]
# ------------------------------------------------------
# Command-line execution
# ------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("JOBPILOT JOB STORE")
    print("=" * 60)

    database = JobDatabase()

    store = JobStore(
        database=database
    )

    jobs = store.load_normalized_jobs()

    print(
        f"Normalized jobs: {len(jobs)}"
    )

    counts = store.ingest()

    print(
        f"Inserted:        {counts['NEW']}"
    )

    print(
        f"Existing:        {counts['EXISTING']}"
    )

    print(
        f"Updated:         {counts['UPDATED']}"
    )

    print(
        f"Skipped:         {counts['SKIPPED_NO_IDENTITY']}"
    )

    print()

    print(
        f"Database total:  {database.count_jobs()}"
    )

    print(
        f"Status counts:   {database.count_by_status()}"
    )

    database.close()