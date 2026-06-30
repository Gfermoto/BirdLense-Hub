"""Tests for scripts/benchmark_video_decode_resize.py (#373)."""

import importlib.util
import json
import sys
from pathlib import Path
import unittest

_REPO_ROOT = next(
    (p for p in (Path(__file__).resolve().parents[3], Path('/workspace')) if (p / 'scripts').exists()),
    Path(__file__).resolve().parents[3],
)


def _load_module():
    path = _REPO_ROOT / "scripts" / "benchmark_video_decode_resize.py"
    spec = importlib.util.spec_from_file_location(
        "benchmark_video_decode_resize",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["benchmark_video_decode_resize"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestBenchmarkVideoDecodeResize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_json_summary_includes_backend(self):
        data = json.loads(self.mod.json_summary("opencv", 10, 1.0, 10.0, 100.0, 640, 640))
        self.assertEqual(data["schema"], "video_decode_resize_benchmark@v1")
        self.assertEqual(data["backend"], "opencv")
        self.assertEqual(data["resize"], [640, 640])
        self.assertIn("cpu_process_pct", data)
        self.assertIn("p95_frame_delay_ms", data)
        self.assertIn("drop_rate", data)
        self.assertIn("platform", data)

    def test_ffmpeg_nvmpi_cmd_shape(self):
        from sources.go2rtc_stream_source import NVMPI_GST_TEMPLATE

        pipeline = NVMPI_GST_TEMPLATE.format(url="rtsp://x", w=640, h=640)
        self.assertIn("nvv4l2decoder", pipeline)
        self.assertIn("nvvidconv", pipeline)
        self.assertIn("width=640,height=640", pipeline)

    def test_drop_rate(self):
        self.assertEqual(self.mod._drop_rate(decoded_frames=90, requested_frames=100), 0.1)
        self.assertEqual(self.mod._drop_rate(decoded_frames=100, requested_frames=100), 0.0)


if __name__ == "__main__":
    unittest.main()
