"""Tests for recording ingest gate helpers."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_ingest_gate import log_missing_video_gate  # noqa: E402


class TestRecordingIngestGate(unittest.TestCase):
    def test_log_missing_video_gate_writes_activity_log_payload(self):
        api = MagicMock()
        log_missing_video_gate(
            api,
            detection_count=2,
            video_path_for_api="data/recordings/x/video.mp4",
            video_output="/tmp/missing.mp4",
        )

        api.activity_log.assert_called_once_with(
            type="ingest_gate",
            data={
                "reason": "video_file_missing",
                "stage": "processor_finalize",
                "video_path": "data/recordings/x/video.mp4",
                "video_output": "/tmp/missing.mp4",
                "detection_count": 2,
            },
        )

    def test_log_missing_video_gate_ignores_empty_api(self):
        log_missing_video_gate(
            None,
            detection_count=1,
            video_path_for_api="data/recordings/x/video.mp4",
            video_output="/tmp/missing.mp4",
        )


if __name__ == "__main__":
    unittest.main()
