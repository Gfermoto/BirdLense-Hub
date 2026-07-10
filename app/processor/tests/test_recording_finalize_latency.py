import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_finalize import (  # noqa: E402
    _latency_budget_breaches,
    _resolve_session_latencies,
)
from recording_finalize_parts.metrics import (  # noqa: E402
    _first_bbox_and_track_latency_seconds,
    build_persist_substage_ms,
)


class TestRecordingFinalizeLatency(unittest.TestCase):
    def test_resolve_session_latencies_prefers_wall_clock(self):
        detections = [
            {
                "source": "video",
                "start_time": 4.0,
                "frames": [{"t": 3.5, "bbox": [0.1, 0.1, 0.2, 0.2]}],
            }
        ]
        trigger_bbox, video_bbox, trigger_track, video_track = _resolve_session_latencies(
            {"trigger_to_first_bbox_wall_s": 1.25, "trigger_to_first_track_wall_s": 2.0},
            detections,
        )
        self.assertEqual(trigger_bbox, 1.25)
        self.assertEqual(video_bbox, 3.5)
        self.assertEqual(trigger_track, 2.0)
        self.assertEqual(video_track, 4.0)

    def test_resolve_session_latencies_falls_back_to_video_offsets(self):
        detections = [
            {
                "source": "video",
                "start_time": 0.8,
                "frames": [{"t": 0.9, "bbox": [0.2, 0.2, 0.4, 0.4]}],
            }
        ]
        trigger_bbox, video_bbox, trigger_track, video_track = _resolve_session_latencies(
            {},
            detections,
        )
        self.assertEqual(trigger_bbox, 0.9)
        self.assertEqual(video_bbox, 0.9)
        self.assertEqual(trigger_track, 0.8)
        self.assertEqual(video_track, 0.8)

    def test_latency_budget_breaches_warn_and_critical(self):
        breaches = _latency_budget_breaches(
            trigger_to_first_bbox_latency_s=6.0,
            finalize_duration_ms=6000.0,
            fusion_duration_ms=900.0,
            persist_duration_ms=2500.0,
        )
        by_metric = {row["metric"]: row for row in breaches}
        self.assertEqual(by_metric["trigger_to_first_bbox_latency_s"]["severity"], "warning")
        self.assertEqual(by_metric["finalize_duration_ms"]["severity"], "warning")
        self.assertNotIn("fusion_duration_ms", by_metric)
        self.assertEqual(by_metric["persist_duration_ms"]["severity"], "warning")

    def test_latency_budget_breaches_ignores_missing_values(self):
        breaches = _latency_budget_breaches(
            trigger_to_first_bbox_latency_s=None,
            finalize_duration_ms=None,
            fusion_duration_ms=None,
            persist_duration_ms=None,
        )
        self.assertEqual(breaches, [])

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

    def test_build_persist_substage_ms_groups_ingest(self):
        substage = build_persist_substage_ms(
            scales_duration_ms=12.5,
            create_video_duration_ms=95.0,
            create_video_ingest_timing_ms={
                "visit_processor_ms": 40.0,
                "commit_ms": 20.0,
            },
            dataset_crops_duration_ms=5.0,
            reid_enrich_duration_ms=150.0,
        )
        self.assertEqual(substage["scales_ms"], 12.5)
        self.assertEqual(substage["reid_enrich_ms"], 150.0)
        self.assertEqual(substage["create_video_ingest_ms"]["visit_processor_ms"], 40.0)
        self.assertNotIn("create_video_ingest_ms", build_persist_substage_ms(
            scales_duration_ms=None,
            create_video_duration_ms=None,
            create_video_ingest_timing_ms=None,
            dataset_crops_duration_ms=None,
            reid_enrich_duration_ms=None,
        ))


if __name__ == "__main__":
    unittest.main()
