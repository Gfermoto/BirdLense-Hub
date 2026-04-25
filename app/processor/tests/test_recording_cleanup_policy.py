"""Tests for recording cleanup policy helpers."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_cleanup_policy import should_keep_empty_recording  # noqa: E402


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class TestRecordingCleanupPolicy(unittest.TestCase):
    def test_keeps_empty_recording_only_for_file_source_with_flag(self):
        self.assertTrue(
            should_keep_empty_recording(
                _Config(
                    {
                        "processor.keep_recording_when_no_detections": True,
                        "video.source": "file",
                    }
                )
            )
        )
        self.assertFalse(
            should_keep_empty_recording(
                _Config(
                    {
                        "processor.keep_recording_when_no_detections": True,
                        "video.source": "go2rtc",
                    }
                )
            )
        )
        self.assertFalse(
            should_keep_empty_recording(
                _Config(
                    {
                        "processor.keep_recording_when_no_detections": False,
                        "video.source": "file",
                    }
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
