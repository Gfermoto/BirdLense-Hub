"""Tests for recording session directory cleanup helpers."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_session_cleanup import remove_session_dir  # noqa: E402


class TestRecordingSessionCleanup(unittest.TestCase):
    def test_remove_session_dir_removes_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "session")
            os.makedirs(path)

            remove_session_dir(path, reason="bad")

            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
