"""Tests for recording dataset crop export helpers."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_dataset_crops import maybe_save_dataset_crops  # noqa: E402


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class TestRecordingDatasetCrops(unittest.TestCase):
    def test_skips_without_video_id(self):
        with patch("recording_dataset_crops._save_dataset_crops") as save:
            maybe_save_dataset_crops(
                _Config({"processor.save_dataset_crops": True}),
                video_id=None,
                video_detections=[{"species_name": "Robin"}],
                data_dir="/tmp/data",
                video_output="/tmp/video.mp4",
            )
        save.assert_not_called()

    def test_calls_dataset_saver_with_configured_threshold(self):
        detections = [{"species_name": "Robin"}]
        with patch("recording_dataset_crops._save_dataset_crops") as save:
            maybe_save_dataset_crops(
                _Config(
                    {
                        "processor.save_dataset_crops": True,
                        "processor.dataset_min_confidence": "0.7",
                    }
                ),
                video_id=12,
                video_detections=detections,
                data_dir="/tmp/data",
                video_output="/tmp/video.mp4",
            )
        save.assert_called_once_with(
            detections,
            12,
            "/tmp/data",
            min_confidence=0.7,
            video_output_path="/tmp/video.mp4",
        )


if __name__ == "__main__":
    unittest.main()
