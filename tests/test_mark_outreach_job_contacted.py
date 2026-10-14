import ast
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock


UI_PATH = Path(__file__).resolve().parents[1] / "app" / "ui.py"


def load_helper(namespace):
    tree = ast.parse(UI_PATH.read_text(encoding="utf-8"))
    helper = next(
        (
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "mark_outreach_job_contacted"
        ),
        None,
    )
    if helper is None:
        raise AssertionError("Helper not found in app/ui.py")

    module = ast.Module(body=[helper], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(UI_PATH), "exec"), namespace)


class TestMarkOutreachJobContacted(unittest.TestCase):
    def setUp(self):
        self.tracker = Mock()
        self.tracker.get_outreach.return_value = {"Job ID": "42"}

        self.store = Mock()
        self.store.mark_contacted.return_value = True
        self.store.database.connection.close = Mock()

        namespace = {
            "Any": Any,
            "OutreachTracker": Mock(return_value=self.tracker),
            "JobStore": Mock(return_value=self.store),
        }
        load_helper(namespace)
        self.helper = namespace["mark_outreach_job_contacted"]

    def test_confirmed_send_marks_correct_job(self):
        result = self.helper(
            "run-1",
            {"status": "SENT", "gmail_message_id": "gmail-123"},
        )
        self.assertTrue(result)
        self.store.mark_contacted.assert_called_once_with(42)
        self.store.database.connection.close.assert_called_once()

    def test_send_failure_does_not_mark_contacted(self):
        result = self.helper(
            "run-1",
            {"status": "SEND_FAILED"},
        )
        self.assertFalse(result)
        self.store.mark_contacted.assert_not_called()

    def test_uncertain_send_does_not_mark_contacted(self):
        result = self.helper(
            "run-1",
            {
                "status": "SENT_TRACKING_FAILED",
                "gmail_message_id": "gmail-123",
            },
        )
        self.assertFalse(result)
        self.store.mark_contacted.assert_not_called()

    def test_missing_message_id_does_not_mark_contacted(self):
        result = self.helper("run-1", {"status": "SENT"})
        self.assertFalse(result)
        self.store.mark_contacted.assert_not_called()

    def test_database_update_failure_returns_false(self):
        self.store.mark_contacted.return_value = False
        result = self.helper(
            "run-1",
            {"status": "SENT", "gmail_message_id": "gmail-123"},
        )
        self.assertFalse(result)
        self.store.database.connection.close.assert_called_once()

    def test_database_exception_propagates_and_closes_connection(self):
        self.store.mark_contacted.side_effect = RuntimeError("database failure")
        with self.assertRaisesRegex(RuntimeError, "database failure"):
            self.helper(
                "run-1",
                {"status": "SENT", "gmail_message_id": "gmail-123"},
            )
        self.store.database.connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
