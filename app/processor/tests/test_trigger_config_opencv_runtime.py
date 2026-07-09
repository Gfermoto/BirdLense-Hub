"""Runtime config plumbing for triggers.opencv."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.insert(0, app_path)

from app_config.trigger_config import (  # noqa: E402
    build_opencv_trigger_runtime_config,
    get_effective_trigger_config,
)


class TestOpenCVTriggerRuntimeConfig(unittest.TestCase):
    def test_build_opencv_passes_advanced_keys(self):
        cfg = {
            "triggers": {
                "opencv": {
                    "enabled": True,
                    "detection_method": "hybrid",
                    "suppress_warmup_frames": 45,
                    "auto_profile_enabled": True,
                    "night_diff_threshold": 16,
                    "motion_max_side_px": 480,
                    "check_interval_seconds": 0.15,
                }
            }
        }
        out = build_opencv_trigger_runtime_config(cfg)
        self.assertEqual(out["detection_method"], "hybrid")
        self.assertEqual(out["suppress_warmup_frames"], 45)
        self.assertTrue(out["auto_profile_enabled"])
        self.assertEqual(out["night_diff_threshold"], 16)
        self.assertEqual(out["motion_max_side_px"], 480)
        self.assertAlmostEqual(out["check_interval_seconds"], 0.15)

    def test_get_effective_trigger_config_uses_full_opencv(self):
        cfg = {
            "triggers": {
                "opencv": {
                    "enabled": True,
                    "detection_method": "mog2",
                    "min_contour_area": 400,
                },
                "frigate": {"enabled": False},
            }
        }
        eff = get_effective_trigger_config(cfg)
        op = eff["opencv"]
        self.assertEqual(op["detection_method"], "mog2")
        self.assertEqual(op["min_contour_area"], 400)
        self.assertIn("smart_trigger_enabled", op)

    def test_get_effective_trigger_config_frigate_trigger_on_update(self):
        cfg = {
            "triggers": {
                "opencv": {"enabled": True},
                "frigate": {"enabled": True, "trigger_on_update": True},
            }
        }
        eff = get_effective_trigger_config(cfg)
        self.assertTrue(eff["frigate"]["trigger_on_update"])

        cfg["triggers"]["frigate"]["trigger_on_update"] = False
        eff2 = get_effective_trigger_config(cfg)
        self.assertFalse(eff2["frigate"]["trigger_on_update"])

    def test_get_effective_trigger_config_motion_sensor_pir_pin(self):
        cfg = {
            "triggers": {
                "opencv": {"enabled": True},
                "motion_sensor": {"enabled": True, "source": "pir", "pir_pin": 17},
            }
        }
        eff = get_effective_trigger_config(cfg)
        self.assertEqual(eff["motion_sensor"]["pir_pin"], 17)


if __name__ == "__main__":
    unittest.main()
