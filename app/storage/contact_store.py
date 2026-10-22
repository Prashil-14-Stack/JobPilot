from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.models.contact import Contact
from app.storage.database import JobDatabase


class ContactStore:
    """
    Persistence layer for JobPilot contacts.

    SQLite is the source of truth for contacts discovered
    through Hunter or other future contact providers.
    """

    def __init__(
        self,
        database: JobDatabase,
        user_id: str | None = None,
    ) -> None:
        if not user_id or "@" not in user_id.strip():
            raise ValueError(
                "A valid authenticated user_id is required for contact storage."
            )

        import sqlite3
        from app.services.user_context import get_user_profile_directory

        self.database = database
        self.user_id = user_id.strip().lower()
        contacts_path = (
            get_user_profile_directory(self.user_id) / "contacts.db"
        )
        self.connection = sqlite3.connect(contacts_path)
        self.connection.row_factory = sqlite3.Row

        self.connection.execute(
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
        self.connection.commit()

    # --------------------------------------------------
    # Insert / Update
    # --------------------------------------------------

    def save_contact(self, contact: Contact) -> str:
        """
        Insert a new contact or update an existing contact.

        Returns:
            'NEW'     -> contact was inserted
            'UPDATED' -> existing contact was updated
        """

        existing = self.get_contact(contact.contact_id)

        now = datetime.now(timezone.utc).isoformat()

        if existing is None:
            self.connection.execute(
                """
                INSERT INTO contacts (
                    contact_id,
                    first_name,
                    last_name,
                    full_name,
                    email,
                    position,
                    company,
                    company_domain,
                    linkedin_url,
                    email_confidence,
                    email_verification_status,
                    source,
                    first_seen_at,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    contact.contact_id,
                    contact.first_name,
                    contact.last_name,
                    contact.full_name,
                    contact.email,
                    contact.position,
                    contact.company,
                    contact.company_domain,
                    contact.linkedin_url,
                    contact.email_confidence,
                    contact.email_verification_status,
                    contact.source,
                    now,
                    now,
                    now,
                    now,
                ),
            )

            self.connection.commit()

            return "NEW"

        self.connection.execute(
            """
            UPDATE contacts
            SET
                first_name = ?,
                last_name = ?,
                full_name = ?,
                email = ?,
                position = ?,
                company = ?,
                company_domain = ?,
                linkedin_url = ?,
                email_confidence = ?,
                email_verification_status = ?,
                source = ?,
                last_seen_at = ?,
                updated_at = ?
            WHERE contact_id = ?
            """,
            (
                contact.first_name,
                contact.last_name,
                contact.full_name,
                contact.email,
                contact.position,
                contact.company,
                contact.company_domain,
                contact.linkedin_url,
                contact.email_confidence,
                contact.email_verification_status,
                contact.source,
                now,
                now,
                contact.contact_id,
            ),
        )

        self.connection.commit()

        return "UPDATED"

    # --------------------------------------------------
    # Lookup
    # --------------------------------------------------

    def get_contact(
        self,
        contact_id: str,
    ) -> Optional[Any]:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM contacts
            WHERE contact_id = ?
            """,
            (contact_id,),
        )

        return cursor.fetchone()

    # --------------------------------------------------
    # Email lookup
    # --------------------------------------------------

    def get_contact_by_email(
        self,
        email: str,
    ) -> Optional[Any]:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM contacts
            WHERE LOWER(email) = LOWER(?)
            """,
            (email,),
        )

        return cursor.fetchone()

    # --------------------------------------------------
    # Company lookup
    # --------------------------------------------------

    def get_contacts_by_domain(
        self,
        company_domain: str,
    ) -> list[Any]:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM contacts
            WHERE LOWER(company_domain) = LOWER(?)
            ORDER BY email_confidence DESC
            """,
            (company_domain,),
        )

        return cursor.fetchall()

    # --------------------------------------------------
    # Counts
    # --------------------------------------------------

    def count_contacts(self) -> int:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM contacts
            """
        )

        return cursor.fetchone()[0]