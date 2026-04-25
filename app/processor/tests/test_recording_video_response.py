"""Tests for recording video response helpers."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_video_response import response_video_id  # noqa: E402


class TestRecordingVideoResponse(unittest.TestCase):
    def test_response_video_id_reads_dict_only(self):
        self.assertEqual(response_video_id({"video_id": "42"}), "42")
        self.assertIsNone(response_video_id(None))
        self.assertIsNone(response_video_id(["not", "dict"]))


if __name__ == "__main__":
    unittest.main()
