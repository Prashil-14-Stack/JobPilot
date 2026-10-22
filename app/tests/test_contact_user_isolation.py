import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models.contact import Contact
from app.storage.contact_store import ContactStore


class ContactUserIsolationTests(unittest.TestCase):
    def test_contacts_are_isolated_between_users(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def user_dir(user_id):
                path = root / user_id.replace("@", "_")
                path.mkdir(parents=True, exist_ok=True)
                return path

            with patch(
                "app.services.user_context.get_user_profile_directory",
                side_effect=user_dir,
            ):
                alice = ContactStore(
                    database=None,
                    user_id="alice@example.com",
                )
                bob = ContactStore(
                    database=None,
                    user_id="bob@example.com",
                )

                try:
                    alice.save_contact(
                        Contact(
                            contact_id="contact-1",
                            full_name="Alice's contact",
                            email="contact@example.com",
                            company="Example Co",
                            company_domain="example.com",
                        )
                    )

                    self.assertIsNotNone(
                        alice.get_contact("contact-1")
                    )
                    self.assertIsNone(
                        bob.get_contact("contact-1")
                    )
                    self.assertNotEqual(
                        alice.connection.execute("PRAGMA database_list").fetchone()[2],
                        bob.connection.execute("PRAGMA database_list").fetchone()[2],
                    )
                finally:
                    alice.connection.close()
                    bob.connection.close()

    def test_missing_user_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            ContactStore(database=None)


if __name__ == "__main__":
    unittest.main()
