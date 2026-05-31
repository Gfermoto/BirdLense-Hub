import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_finalize import (  # noqa: E402
    _first_bbox_and_track_latency_seconds,
)


class TestRecordingFinalizeLatency(unittest.TestCase):
    def test_latency_uses_first_valid_bbox_timestamp(self):
        detections = [
            {
                "source": "video",
                "start_time": 1.2,
                "frames": [
                    {"t": 1.1, "bbox": [0.1, 0.1, 0.2, 0.2]},
                    {"t": 1.3, "bbox": [0.1, 0.1, 0.3, 0.3]},
                ],
            },
            {
                "source": "video",
                "start_time": 0.8,
                "frames": [
                    {"t": 0.9, "bbox": [0.2, 0.2, 0.4, 0.4]},
                ],
            },
        ]
        first_bbox, first_track = _first_bbox_and_track_latency_seconds(
            detections
        )
        self.assertEqual(first_bbox, 0.9)
        self.assertEqual(first_track, 0.8)

    def test_latency_ignores_invalid_bbox_frames(self):
        detections = [
            {
                "source": "video",
                "start_time": 2.0,
                "frames": [
                    {"t": 0.4, "bbox": [0.2, 0.2, 0.2, 0.5]},
                    {"t": 0.5, "bbox": [0.2, 0.2, 0.5, 0.5]},
                ],
            },
            {
                "source": "audio",
                "start_time": 0.1,
                "frames": [
                    {"t": 0.1, "bbox": [0.1, 0.1, 0.2, 0.2]},
                ],
            },
        ]
        first_bbox, first_track = _first_bbox_and_track_latency_seconds(
            detections
        )
        self.assertEqual(first_bbox, 0.5)
        self.assertEqual(first_track, 2.0)

    def test_latency_returns_none_without_video_frames(self):
        detections = [
            {
                "source": "audio",
                "start_time": 0.0,
                "frames": [],
            }
        ]
        first_bbox, first_track = _first_bbox_and_track_latency_seconds(
            detections
        )
        self.assertIsNone(first_bbox)
        self.assertIsNone(first_track)


if __name__ == "__main__":
    unittest.main()
