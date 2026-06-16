import os
import sys
import unittest
from unittest.mock import patch

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from frame_processor import FrameProcessor  # noqa: E402
from tracker_paths import resolve_tracker_config_path  # noqa: E402


class _DummyStrategy:
    def __init__(self):
        self.calls = []

    def detect(
        self,
        frame,
        tracker_config,
        *,
        min_confidence,
        profile_overrides=None,
        classification_frame=None,
    ):
        self.calls.append(
            {
                "tracker_config": tracker_config,
                "min_confidence": min_confidence,
                "profile_overrides": dict(profile_overrides or {}),
            }
        )
        return []

    def reset(self):
        return None


class _FakeLightDetector:
    def __init__(self, brightness, contrast):
        self.brightness = brightness
        self.contrast = contrast

    def measure(self, frame):
        return {
            "brightness": self.brightness,
            "contrast": self.contrast,
            "has_sufficient_light": False,
        }

    def has_sufficient_light(self, frame):
        return False


class TestRuntimeProfile(unittest.TestCase):
    def test_resolve_night_profile_on_low_light(self):
        from processor_runtime_profile import resolve_runtime_profile

        class _Cfg(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        cfg = _Cfg(
            {
                "processor.adaptive_profiles.enabled": True,
                "processor.adaptive_profiles.night.max_brightness": 18,
                "processor.adaptive_profiles.night.max_contrast": 12,
                "processor.adaptive_profiles.night.overrides": {
                    "min_confidence_binary": 0.18,
                    "min_box_size_px": 32,
                },
            }
        )

        name, overrides = resolve_runtime_profile(cfg, brightness=10.0, contrast=8.0)

        self.assertEqual(name, "night")
        self.assertEqual(overrides["min_box_size_px"], 32)
        self.assertAlmostEqual(overrides["min_confidence_binary"], 0.18)

    def test_frame_processor_uses_profile_overrides_for_detection(self):
        strategy = _DummyStrategy()
        frame = np.zeros((32, 32, 3), dtype=np.uint8)

        def cfg_get(key, default=None):
            mapping = {
                "processor.light_gate_enabled": True,
                "processor.light_gate_min_brightness": 20,
                "processor.light_gate_min_contrast": 20,
                "processor.min_confidence_binary": 0.28,
                "processor.adaptive_profiles.enabled": True,
                "processor.adaptive_profiles.night.max_brightness": 18,
                "processor.adaptive_profiles.night.max_contrast": 12,
                "processor.adaptive_profiles.night.overrides": {
                    "light_gate_min_brightness": 8,
                    "light_gate_min_contrast": 6,
                    "min_confidence_binary": 0.18,
                    "min_box_size_px": 32,
                },
                "processor.tracker": "bytetrack.yaml",
                "processor.tracker_profiles": {
                    "night": "models/tracker/bytetrack_birdlense_night.yaml",
                },
            }
            return mapping.get(key, default)

        with patch("frame_processor.app_config.get", side_effect=cfg_get), patch(
            "frame_processor.resolve_adaptive_tracker_path",
            side_effect=lambda path, _fps, **kwargs: path,
        ):
            fp = FrameProcessor(strategy)
            fp.light_detector = _FakeLightDetector(brightness=10.0, contrast=8.0)

            ran = fp.run(frame, frame_time=0.0)

        self.assertFalse(ran)
        self.assertEqual(len(strategy.calls), 1)
        self.assertAlmostEqual(strategy.calls[0]["min_confidence"], 0.18)
        self.assertEqual(
            strategy.calls[0]["tracker_config"],
            resolve_tracker_config_path("models/tracker/bytetrack_birdlense_night.yaml"),
        )
        self.assertEqual(strategy.calls[0]["profile_overrides"]["min_box_size_px"], 32)
        self.assertEqual(fp.last_run_stats["runtime_profile"], "night")

    def test_runtime_overlay_resolve_strategy_field_order(self):
        from processor_runtime_profile import RuntimeProfileConfigOverlay

        class _Strat:
            min_box_size_px = 1

        app = {"processor.min_box_size_px": 64}
        o = RuntimeProfileConfigOverlay(app, {})
        self.assertEqual(
            o.resolve_strategy_field("processor.min_box_size_px", _Strat(), "min_box_size_px", 64),
            1,
        )
        o2 = RuntimeProfileConfigOverlay(app, {"min_box_size_px": 48})
        self.assertEqual(
            o2.resolve_strategy_field("processor.min_box_size_px", _Strat(), "min_box_size_px", 64),
            48,
        )


if __name__ == "__main__":
    unittest.main()
