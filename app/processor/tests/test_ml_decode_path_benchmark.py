"""Synthetic tests for scripts/ml_decode_path_benchmark.py (#413)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestMlDecodePathBenchmark(unittest.TestCase):
    def test_report_passes_when_drop_rate_improves(self):
        from ml_decode_path_benchmark import build_decode_path_benchmark_report

        opencv = {
            "status": "ok",
            "fps": 25.0,
            "drop_rate": 0.25,
            "p95_frame_delay_ms": 50.0,
        }
        ffmpeg = {
            "status": "ok",
            "fps": 30.0,
            "drop_rate": 0.10,
            "p95_frame_delay_ms": 30.0,
        }
        out = build_decode_path_benchmark_report(
            opencv_row=opencv,
            ffmpeg_row=ffmpeg,
            video="/tmp/a.mp4",
            frames=100,
            width=640,
            height=640,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["gates"]["drop_rate_improved_20pct"])

    def test_report_fails_when_ffmpeg_backend_failed(self):
        from ml_decode_path_benchmark import build_decode_path_benchmark_report

        out = build_decode_path_benchmark_report(
            opencv_row={"status": "ok", "drop_rate": 0.2, "p95_frame_delay_ms": 40.0, "fps": 20.0},
            ffmpeg_row={"status": "failed", "return_code": 1},
            video="/tmp/a.mp4",
            frames=100,
            width=640,
            height=640,
        )
        self.assertFalse(out["ok"])
        self.assertFalse(out["gates"].get("ffmpeg_vaapi_ok", True))  # Orin: NVMPI, not VA-API

    def test_zero_drop_baseline_treated_as_no_regression(self):
        from ml_decode_path_benchmark import build_decode_path_benchmark_report

        out = build_decode_path_benchmark_report(
            opencv_row={"status": "ok", "drop_rate": 0.0, "p95_frame_delay_ms": 20.0, "fps": 20.0},
            ffmpeg_row={"status": "ok", "drop_rate": 0.0, "p95_frame_delay_ms": 15.0, "fps": 25.0},
            video="/tmp/a.mp4",
            frames=100,
            width=640,
            height=640,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["gates"]["drop_rate_improved_20pct"])


if __name__ == "__main__":
    unittest.main()
