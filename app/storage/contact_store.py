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
    ) -> None:
        self.database = database

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
            self.database.connection.execute(
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

            self.database.connection.commit()

            return "NEW"

        self.database.connection.execute(
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

        self.database.connection.commit()

        return "UPDATED"

    # --------------------------------------------------
    # Lookup
    # --------------------------------------------------

    def get_contact(
        self,
        contact_id: str,
    ) -> Optional[Any]:

        cursor = self.database.connection.cursor()

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

        cursor = self.database.connection.cursor()

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

        cursor = self.database.connection.cursor()

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

        cursor = self.database.connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM contacts
            """
        )

        return cursor.fetchone()[0]