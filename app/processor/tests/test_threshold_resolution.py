import os
import sys
import unittest
from unittest.mock import patch

import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.insert(0, src_path)
sys.path.insert(0, os.path.join(project_root, "app"))

from threshold_resolution import (  # noqa: E402
    build_camera_processor_overrides,
    merge_adaptive_profile_overrides,
    resolve_effective_threshold,
    THRESHOLD_ACCEPTANCE_KEYS,
)


def _default_feeder_role(role: str) -> dict:
    path = os.path.join(project_root, "app", "app_config", "default_config.yaml")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return (cfg.get("processor") or {}).get("camera_tuning_by_role", {}).get(role) or {}


def _load_default_config() -> dict:
    path = os.path.join(project_root, "app", "app_config", "default_config.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class TestMergeAdaptiveProfileOverrides(unittest.TestCase):
    def test_night_cannot_raise_role_bird_threshold(self):
        out = merge_adaptive_profile_overrides(
            {"min_confidence_binary_bird": 0.02},
            {"min_confidence_binary_bird": 0.28, "min_box_size_px": 14},
        )
        self.assertAlmostEqual(out["min_confidence_binary_bird"], 0.02)
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
            "processor.min_confidence_binary_bird": 0.06,
            "processor.camera_tuning_by_role.feeder_far": {"min_confidence_binary_bird": 0.03},
        }
        self.assertAlmostEqual(
            resolve_effective_threshold(cfg, "min_confidence_binary_bird", camera_id="Forest"),
            0.03,
        )

    @patch("threshold_resolution.resolve_camera_tuning_role")
    def test_adaptive_min_with_role(self, mock_role):
        mock_role.return_value = "feeder_far"
        cfg = {
            "processor.min_confidence_binary_bird": 0.06,
            "processor.camera_tuning_by_role.feeder_far": {"min_confidence_binary_bird": 0.03},
        }
        self.assertAlmostEqual(
            resolve_effective_threshold(
                cfg,
                "min_confidence_binary_bird",
                camera_id="Forest",
                adaptive_overrides={"min_confidence_binary_bird": 0.28},
            ),
            0.03,
        )


class TestFeederCloseDefaults(unittest.TestCase):
    def test_feeder_close_bird_threshold_at_most_0_02(self):
        role = _default_feeder_role("feeder_close")
        self.assertLessEqual(float(role["min_confidence_binary_bird"]), 0.02)

    def test_feeder_roles_have_scoring_floors(self):
        close = _default_feeder_role("feeder_close")
        far = _default_feeder_role("feeder_far")
        self.assertLessEqual(float(close["scoring_default_low_threshold"]), 0.12)
        self.assertLessEqual(float(far["scoring_default_low_threshold"]), 0.12)
        self.assertLessEqual(float(close["scoring_relaxed_min_confidence"]), 0.02)

    def test_feeder_roles_disable_scene_adaptive_boost(self):
        close = _default_feeder_role("feeder_close")
        far = _default_feeder_role("feeder_far")
        self.assertFalse(close.get("scene_adaptive_conf_enabled", True))
        self.assertFalse(far.get("scene_adaptive_conf_enabled", True))


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
            0.04,
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
            0.04,
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
                    return {"min_confidence_binary_bird": 0.02}
                return default

        out = build_camera_processor_overrides(AppCfg(), "BirdBox")
        self.assertAlmostEqual(out.get("min_confidence_binary_bird"), 0.02)


class TestConfigCodeDefaultsConsistency(unittest.TestCase):
    """Verify YAML defaults match code fallbacks for all threshold keys."""

    @classmethod
    def setUpClass(cls):
        cls.config = _load_default_config()
        from processor_config_defaults import (
            AUTO_UNSTICK_MIN_CONFIDENCE_BINARY,
            AUTO_UNSTICK_MIN_CONFIDENCE_BINARY_BIRD,
            MIN_CONFIDENCE_BINARY,
            MIN_CONFIDENCE_BINARY_BIRD,
            MIN_CONFIDENCE_TO_PROCESS,
            MIN_CONFIDENCE_TO_STORE,
        )

        cls.code = {
            "min_confidence_to_process": MIN_CONFIDENCE_TO_PROCESS,
            "min_confidence_binary": MIN_CONFIDENCE_BINARY,
            "min_confidence_binary_bird": MIN_CONFIDENCE_BINARY_BIRD,
            "auto_unstick_min_confidence_binary": AUTO_UNSTICK_MIN_CONFIDENCE_BINARY,
            "auto_unstick_min_confidence_binary_bird": AUTO_UNSTICK_MIN_CONFIDENCE_BINARY_BIRD,
            "min_confidence_to_store": MIN_CONFIDENCE_TO_STORE,
        }

    def test_generic_bird_min_best_frame_score_consistency(self):
        yaml_val = (self.config.get("processor") or {}).get("generic_bird_min_best_frame_score")
        code_default = 5.0
        self.assertEqual(
            yaml_val, code_default,
            f"YAML generic_bird_min_best_frame_score={yaml_val} != code default {code_default}"
        )

    def test_feeder_role_thresholds_match_config(self):
        close = _default_feeder_role("feeder_close")
        far = _default_feeder_role("feeder_far")
        self.assertAlmostEqual(float(close.get("min_confidence_binary_bird", 0.12)), 0.02)
        self.assertAlmostEqual(float(far.get("min_confidence_binary_bird", 0.12)), 0.04)

    def test_global_processor_defaults_match_code(self):
        proc = self.config.get("processor") or {}
        det = self.config.get("detection") or {}
        for key, code_val in self.code.items():
            if key == "min_confidence_to_store":
                yaml_val = det.get(key)
            else:
                yaml_val = proc.get(key)
            self.assertEqual(yaml_val, code_val, f"YAML {key}={yaml_val} != code {code_val}")

    def test_detection_frigate_standalone_off(self):
        det = self.config.get("detection") or {}
        self.assertFalse(det.get("frigate_standalone_when_no_yolo", True))

    def test_classifier_crop_source_record_hires(self):
        proc = self.config.get("processor") or {}
        self.assertEqual(proc.get("classifier_crop_source"), "record_hires")

    def test_species_confidence_override_bird(self):
        proc = self.config.get("processor") or {}
        overrides = proc.get("species_confidence_overrides") or {}
        bird = float(overrides.get("Bird"))
        self.assertAlmostEqual(bird, 0.08)
        self.assertLessEqual(bird, 0.1, "Bird override must not exceed 0.1 in default_config")

    def test_yolo_weak_track_salvage_enabled_default(self):
        det = self.config.get("detection") or {}
        self.assertTrue(det.get("yolo_weak_track_salvage_enabled", False))


if __name__ == "__main__":
    unittest.main()
