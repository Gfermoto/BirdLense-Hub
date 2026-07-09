"""Unit tests for detect_first module."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from detect_first import (  # noqa: E402
    build_frigate_assisted_detect_first_anchor,
    build_persist_row_from_anchor,
    detect_first_runtime_signal_fields,
    enrich_detect_first_anchor,
    is_valid_detect_first_anchor,
    restore_detect_first_persist_rows,
    sanitize_anchor_for_context,
)


class TestDetectFirst(unittest.TestCase):
    def test_runtime_signals_empty_when_no_anchor(self):
        fields = detect_first_runtime_signal_fields(None)
        self.assertFalse(fields["detect_first_confirmed"])
        self.assertIsNone(fields["detect_first_anchor_track_id"])

    def test_runtime_signals_from_valid_anchor(self):
        anchor = enrich_detect_first_anchor(
            {"track_id": 3, "bbox": [0.1, 0.2, 0.3, 0.4], "confidence": 0.55},
            detect_first_frames=12,
            detect_first_hits=4,
            trigger_source="opencv",
            camera_id="Forest",
        )
        fields = detect_first_runtime_signal_fields(anchor)
        self.assertTrue(fields["detect_first_confirmed"])
        self.assertEqual(fields["detect_first_anchor_track_id"], 3)
        self.assertEqual(fields["detect_first_window_frames"], 12)
        self.assertEqual(fields["detect_first_window_hits"], 4)

    def test_frigate_assist_accepts_grouped_camera(self):
        class Cfg:
            def get(self, key, default=None):
                data = {
                    "processor.detect_first_frigate_assist_enabled": True,
                    "processor.detect_first_frigate_assist_min_confidence": 0.5,
                    "processor.multi_camera_groups": [["BirdBox", "Forest"]],
                }
                return data.get(key, default)

        class Detector:
            def get_last_frigate_event(self):
                return {
                    "camera": "Forest",
                    "confidence": 0.88,
                    "_frigate_has_geometry": True,
                    "label": "bird",
                }

        from unittest.mock import patch

        with patch(
            "frigate_live_track.get_frigate_live_bbox",
            return_value=[0.1, 0.2, 0.3, 0.4],
        ):
            anchor = build_frigate_assisted_detect_first_anchor(
                app_config=Cfg(),
                camera_id="BirdBox",
                motion_detector=Detector(),
                trigger_source="frigate",
            )

        self.assertIsNotNone(anchor)
        self.assertTrue(anchor["detect_first_frigate_assisted_grouped"])
        self.assertEqual(anchor["detect_first_frigate_assisted_source_camera"], "Forest")

    def test_anchor_rejects_degenerate_bbox(self):
        self.assertFalse(
            is_valid_detect_first_anchor({"track_id": 1, "bbox": [0.3, 0.3, 0.2, 0.4]})
        )

    def test_sanitize_anchor_strips_non_json_frames(self):
        snap = sanitize_anchor_for_context(
            {
                "track_id": 5,
                "bbox": [0.1, 0.2, 0.35, 0.45],
                "confidence": 0.4,
                "frames": [{"t": 0.2, "bbox": [0.1, 0.2, 0.35, 0.45]}],
            }
        )
        self.assertIsNotNone(snap)
        self.assertEqual(len(snap["frames"]), 1)

    def test_build_persist_row_from_anchor(self):
        row = build_persist_row_from_anchor(
            {
                "track_id": 9,
                "bbox": [0.1, 0.2, 0.3, 0.4],
                "confidence": 0.33,
                "frames": [{"t": 0.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
            },
            video_duration_s=4.0,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["track_id"], 9)
        self.assertEqual(len(row["frames"]), 1)
        self.assertTrue(row.get("visit_eligible"))

    def test_anchor_only_does_not_persist_by_default(self):
        ctx = {
            "runtime_signals": {"detect_first_confirmed": True, "detect_first_anchor_track_id": 9},
            "detect_first_anchor": {
                "track_id": 9,
                "bbox": [0.1, 0.2, 0.3, 0.4],
                "confidence": 0.33,
                "detector_label": "Bird",
                "frames": [{"t": 0.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
            },
        }
        rows, restored = restore_detect_first_persist_rows(
            [],
            recording_context=ctx,
            accepted_pre_fusion=[],
            frame_processor_tracks={},
            video_duration_s=3.0,
        )
        self.assertFalse(restored)
        self.assertEqual(rows, [])

    def test_restore_skips_when_accepted_ingestible_rows_exist(self):
        good = {
            "source": "video",
            "detection_provider": "yolo",
            "accepted": True,
            "visit_eligible": True,
            "decision_kind": "accepted_species",
            "frames": [{"t": 0.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
        }
        rows, restored = restore_detect_first_persist_rows(
            [good],
            recording_context={"runtime_signals": {"detect_first_confirmed": True}},
            accepted_pre_fusion=[],
            frame_processor_tracks={},
            video_duration_s=3.0,
        )
        self.assertFalse(restored)
        self.assertEqual(rows, [good])

    def test_restore_from_live_track_when_anchor_missing(self):
        tracks = {
            4: {
                "start_time": 0.0,
                "end_time": 1.2,
                "detector_events": [{"label": "Bird", "confidence": 0.25}],
                "frames": [{"t": 0.1, "bbox": [0.2, 0.3, 0.4, 0.5]}],
            }
        }
        rows, restored = restore_detect_first_persist_rows(
            [{"source": "video", "detection_provider": "yolo", "track_id": 1, "frames": []}],
            recording_context={
                "runtime_signals": {
                    "detect_first_confirmed": True,
                    "detect_first_anchor_track_id": 4,
                }
            },
            accepted_pre_fusion=[],
            frame_processor_tracks=tracks,
            video_duration_s=2.0,
        )
        self.assertTrue(restored)
        self.assertEqual(rows[0]["track_id"], 4)

    def test_restore_prefers_dense_live_track_before_anchor_only(self):
        frames = [
            {"t": i * 0.2, "bbox": [0.2 + i * 0.01, 0.3, 0.4 + i * 0.01, 0.5]}
            for i in range(6)
        ]
        tracks = {
            9: {
                "start_time": 0.0,
                "end_time": 1.0,
                "detector_events": [{"label": "Bird", "confidence": 0.31}],
                "frames": frames,
            }
        }
        ctx = {
            "runtime_signals": {"detect_first_confirmed": True, "detect_first_anchor_track_id": 9},
            "detect_first_anchor": {
                "track_id": 9,
                "bbox": [0.1, 0.2, 0.3, 0.4],
                "confidence": 0.33,
                "detector_label": "Bird",
                "frames": [{"t": 0.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
            },
        }
        rows, restored = restore_detect_first_persist_rows(
            [],
            recording_context=ctx,
            accepted_pre_fusion=[],
            frame_processor_tracks=tracks,
            video_duration_s=3.0,
        )
        self.assertTrue(restored)
        self.assertEqual(rows[0]["track_id"], 9)
        self.assertEqual(len(rows[0]["frames"]), 6)


if __name__ == "__main__":
    unittest.main()
