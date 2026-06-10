"""Tests for playback geometry (dual-stream main/detect parity)."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from playback_geometry import (  # noqa: E402
    enrich_detections_playback_geometry,
    remap_track_bboxes_playback_shape,
    resolve_playback_shape_hw,
)


class TestPlaybackGeometry(unittest.TestCase):
    def test_resolve_prefers_mp4_over_config(self):
        with patch(
            "playback_geometry.probe_video_file_shape_hw",
            return_value=(1080, 1920),
        ):
            shape, source = resolve_playback_shape_hw(
                config_main_size=(1280, 720),
                video_path="/tmp/video.mp4",
            )
        self.assertEqual(shape, (1080, 1920))
        self.assertEqual(source, "mp4_ffprobe")

    def test_resolve_record_stream_when_no_mp4(self):
        media = MagicMock(stream_url="rtsp://example/main")
        with patch(
            "playback_geometry.probe_record_stream_shape_hw",
            return_value=(720, 1280),
        ):
            shape, source = resolve_playback_shape_hw(
                config_main_size=(1920, 1080),
                media_source=media,
            )
        self.assertEqual(shape, (720, 1280))
        self.assertEqual(source, "record_stream_ffprobe")

    def test_remap_track_bboxes_on_shape_change(self):
        tracks = {
            1: {
                "frames": [{"t": 0.0, "bbox": [0.1, 0.2, 0.5, 0.6]}],
                "key_frames": [{"t": 0.0, "bbox": [0.1, 0.2, 0.5, 0.6], "score": 1.0}],
            }
        }
        n = remap_track_bboxes_playback_shape(
            tracks,
            from_shape_hw=(576, 704),
            to_shape_hw=(1080, 1920),
        )
        self.assertEqual(n, 2)
        bb = tracks[1]["frames"][0]["bbox"]
        self.assertAlmostEqual(bb[0], 0.1, places=2)
        self.assertGreater(bb[2], bb[0])

    def test_remap_skips_when_same_shape(self):
        tracks = {1: {"frames": [{"bbox": [0.1, 0.2, 0.5, 0.6]}]}}
        n = remap_track_bboxes_playback_shape(
            tracks,
            from_shape_hw=(1080, 1920),
            to_shape_hw=(1080, 1920),
        )
        self.assertEqual(n, 0)

    def test_enrich_detections_attaches_playback_shape(self):
        class _Strategy:
            _detector_frame_shape = (576, 704)
            _overlay_frame_shape = (576, 704)
            _playback_frame_shape_hw = (1080, 1920)

        fp = MagicMock(strategy=_Strategy())
        rows = enrich_detections_playback_geometry(
            [{"species_name": "Bird", "frames": []}],
            fp,
        )
        self.assertEqual(rows[0]["playback_shape_hw"], [1080, 1920])
        self.assertEqual(rows[0]["overlay_shape_hw"], [576, 704])


if __name__ == "__main__":
    unittest.main()
