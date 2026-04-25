"""Tests for recording notification preview activity-log helpers."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_notify_preview_log import write_notify_preview_activity  # noqa: E402


class TestRecordingNotifyPreviewLog(unittest.TestCase):
    def test_writes_notify_preview_payload(self):
        api = MagicMock()

        write_notify_preview_activity(
            api,
            species="Robin",
            video_id=42,
            preview_source="best_frame",
            image_base64="abc",
        )

        api.activity_log.assert_called_once_with(
            type="notify_preview_generated",
            data={
                "species": "Robin",
                "video_id": 42,
                "preview_source": "best_frame",
                "has_image": True,
            },
        )

    def test_ignores_empty_api(self):
        write_notify_preview_activity(
            None,
            species="Robin",
            video_id=42,
            preview_source="best_frame",
            image_base64=None,
        )


if __name__ == "__main__":
    unittest.main()
