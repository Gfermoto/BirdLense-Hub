import os
import sys
import unittest
from unittest.mock import patch

import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.insert(0, src_path)

from threshold_resolution import (  # noqa: E402
    build_camera_processor_overrides,
    merge_adaptive_profile_overrides,
    resolve_effective_threshold,
)


def _default_feeder_role(role: str) -> dict:
    path = os.path.join(project_root, "app", "app_config", "default_config.yaml")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return (cfg.get("processor") or {}).get("camera_tuning_by_role", {}).get(role) or {}


class TestMergeAdaptiveProfileOverrides(unittest.TestCase):
    def test_night_cannot_raise_role_bird_threshold(self):
        out = merge_adaptive_profile_overrides(
            {"min_confidence_binary_bird": 0.06},
            {"min_confidence_binary_bird": 0.28, "min_box_size_px": 14},
        )
        self.assertAlmostEqual(out["min_confidence_binary_bird"], 0.06)
        self.assertEqual(out["min_box_size_px"], 14)

    def test_camera_wins_non_acceptance_over_adaptive(self):
        out = merge_adaptive_profile_overrides(
            {"min_box_size_px": 8},
            {"min_box_size_px": 14},
        )
        self.assertEqual(out["min_box_size_px"], 8)


class TestResolveEffectiveThreshold(unittest.TestCase):
    @patch("threshold_resolution.resolve_camera_tuning_role")
    def test_role_beats_global(self, mock_role):
        mock_role.return_value = "feeder_far"
        cfg = {
            "processor.min_confidence_binary_bird": 0.12,
            "processor.camera_tuning_by_role.feeder_far": {"min_confidence_binary_bird": 0.05},
        }
        self.assertAlmostEqual(
            resolve_effective_threshold(cfg, "min_confidence_binary_bird", camera_id="Forest"),
            0.05,
        )

    @patch("threshold_resolution.resolve_camera_tuning_role")
    def test_openvino_cap_does_not_raise_role(self, mock_role):
        mock_role.return_value = "feeder_close"
        cfg = {
            "processor.min_confidence_binary_bird": 0.12,
            "processor.openvino_min_confidence_binary_bird": 0.12,
            "processor.camera_tuning_by_role.feeder_close": {
                "min_confidence_binary_bird": 0.06,
                "openvino_min_confidence_binary_bird": 0.06,
            },
        }
        self.assertAlmostEqual(
            resolve_effective_threshold(
                cfg,
                "min_confidence_binary_bird",
                camera_id="BirdBox",
                inference_backend="openvino",
            ),
            0.06,
        )

    @patch("threshold_resolution.resolve_camera_tuning_role")
    def test_adaptive_min_with_role(self, mock_role):
        mock_role.return_value = "feeder_far"
        cfg = {
            "processor.min_confidence_binary_bird": 0.12,
            "processor.camera_tuning_by_role.feeder_far": {"min_confidence_binary_bird": 0.08},
        }
        self.assertAlmostEqual(
            resolve_effective_threshold(
                cfg,
                "min_confidence_binary_bird",
                camera_id="Forest",
                adaptive_overrides={"min_confidence_binary_bird": 0.28},
            ),
            0.08,
        )


class TestFeederCloseDefaults(unittest.TestCase):
    def test_feeder_close_has_openvino_keys(self):
        role = _default_feeder_role("feeder_close")
        self.assertIn("openvino_min_confidence_binary_bird", role)
        self.assertLessEqual(float(role["openvino_min_confidence_binary_bird"]), 0.08)

    def test_feeder_roles_have_scoring_floors(self):
        close = _default_feeder_role("feeder_close")
        far = _default_feeder_role("feeder_far")
        self.assertLessEqual(float(close["scoring_default_low_threshold"]), 0.16)
        self.assertLessEqual(float(far["scoring_default_low_threshold"]), 0.12)


class TestFeederRoleEffectiveAfterConfigMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app_config.app_config import AppConfig, app_config

        default = yaml.safe_load(
            open(app_config.default_config_file, encoding="utf-8")
        ) or {}
        merged = AppConfig.merge_dicts(default, {})
        AppConfig._enforce_confidence_floors(merged)
        cls.merged_cfg = merged

    @staticmethod
    def _dotted_get(root: dict, key: str, default=None):
        val = root
        for part in key.split("."):
            if not isinstance(val, dict):
                return default
            val = val.get(part, default)
            if val is None:
                return default
        return val

    @patch("threshold_resolution.resolve_camera_tuning_role")
    def test_feeder_close_min_confidence_to_process(self, mock_role):
        mock_role.return_value = "feeder_close"
        root = self.merged_cfg

        class AppCfg:
            def get(self, key, default=None):
                return TestFeederRoleEffectiveAfterConfigMerge._dotted_get(root, key, default)

        self.assertAlmostEqual(
            resolve_effective_threshold(
                AppCfg(),
                "min_confidence_to_process",
                camera_id="BirdBox",
            ),
            0.08,
        )

    @patch("threshold_resolution.resolve_camera_tuning_role")
    def test_feeder_far_min_confidence_to_process(self, mock_role):
        mock_role.return_value = "feeder_far"
        root = self.merged_cfg

        class AppCfg:
            def get(self, key, default=None):
                return TestFeederRoleEffectiveAfterConfigMerge._dotted_get(root, key, default)

        self.assertAlmostEqual(
            resolve_effective_threshold(
                AppCfg(),
                "min_confidence_to_process",
                camera_id="Forest",
            ),
            0.06,
        )


class TestBuildCameraProcessorOverrides(unittest.TestCase):
    @patch("app_config.cameras.get_valid_cameras")
    def test_birdbox_gets_feeder_close(self, mock_cameras):
        mock_cameras.return_value = [{"id": "BirdBox", "tuning_role": "feeder_close"}]

        class AppCfg:
            def get(self, key, default=None):
                if key == "video":
                    return {}
                if key == "processor.camera_tuning_by_role.feeder_close":
                    return {"min_confidence_binary_bird": 0.06}
                return default

        out = build_camera_processor_overrides(AppCfg(), "BirdBox")
        self.assertAlmostEqual(out.get("min_confidence_binary_bird"), 0.06)


if __name__ == "__main__":
    unittest.main()
