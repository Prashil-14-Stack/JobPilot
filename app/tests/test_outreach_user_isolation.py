import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.networking.outreach_tracker import OutreachTracker


class OutreachUserIsolationTests(unittest.TestCase):
    def test_outreach_records_are_isolated_between_users(self):
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
                alice = OutreachTracker(user_id="alice@example.com")
                bob = OutreachTracker(user_id="bob@example.com")

                try:
                    message = SimpleNamespace(
                        job_id=123,
                        company="Example Co",
                        role="Business Analyst",
                        contact_name="Test Contact",
                        contact_email="contact@example.com",
                        subject="Test subject",
                        body="Test body",
                        cv_path="/tmp/test-cv.pdf",
                        status="DRAFT",
                    )

                    result = alice.record(
                        message=message,
                        job={
                            "location": "Remote",
                            "source": "Test",
                        },
                        contact={
                            "position": "Recruiter",
                        },
                    )

                    run_id = result["run_id"]

                    self.assertIsNotNone(
                        alice.get_outreach(run_id)
                    )
                    self.assertIsNone(
                        bob.get_outreach(run_id)
                    )
                    self.assertNotEqual(
                        alice.output_path,
                        bob.output_path,
                    )
                finally:
                    # The tracker stores files, so there are no DB
                    # connections to close here.
                    pass

    def test_missing_user_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            OutreachTracker()


if __name__ == "__main__":
    unittest.main()
