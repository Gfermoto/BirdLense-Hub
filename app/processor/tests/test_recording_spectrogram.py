"""Tests for recording spectrogram helpers."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_spectrogram import (  # noqa: E402
    maybe_generate_recording_spectrogram,
)


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class TestRecordingSpectrogram(unittest.TestCase):
    """Test recording spectrogram generation policy."""

    def test_skips_when_not_forced_and_no_birdnet_event(self):
        """Skip spectrograms unless config or BirdNET requires one."""
        with patch("recording_spectrogram.generate_spectrogram") as generate:
            path = maybe_generate_recording_spectrogram(
                _Config({"processor.generate_spectrogram_always": False}),
                mqtt_events=[],
                video_output="/tmp/video.mp4",
                output_path_physical="/tmp/session",
                output_path_logical="data/recordings/x",
            )

        self.assertIsNone(path)
        generate.assert_not_called()

    def test_returns_logical_path_when_generation_succeeds(self):
        """Return API-facing logical spectrogram path on success."""
        with patch(
            "recording_spectrogram.generate_spectrogram",
            return_value=True,
        ) as generate:
            path = maybe_generate_recording_spectrogram(
                _Config({"processor.spectrogram_px_per_sec": 300}),
                mqtt_events=[{"source": "birdnet"}],
                video_output="/tmp/video.mp4",
                output_path_physical="/tmp/session",
                output_path_logical="data/recordings/x",
            )

        self.assertEqual(path, "data/recordings/x/spectrogram_300.jpg")
        generate.assert_called_once_with(
            "/tmp/video.mp4",
            "/tmp/session/spectrogram_300.jpg",
            300,
        )


if __name__ == "__main__":
    unittest.main()
