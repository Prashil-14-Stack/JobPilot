
import unittest
from unittest.mock import MagicMock, patch

import streamlit as st

from app.networking import gmail_oauth


class GmailOAuthTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()

    def tearDown(self):
        st.session_state.clear()

    def test_rejects_mismatched_oauth_state(self):
        st.session_state[gmail_oauth.USER_KEY] = "alice@example.com"
        st.session_state[gmail_oauth.STATE_KEY] = "expected-state"

        with self.assertRaisesRegex(PermissionError, "state validation"):
            gmail_oauth.finish_gmail_authorization(
                "alice@example.com",
                {
                    "state": "wrong-state",
                    "code": "test-code",
                },
            )

    def test_rejects_different_signed_in_user(self):
        st.session_state[gmail_oauth.USER_KEY] = "alice@example.com"
        st.session_state[gmail_oauth.STATE_KEY] = "expected-state"

        with self.assertRaisesRegex(PermissionError, "does not match"):
            gmail_oauth.finish_gmail_authorization(
                "bob@example.com",
                {
                    "state": "expected-state",
                    "code": "test-code",
                },
            )

    def test_saves_token_to_authenticated_users_profile(self):
        st.session_state[gmail_oauth.USER_KEY] = "alice@example.com"
        st.session_state[gmail_oauth.STATE_KEY] = "expected-state"
        st.session_state["jobpilot_gmail_oauth_url"] = "test-url"

        credentials = MagicMock()
        credentials.refresh_token = "test-refresh-token"
        credentials.to_json.return_value = '{"token": "test"}'

        flow = MagicMock()
        flow.credentials = credentials

        with (
            patch.object(gmail_oauth, "_new_flow", return_value=flow),
            patch.object(
                gmail_oauth,
                "gmail_token_path",
            ) as mock_token_path,
        ):
            from pathlib import Path
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as tmp:
                token_path = Path(tmp) / "alice" / "gmail_token.json"
                mock_token_path.return_value = token_path

                gmail_oauth.finish_gmail_authorization(
                    "alice@example.com",
                    {
                        "state": "expected-state",
                        "code": "test-code",
                    },
                )

                self.assertTrue(token_path.exists())
                self.assertEqual(
                    token_path.read_text(encoding="utf-8"),
                    '{"token": "test"}',
                )

        self.assertNotIn(gmail_oauth.STATE_KEY, st.session_state)
        self.assertNotIn(gmail_oauth.USER_KEY, st.session_state)
        self.assertNotIn(
            "jobpilot_gmail_oauth_url",
            st.session_state,
        )


if __name__ == "__main__":
    unittest.main()
