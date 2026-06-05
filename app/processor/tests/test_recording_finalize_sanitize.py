"""Finalize overlay sanitize — linear must not strip bbox frames for persist."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from recording_finalize import _sanitize_persisted_overlay_frames  # noqa: E402


def _static_pinned_frames(n: int = 12):
    return [{"t": float(i), "bbox": [0.40, 0.30, 0.48, 0.38]} for i in range(n)]


class TestRecordingFinalizeSanitize(unittest.TestCase):
    def test_linear_skips_static_pinned_frame_strip(self):
        row = {
            "source": "video",
            "detection_provider": "yolo",
            "decision_kind": "accepted_species",
            "start_time": 0.0,
            "end_time": 58.0,
            "frames": _static_pinned_frames(),
        }
        runtime = {"processor.pipeline_mode": "linear", "processor.track_static_reject_enabled": True}
        with patch("recording_finalize.app_config") as mock_cfg:
            mock_cfg.get.return_value = False
            out = _sanitize_persisted_overlay_frames([row], runtime_cfg=runtime)
        self.assertEqual(len(out[0]["frames"]), 12)
        self.assertNotIn("overlay_suppressed", out[0])

    def test_legacy_strips_static_pinned_frames(self):
        row = {
            "source": "video",
            "detection_provider": "yolo",
            "decision_kind": "accepted_species",
            "start_time": 0.0,
            "end_time": 58.0,
            "frames": _static_pinned_frames(),
        }
        runtime = {"processor.pipeline_mode": "legacy", "processor.track_static_reject_enabled": True}
        with patch("recording_finalize.app_config") as mock_cfg:
            mock_cfg.get.return_value = False
            out = _sanitize_persisted_overlay_frames([row], runtime_cfg=runtime)
        self.assertEqual(out[0]["frames"], [])
        self.assertIn("overlay_suppressed", out[0])


if __name__ == "__main__":
    unittest.main()
