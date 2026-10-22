import ast
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch


UI_PATH = Path(__file__).resolve().parents[1] / "ui.py"


def load_actual_helper(namespace: dict) -> None:
    """Load the real helper definition without executing the Streamlit app."""
    tree = ast.parse(UI_PATH.read_text(encoding="utf-8"))

    helper = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "mark_outreach_job_contacted"
        ),
        None,
    )

    if helper is None:
        raise AssertionError(
            "mark_outreach_job_contacted() was not found in app/ui.py"
        )

    isolated_module = ast.Module(body=[helper], type_ignores=[])
    ast.fix_missing_locations(isolated_module)
    exec(compile(isolated_module, str(UI_PATH), "exec"), namespace)


class MarkOutreachJobContactedTests(unittest.TestCase):
    def setUp(self):
        self.tracker = Mock()
        self.tracker.get_outreach.return_value = {"Job ID": "42"}

        self.store = Mock()
        self.store.mark_contacted.return_value = True

        self.status_store_patcher = patch(
            "app.storage.user_job_status_store.UserJobStatusStore",
            return_value=self.store,
        )
        self.status_store_patcher.start()
        self.addCleanup(self.status_store_patcher.stop)

        namespace = {
            "Any": Any,
            "AUTH_USER_ID": "test.user@example.com",
            "OutreachTracker": Mock(return_value=self.tracker),
        }
        load_actual_helper(namespace)
        actual_helper = namespace["mark_outreach_job_contacted"]
        self.helper = lambda run_id, result: actual_helper(
            run_id, result, "test.user@example.com"
        )

    def test_confirmed_send_marks_correct_job(self):
        result = {
            "status": "SENT",
            "gmail_message_id": "gmail-message-123",
        }

        saved = self.helper("run-1", result)

        self.assertTrue(saved)
        self.tracker.get_outreach.assert_called_once_with("run-1")
        self.store.mark_contacted.assert_called_once_with(42)
        self.store.close.assert_called_once()

    def test_send_failure_does_not_mark_contacted(self):
        saved = self.helper(
            "run-1",
            {"status": "SEND_FAILED", "error_message": "Simulated failure"},
        )

        self.assertFalse(saved)
        self.tracker.get_outreach.assert_not_called()
        self.store.mark_contacted.assert_not_called()

    def test_uncertain_send_does_not_mark_contacted(self):
        saved = self.helper(
            "run-1",
            {
                "status": "SENT_TRACKING_FAILED",
                "gmail_message_id": "gmail-message-123",
            },
        )

        self.assertFalse(saved)
        self.tracker.get_outreach.assert_not_called()
        self.store.mark_contacted.assert_not_called()

    def test_missing_gmail_message_id_does_not_mark_contacted(self):
        saved = self.helper("run-1", {"status": "SENT"})

        self.assertFalse(saved)
        self.tracker.get_outreach.assert_not_called()
        self.store.mark_contacted.assert_not_called()

    def test_database_update_failure_does_not_report_success(self):
        self.store.mark_contacted.return_value = False

        saved = self.helper(
            "run-1",
            {"status": "SENT", "gmail_message_id": "gmail-message-123"},
        )

        self.assertFalse(saved)
        self.store.mark_contacted.assert_called_once_with(42)
        self.store.close.assert_called_once()

    def test_database_exception_is_not_swallowed(self):
        self.store.mark_contacted.side_effect = RuntimeError(
            "Simulated database failure"
        )

        with self.assertRaisesRegex(RuntimeError, "Simulated database failure"):
            self.helper(
                "run-1",
                {"status": "SENT", "gmail_message_id": "gmail-message-123"},
            )

        self.store.close.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
