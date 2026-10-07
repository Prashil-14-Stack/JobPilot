from datetime import datetime, timezone
from typing import Optional

from app.storage.database import JobDatabase


class CompanyDomainStore:
    """
    Persistence layer for resolved company domains.
    """

    def __init__(
        self,
        database: JobDatabase | None = None,
    ) -> None:
        self.database = database or JobDatabase()

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get(
        self,
        company: str,
    ) -> Optional[dict]:
        """
        Retrieve a stored domain resolution by company name.
        """

        cursor = self.database.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM company_domains
            WHERE normalized_company = ?
            """,
            (company.strip().lower(),),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    def save(
        self,
        company: str,
        domain: Optional[str],
        status: str,
        confidence: int,
        source: str,
        reason: str,
    ) -> str:
        """
        Insert or update a company domain resolution.

        Returns:
            NEW or UPDATED
        """

        now = self.utc_now()
        normalized_company = company.strip().lower()

        existing = self.get(company)

        cursor = self.database.connection.cursor()

        if existing is None:
            cursor.execute(
                """
                INSERT INTO company_domains (
                    company,
                    normalized_company,
                    domain,
                    status,
                    confidence,
                    source,
                    reason,
                    first_resolved_at,
                    last_resolved_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company,
                    normalized_company,
                    domain,
                    status,
                    confidence,
                    source,
                    reason,
                    now,
                    now,
                    now,
                    now,
                ),
            )

            self.database.connection.commit()

            return "NEW"

        cursor.execute(
            """
            UPDATE company_domains
            SET
                company = ?,
                domain = ?,
                status = ?,
                confidence = ?,
                source = ?,
                reason = ?,
                last_resolved_at = ?,
                updated_at = ?
            WHERE normalized_company = ?
            """,
            (
                company,
                domain,
                status,
                confidence,
                source,
                reason,
                now,
                now,
                normalized_company,
            ),
        )

        self.database.connection.commit()

        return "UPDATED"

    def count(self) -> int:
        """
        Return the number of stored company resolutions.
        """

        cursor = self.database.connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM company_domains
            """
        )

        return cursor.fetchone()[0]