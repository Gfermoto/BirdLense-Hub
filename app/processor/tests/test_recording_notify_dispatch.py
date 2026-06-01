"""Tests for finalized recording notification dispatch."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_notify_dispatch import notify_unique_species  # noqa: E402


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class TestRecordingNotifyDispatch(unittest.TestCase):
    def test_notifies_each_species_once_with_video_link(self):
        api = MagicMock()
        detections = [
            {
                "species_name": "Robin",
                "confidence": 0.9,
                "notification_eligible": True,
            },
            {
                "species_name": "Robin",
                "confidence": 0.8,
                "notification_eligible": True,
            },
        ]

        with patch(
            "recording_notify_dispatch.write_notify_preview_activity"
        ) as write_log:
            notify_unique_species(
                api,
                _Config({"processor.min_confidence_to_notify": 0.5}),
                video_detections=detections,
                video_output="/tmp/video.mp4",
                video_id=42,
                encode_func=lambda _d, _v: ("img", "best_frame"),
            )

        api.notify_species.assert_called_once_with(
            "Robin",
            image_base64="img",
            link="videos/42",
            preview_source="best_frame",
            notification_eligible=True,
        )
        write_log.assert_called_once()

    def test_suppresses_low_confidence(self):
        api = MagicMock()
        encode = MagicMock(return_value=("img", "best_frame"))

        notify_unique_species(
            api,
            _Config({"processor.min_confidence_to_notify": 0.95}),
            video_detections=[
                {
                    "species_name": "Robin",
                    "confidence": 0.9,
                    "notification_eligible": True,
                }
            ],
            video_output="/tmp/video.mp4",
            video_id=42,
            encode_func=encode,
        )

        api.notify_species.assert_not_called()
        encode.assert_not_called()

    def test_skips_when_preview_missing(self):
        api = MagicMock()

        notify_unique_species(
            api,
            _Config({"processor.min_confidence_to_notify": 0.5}),
            video_detections=[
                {
                    "species_name": "Robin",
                    "confidence": 0.9,
                    "notification_eligible": True,
                }
            ],
            video_output="/tmp/video.mp4",
            video_id=None,
            encode_func=lambda _d, _v: (None, "missing"),
        )

        api.notify_species.assert_not_called()


if __name__ == "__main__":
    unittest.main()
