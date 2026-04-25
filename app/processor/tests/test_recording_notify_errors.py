"""Tests for recording notification error helpers."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_notify_errors import notify_error_hint  # noqa: E402


class _ResponseError(Exception):
    def __init__(self, status_code):
        self.response = type("Response", (), {"status_code": status_code})()


class TestRecordingNotifyErrors(unittest.TestCase):
    def test_notify_error_hint_includes_processor_secret_for_403(self):
        self.assertEqual(
            notify_error_hint(_ResponseError(403)),
            " 403 (check PROCESSOR_SECRET in app/.env)",
        )

    def test_notify_error_hint_includes_plain_status_for_other_response(self):
        self.assertEqual(notify_error_hint(_ResponseError(500)), " 500")
        self.assertEqual(notify_error_hint(Exception("boom")), "")


if __name__ == "__main__":
    unittest.main()
