
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import streamlit as st

from app.networking import gmail_oauth


TEST_CONFIG = {
    "client_id": "test-client-id",
    "client_secret": "test-client-secret",
    "redirect_uri": "https://example.com/callback",
    "state_secret": "test-state-secret-for-unit-tests",
}


class GmailOAuthTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
        self.config_patch = patch.object(
            gmail_oauth, "_oauth_config", return_value=TEST_CONFIG
        )
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def tearDown(self):
        st.session_state.clear()

    def test_rejects_mismatched_oauth_state(self):
        with self.assertRaisesRegex(PermissionError, "invalid, expired"):
            gmail_oauth.finish_gmail_authorization(
                "alice@example.com",
                {"state": "wrong-state", "code": "test-code"},
            )

    def test_rejects_different_signed_in_user(self):
        state = gmail_oauth._create_signed_state(
            "alice@example.com", now=1000
        )

        with self.assertRaisesRegex(PermissionError, "different signed-in user"):
            gmail_oauth._verify_signed_state(
                state, "bob@example.com", now=1001
            )

    def test_rejects_expired_state(self):
        state = gmail_oauth._create_signed_state(
            "alice@example.com", now=1000
        )

        with self.assertRaisesRegex(PermissionError, "invalid, expired"):
            gmail_oauth._verify_signed_state(
                state,
                "alice@example.com",
                now=1000 + gmail_oauth.STATE_TTL_SECONDS + 1,
            )

    def test_saves_token_to_authenticated_users_profile(self):
        state = gmail_oauth._create_signed_state(
            "alice@example.com", now=1000
        )

        credentials = MagicMock()
        credentials.refresh_token = "test-refresh-token"
        credentials.to_json.return_value = '{"token": "test"}'

        flow = MagicMock()
        flow.credentials = credentials

        with (
            patch.object(gmail_oauth, "_new_flow", return_value=flow),
            patch.object(gmail_oauth, "gmail_token_path") as mock_token_path,
            patch.object(gmail_oauth.time, "time", return_value=1001),
        ):
            with TemporaryDirectory() as tmp:
                token_path = Path(tmp) / "alice" / "gmail_token.json"
                mock_token_path.return_value = token_path

                gmail_oauth.finish_gmail_authorization(
                    "alice@example.com",
                    {"state": state, "code": "test-code"},
                )

                self.assertTrue(token_path.exists())
                self.assertEqual(
                    token_path.read_text(encoding="utf-8"),
                    '{"token": "test"}',
                )

        self.assertNotIn(gmail_oauth.STATE_KEY, st.session_state)
        self.assertNotIn(gmail_oauth.USER_KEY, st.session_state)
        self.assertNotIn(gmail_oauth.URL_KEY, st.session_state)


if __name__ == "__main__":
    unittest.main()