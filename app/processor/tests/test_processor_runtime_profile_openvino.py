"""Tests for OpenVINO runtime tuning resolver (#412)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestResolveOpenvinoTuning(unittest.TestCase):
    def test_defaults(self):
        from processor_runtime_profile import resolve_openvino_tuning

        cfg = {}
        out = resolve_openvino_tuning(cfg)
        self.assertEqual(out["profile"], "latency")
        self.assertEqual(out["num_requests"], 0)
        self.assertTrue(out["model_cache_enabled"])

    def test_overrides(self):
        from processor_runtime_profile import resolve_openvino_tuning

        cfg = {
            "processor.openvino.profile": "latency",
            "processor.openvino.num_requests": 1,
            "processor.openvino.model_cache_enabled": True,
        }
        out = resolve_openvino_tuning(
            cfg,
            profile_overrides={
                "openvino_profile": "throughput",
                "openvino_num_requests": 3,
                "openvino_model_cache_enabled": False,
            },
        )
        self.assertEqual(out["profile"], "throughput")
        self.assertEqual(out["num_requests"], 3)
        self.assertFalse(out["model_cache_enabled"])


if __name__ == "__main__":
    unittest.main()
