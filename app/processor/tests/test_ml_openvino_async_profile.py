"""Synthetic tests for scripts/ml_openvino_async_profile.py (#412)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestMlOpenvinoAsyncProfile(unittest.TestCase):
    def test_build_report_picks_fastest_profile(self):
        from ml_openvino_async_profile import build_openvino_async_profile_report

        rows = [
            {
                "profile": "slow",
                "status": "ok",
                "settings": {"inference_device": "cpu"},
                "aggregates": {"runtime_seconds_mean": 4.5, "fused_track_count_sum": 10, "label_eval_recall": 0.8},
            },
            {
                "profile": "fast",
                "status": "ok",
                "settings": {"inference_device": "intel:gpu"},
                "aggregates": {"runtime_seconds_mean": 2.1, "fused_track_count_sum": 9, "label_eval_recall": 0.7},
            },
        ]
        out = build_openvino_async_profile_report(profile_rows=rows, videos=["/tmp/a.mp4"])
        self.assertTrue(out["ok"])
        self.assertEqual(out["best_profile"]["name"], "fast")

    def test_build_report_skips_failed_profiles(self):
        from ml_openvino_async_profile import build_openvino_async_profile_report

        rows = [{"profile": "broken", "status": "failed", "return_code": 1}]
        out = build_openvino_async_profile_report(profile_rows=rows, videos=["/tmp/a.mp4"])
        self.assertFalse(out["ok"])
        self.assertIsNone(out["best_profile"])


if __name__ == "__main__":
    unittest.main()
