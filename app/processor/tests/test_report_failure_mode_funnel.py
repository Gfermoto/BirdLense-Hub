"""Unit tests for scripts/report_failure_mode_funnel.py."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestReportFailureModeFunnel(unittest.TestCase):
    def test_classify_failure_mode_variants(self):
        from report_failure_mode_funnel import _classify_failure_mode

        self.assertEqual(
            _classify_failure_mode(
                yolo_raw_boxes_total=0,
                yolo_frames_with_tracks=0,
                post_fusion_persisted=0,
            ),
            "detector_silent_raw0",
        )
        self.assertEqual(
            _classify_failure_mode(
                yolo_raw_boxes_total=3,
                yolo_frames_with_tracks=0,
                post_fusion_persisted=0,
            ),
            "quality_filter_collapse_raw_gt_0_tracks_0",
        )
        self.assertEqual(
            _classify_failure_mode(
                yolo_raw_boxes_total=3,
                yolo_frames_with_tracks=2,
                post_fusion_persisted=0,
            ),
            "decision_fusion_drop_tracks_gt_0_persisted_0",
        )
        self.assertEqual(
            _classify_failure_mode(
                yolo_raw_boxes_total=3,
                yolo_frames_with_tracks=2,
                post_fusion_persisted=1,
            ),
            "healthy_persisted_gt_0",
        )

    def test_build_failure_mode_funnel_counts(self):
        from report_failure_mode_funnel import build_failure_mode_funnel

        rows = [
            {
                "camera_id": "cam1",
                "camera_slot": 0,
                "yolo_raw_boxes_total": 0,
                "yolo_frames_with_tracks": 0,
                "payload_json": "{}",
            },
            {
                "camera_id": "cam1",
                "camera_slot": 0,
                "yolo_raw_boxes_total": 5,
                "yolo_frames_with_tracks": 0,
                "payload_json": "{}",
            },
            {
                "camera_id": "cam2",
                "camera_slot": 1,
                "yolo_raw_boxes_total": 5,
                "yolo_frames_with_tracks": 2,
                "payload_json": '{"post_fusion_persisted": 0}',
            },
            {
                "camera_id": "cam2",
                "camera_slot": 1,
                "yolo_raw_boxes_total": 5,
                "yolo_frames_with_tracks": 2,
                "payload_json": '{"post_fusion_persisted": 1}',
            },
        ]

        report = build_failure_mode_funnel(rows, lookback_hours=24)
        self.assertTrue(report["ok"])
        self.assertEqual(report["sessions_total"], 4)
        self.assertEqual(report["global_funnel"]["detector_silent_raw0"], 1)
        self.assertEqual(
            report["global_funnel"][
                "quality_filter_collapse_raw_gt_0_tracks_0"
            ],
            1,
        )
        self.assertEqual(
            report["global_funnel"][
                "decision_fusion_drop_tracks_gt_0_persisted_0"
            ],
            1,
        )
        self.assertEqual(report["global_funnel"]["healthy_persisted_gt_0"], 1)
        self.assertIn("cam1", report["by_camera"])
        self.assertIn("0", report["by_slot"])

    def test_build_failure_mode_funnel_decision_reason_counts(self):
        from report_failure_mode_funnel import build_failure_mode_funnel

        rows = [
            {
                "camera_id": "BirdBox",
                "camera_slot": 0,
                "yolo_raw_boxes_total": 5,
                "yolo_frames_with_tracks": 2,
                "payload_json": (
                    '{"post_fusion_persisted": 0, "trigger_graph": '
                    '{"decision_reason_counts": {"rejected_static_pinned_track": 2, '
                    '"rejected_short_track": 1}}}'
                ),
            },
        ]
        report = build_failure_mode_funnel(rows, lookback_hours=24)
        self.assertEqual(
            report["decision_reason_counts"]["rejected_static_pinned_track"], 2
        )
        self.assertEqual(
            report["decision_reason_by_camera"]["BirdBox"]["rejected_short_track"], 1
        )


if __name__ == "__main__":
    unittest.main()
