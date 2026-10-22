from __future__ import annotations

import sqlite3
from typing import Any

from app.services.user_context import get_user_profile_directory


class UserJobStatusStore:
    """Store job application and review state separately for each user."""

    def __init__(self, user_id: str):
        if not user_id or "@" not in user_id.strip():
            raise ValueError("A verified user identity is required.")

        self.user_id = user_id.strip().lower()
        profile_dir = get_user_profile_directory(self.user_id)
        self.database_path = profile_dir / "job_state.db"

        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_job_status (
                job_id INTEGER PRIMARY KEY,
                application_status TEXT NOT NULL DEFAULT 'NOT_APPLIED',
                applied_at TEXT,
                contact_status TEXT NOT NULL DEFAULT 'NOT_CONTACTED',
                review_status TEXT NOT NULL DEFAULT 'PENDING',
                updated_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def get_status(self, job_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT application_status, applied_at,
                   contact_status, review_status
            FROM user_job_status
            WHERE job_id = ?
            """,
            (int(job_id),),
        ).fetchone()

        if row is None:
            return {
                "application_status": "NOT_APPLIED",
                "applied_at": None,
                "contact_status": "NOT_CONTACTED",
                "review_status": "PENDING",
            }

        return dict(row)

    def get_all_statuses(self) -> dict[int, dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT job_id, application_status, applied_at, "
            "contact_status, review_status FROM user_job_status"
        ).fetchall()

        return {
            int(row["job_id"]): {
                key: row[key]
                for key in (
                    "application_status",
                    "applied_at",
                    "contact_status",
                    "review_status",
                )
            }
            for row in rows
        }

    def _update(self, job_id: int, field: str, value: str) -> bool:
        allowed_fields = {
            "application_status",
            "contact_status",
            "review_status",
        }
        if field not in allowed_fields:
            raise ValueError("Unsupported job status field.")

        now = self._now()
        self.connection.execute(
            f"""
            INSERT INTO user_job_status (job_id, {field}, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                {field} = excluded.{field},
                updated_at = excluded.updated_at
            """,
            (int(job_id), value, now),
        )
        self.connection.commit()
        return True

    def mark_applied(self, job_id: int) -> bool:
        now = self._now()
        self.connection.execute(
            """
            INSERT INTO user_job_status
                (job_id, application_status, applied_at, updated_at)
            VALUES (?, 'APPLIED', ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                application_status = 'APPLIED',
                applied_at = COALESCE(
                    user_job_status.applied_at, excluded.applied_at
                ),
                updated_at = excluded.updated_at
            """,
            (int(job_id), now, now),
        )
        self.connection.commit()
        return True

    def mark_contacted(self, job_id: int) -> bool:
        return self._update(job_id, "contact_status", "CONTACTED")

    def dismiss_job(self, job_id: int) -> bool:
        return self._update(job_id, "review_status", "DISMISSED")

    def close(self) -> None:
        self.connection.close()
