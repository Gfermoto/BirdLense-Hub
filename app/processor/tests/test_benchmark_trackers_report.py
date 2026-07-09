"""Synthetic tests for scripts/benchmark_trackers_report.py (#519)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestBenchmarkTrackersReport(unittest.TestCase):
    def test_report_builds_rows_and_passes_without_gate(self):
        from benchmark_trackers_report import build_tracker_ab_report

        source = {
            "report_format": "benchmark_trackers@v1",
            "clip": "/tmp/clip.mp4",
            "frame_step": 24,
            "presets": {
                "bytetrack_birdlense": {
                    "fused_track_count": 10,
                    "yolo_frames_with_tracks": 15,
                    "yolo_frames_total": 100,
                    "wall_seconds": 4.2,
                },
                "botsort_birdlense": {
                    "fused_track_count": 9,
                    "yolo_frames_with_tracks": 14,
                    "yolo_frames_total": 100,
                    "wall_seconds": 4.5,
                },
            },
        }
        out = build_tracker_ab_report(
            trackers_report=source,
            baseline_preset="bytetrack_birdlense",
            min_recall_ratio_vs_baseline=0.0,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["metrics"]["baseline_fused_track_count"], 10)
        self.assertEqual(len(out["rows"]), 2)

    def test_report_fails_when_gate_is_enabled_and_ratio_low(self):
        from benchmark_trackers_report import build_tracker_ab_report

        source = {
            "report_format": "benchmark_trackers@v1",
            "clip": "/tmp/clip.mp4",
            "frame_step": 24,
            "presets": {
                "bytetrack_birdlense": {"fused_track_count": 10},
                "botsort_birdlense": {"fused_track_count": 7},
            },
        }
        out = build_tracker_ab_report(
            trackers_report=source,
            baseline_preset="bytetrack_birdlense",
            min_recall_ratio_vs_baseline=0.9,
        )
        self.assertFalse(out["ok"])
        self.assertIn(
            "botsort_birdlense_recall_ratio_vs_bytetrack_birdlense_ok",
            out["gates"],
        )
        self.assertFalse(
            out["gates"][
                "botsort_birdlense_recall_ratio_vs_bytetrack_birdlense_ok"
            ]
        )


if __name__ == "__main__":
    unittest.main()
