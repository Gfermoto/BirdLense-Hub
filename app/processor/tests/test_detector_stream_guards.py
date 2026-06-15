"""Detector stream parity guards (subtype + lores resolution)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_GUARD = _REPO / "app" / "scripts" / "verify_merged_detector_config.py"
_spec = importlib.util.spec_from_file_location("verify_merged_detector_config", _GUARD)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

capture_wh_matches_inference_lores = _mod.capture_wh_matches_inference_lores
evaluate_detector_guards = _mod.evaluate_detector_guards


class TestDetectorStreamGuards(unittest.TestCase):
    def test_capture_wh_matches_inference_lores(self):
        self.assertTrue(capture_wh_matches_inference_lores((704, 576), (704, 576)))
        self.assertTrue(capture_wh_matches_inference_lores((703, 575), (704, 576)))
        self.assertFalse(capture_wh_matches_inference_lores((2688, 1520), (704, 576)))
        self.assertFalse(capture_wh_matches_inference_lores((1920, 1080), (704, 576)))

    def test_warns_dahua_detect_subtype_zero(self):
        user = {
            "video": {
                "cameras": [
                    {
                        "id": "BirdBox",
                        "detect_stream_name": (
                            "rtsp://admin:pass@192.168.1.129:554/cam/realmonitor?channel=1&subtype=0"
                        ),
                    },
                ],
            },
        }
        report = evaluate_detector_guards(default={}, user=user)
        self.assertTrue(report["warn_count"] >= 1)
        keys = {w.get("key") for w in report.get("warnings") or []}
        self.assertIn("video.cameras[].detect_stream_name", keys)

    def test_no_warn_dahua_detect_subtype_one(self):
        user = {
            "video": {
                "cameras": [
                    {
                        "id": "Forest",
                        "detect_stream_name": (
                            "rtsp://admin:pass@192.168.1.101:554/cam/realmonitor?channel=1&subtype=1"
                        ),
                    },
                ],
            },
        }
        report = evaluate_detector_guards(default={}, user=user)
        subtype_warns = [
            w
            for w in report.get("warnings") or []
            if w.get("key") == "video.cameras[].detect_stream_name"
        ]
        self.assertEqual(subtype_warns, [])


if __name__ == "__main__":
    unittest.main()
