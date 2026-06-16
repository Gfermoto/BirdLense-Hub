"""Defaults module stays aligned with default_config.yaml."""

from __future__ import annotations

import os
import sys
import unittest

import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.insert(0, src_path)
sys.path.insert(0, os.path.join(project_root, "app"))

from processor_config_defaults import (  # noqa: E402
    ABSORB_GENERIC_BIRD_MIN_CLASSIFIER_CONFIDENCE,
    BINARY_IMGSZ,
    DETECT_USE_NATIVE_RESOLUTION,
    INFERENCE_LORES_WH,
    AUTO_UNSTICK_MIN_BOX_SIZE_PX,
    AUTO_UNSTICK_MIN_CENTER_DIST,
    AUTO_UNSTICK_MIN_CONFIDENCE_BINARY,
    AUTO_UNSTICK_MIN_CONFIDENCE_BINARY_BIRD,
    AUTO_UNSTICK_NO_TRACK_FRAMES,
    BBOX_IOU_GATE_ACTION,
    BIRDER_EU_MIN_CONFIDENCE,
    CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE,
    MIN_CONFIDENCE_BINARY,
    MIN_CONFIDENCE_BINARY_BIRD,
    MIN_CONFIDENCE_TO_PROCESS,
    MIN_CONFIDENCE_TO_STORE,
    PIPELINE_MODE,
    TRACKER_ADAPTIVE_MAX_BUFFER,
    TRACKER_ADAPTIVE_MIN_BUFFER,
    TRACKER_REMEMBER_SECONDS,
    TRACK_TO_PREDICT_FALLBACK_ENABLED,
    ULTRA_WEAK_BOX_SALVAGE_ENABLED,
    YOLO_BLIND_MIN_FRAMES,
)


def _load_default_yaml() -> dict:
    path = os.path.join(project_root, "app", "app_config", "default_config.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class TestProcessorConfigDefaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = _load_default_yaml()
        cls.proc = cfg.get("processor") or {}
        cls.det = cfg.get("detection") or {}

    def test_pipeline_mode_linear(self):
        self.assertEqual(PIPELINE_MODE, self.proc["pipeline_mode"])

    def test_lores_yolo_defaults_match_yaml(self):
        self.assertEqual(list(INFERENCE_LORES_WH), list(self.proc["inference_lores_wh"]))
        self.assertEqual(BINARY_IMGSZ, self.proc["binary_imgsz"])
        self.assertEqual(DETECT_USE_NATIVE_RESOLUTION, self.proc["detect_use_native_resolution"])

    def test_min_confidence_to_process(self):
        self.assertEqual(MIN_CONFIDENCE_TO_PROCESS, self.proc["min_confidence_to_process"])

    def test_auto_unstick_no_track_frames_is_ten_not_one_eighty(self):
        self.assertEqual(AUTO_UNSTICK_NO_TRACK_FRAMES, self.proc["auto_unstick_no_track_frames"])
        self.assertEqual(AUTO_UNSTICK_NO_TRACK_FRAMES, 10)

    def test_auto_unstick_thresholds(self):
        self.assertEqual(AUTO_UNSTICK_MIN_CONFIDENCE_BINARY, self.proc["auto_unstick_min_confidence_binary"])
        self.assertEqual(
            AUTO_UNSTICK_MIN_CONFIDENCE_BINARY_BIRD,
            self.proc["auto_unstick_min_confidence_binary_bird"],
        )
        self.assertEqual(AUTO_UNSTICK_MIN_BOX_SIZE_PX, self.proc["auto_unstick_min_box_size_px"])
        self.assertEqual(AUTO_UNSTICK_MIN_CENTER_DIST, self.proc["auto_unstick_min_center_dist"])

    def test_binary_confidence_floors(self):
        self.assertEqual(MIN_CONFIDENCE_BINARY, self.proc["min_confidence_binary"])
        self.assertEqual(MIN_CONFIDENCE_BINARY_BIRD, self.proc["min_confidence_binary_bird"])

    def test_tracker_buffer_defaults(self):
        self.assertEqual(TRACKER_REMEMBER_SECONDS, self.proc["tracker_remember_seconds"])
        self.assertEqual(TRACKER_ADAPTIVE_MIN_BUFFER, self.proc["tracker_adaptive_min_buffer"])
        self.assertEqual(TRACKER_ADAPTIVE_MAX_BUFFER, self.proc["tracker_adaptive_max_buffer"])

    def test_classifier_thresholds(self):
        self.assertEqual(CLASSIFIER_BEST_GUESS_MIN_CONFIDENCE, self.proc["classifier_best_guess_min_confidence"])
        self.assertEqual(BIRDER_EU_MIN_CONFIDENCE, self.proc["birder_eu_min_confidence"])

    def test_salvage_fallback_off_by_default(self):
        self.assertFalse(ULTRA_WEAK_BOX_SALVAGE_ENABLED)
        self.assertEqual(TRACK_TO_PREDICT_FALLBACK_ENABLED, self.proc["track_to_predict_fallback_enabled"])
        self.assertTrue(TRACK_TO_PREDICT_FALLBACK_ENABLED)

    def test_track_spatial_split_default_on(self):
        self.assertTrue(self.proc["track_spatial_split_enabled"])
        self.assertEqual(self.proc["track_spatial_split_max_center_jump_norm"], 0.18)
        self.assertEqual(self.proc["track_spatial_split_min_segment_frames"], 2)

    def test_detection_keys(self):
        self.assertEqual(MIN_CONFIDENCE_TO_STORE, self.det["min_confidence_to_store"])
        self.assertEqual(BBOX_IOU_GATE_ACTION, self.det["bbox_iou_gate_action"])
        self.assertEqual(YOLO_BLIND_MIN_FRAMES, self.det["yolo_blind_min_frames"])
        self.assertEqual(
            ABSORB_GENERIC_BIRD_MIN_CLASSIFIER_CONFIDENCE,
            self.det["absorb_generic_bird_min_classifier_confidence"],
        )


if __name__ == "__main__":
    unittest.main()
