import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.storage.user_job_status_store import UserJobStatusStore


class UserJobStatusIsolationTests(unittest.TestCase):
    def test_status_and_dismissal_are_isolated_between_users(self):
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
                alice = UserJobStatusStore("alice@example.com")
                bob = UserJobStatusStore("bob@example.com")

                try:
                    alice.mark_applied(101)
                    alice.dismiss_job(202)

                    self.assertEqual(
                        alice.get_status(101)["application_status"],
                        "APPLIED",
                    )
                    self.assertEqual(
                        alice.get_status(202)["review_status"],
                        "DISMISSED",
                    )

                    self.assertEqual(
                        bob.get_status(101)["application_status"],
                        "NOT_APPLIED",
                    )
                    self.assertEqual(
                        bob.get_status(202)["review_status"],
                        "PENDING",
                    )
                    self.assertNotEqual(
                        alice.database_path,
                        bob.database_path,
                    )
                finally:
                    alice.close()
                    bob.close()

    def test_missing_user_identity_is_rejected(self):
        for user_id in ("", " ", "not-an-email"):
            with self.subTest(user_id=user_id):
                with self.assertRaises(ValueError):
                    UserJobStatusStore(user_id)


if __name__ == "__main__":
    unittest.main()
