"""FinalizeTransaction rollback when ingest fails (#602)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from recording_finalize import finalize_motion_recording  # noqa: E402


class TestFinalizeTransactionRollback(unittest.TestCase):
    @patch("recording_finalize.should_keep_empty_recording", return_value=False)
    @patch("recording_finalize._is_playable_video_file", return_value=True)
    @patch("recording_finalize.get_recording_mqtt_events", return_value=[])
    @patch("recording_finalize.build_fused_video_detections")
    def test_create_video_fail_removes_session_dir(
        self,
        mock_fuse,
        _mqtt,
        _playable,
        _keep_empty,
    ):
        mock_fuse.side_effect = lambda rows, *a, **k: rows
        with tempfile.TemporaryDirectory() as session_dir:
            video_path = os.path.join(session_dir, "video.mp4")
            with open(video_path, "wb") as fh:
                fh.write(b"\x00" * 64)
            api = MagicMock()
            api.create_video.side_effect = RuntimeError("ingest down")
            dm = MagicMock()
            dm.get_decisions.return_value = [
                {
                    "accepted": True,
                    "source": "video",
                    "detection_provider": "yolo",
                    "species_name": "Bird",
                    "start_time": 0.0,
                    "end_time": 1.0,
                    "confidence": 0.5,
                    "frames": [{"t": 0.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
                    "track_id": 1,
                }
            ]
            fp = MagicMock()
            fp.tracks = {
                1: {
                    "start_time": 0.0,
                    "end_time": 1.0,
                    "frames": [{"t": 0.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
                    "detector_events": [{"label": "Bird", "confidence": 0.5}],
                }
            }
            start = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
            end = datetime(2026, 6, 9, 12, 0, 5, tzinfo=timezone.utc)
            with patch("recording_finalize.app_config") as mock_cfg:
                mock_cfg.get.side_effect = lambda key, default=None: {
                    "detection.merge_window_seconds": 5,
                    "processor.min_track_duration": 0.5,
                    "processor.min_confidence_to_process": 0.12,
                    "detection.yolo_blind_score_threshold": 0.7,
                    "detection.track_first_gate_enabled": True,
                    "processor.behavior_recognition": {},
                }.get(key, default)
                mock_cfg.config = {}
                finalize_motion_recording(
                    api,
                    MagicMock(),
                    MagicMock(),
                    fp,
                    dm,
                    start_time=start,
                    end_time=end,
                    output_path_physical=session_dir,
                    output_path_logical="data/x",
                    video_output=video_path,
                    video_path_for_api="data/x/video.mp4",
                    scales_topic_arg=None,
                    data_dir="/tmp",
                )
            self.assertFalse(os.path.isdir(session_dir))


if __name__ == "__main__":
    unittest.main()
