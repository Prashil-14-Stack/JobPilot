import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.networking.gmail_sender import GmailSender


class GmailUserIsolationTests(unittest.TestCase):
    def test_real_constructor_assigns_separate_token_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def user_dir(user_id):
                path = root / user_id.replace("@", "_")
                path.mkdir(parents=True, exist_ok=True)
                return path

            with (
                patch(
                    "app.services.user_context.get_user_profile_directory",
                    side_effect=user_dir,
                ),
                patch.object(GmailSender, "_authenticate", return_value=None),
            ):
                alice = GmailSender(user_id="alice@example.com")
                bob = GmailSender(user_id="bob@example.com")

            self.assertEqual(alice.token_path.name, "gmail_token.json")
            self.assertEqual(bob.token_path.name, "gmail_token.json")
            self.assertNotEqual(alice.token_path, bob.token_path)
            self.assertNotEqual(
                alice.token_path.parent,
                bob.token_path.parent,
            )

    def test_missing_user_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            GmailSender()

    def test_blank_user_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            GmailSender(user_id=" ")


if __name__ == "__main__":
    unittest.main()
