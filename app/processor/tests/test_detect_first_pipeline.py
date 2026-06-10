"""Detect-first recording pipeline contract tests."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

import processor_bootstrap as bootstrap_mod  # noqa: E402
from detection_fusion import build_fused_video_detections  # noqa: E402
from detect_first import build_raw_hits_detect_first_anchor  # noqa: E402
from frame_processor import FrameProcessor  # noqa: E402


def _cfg_get(key, default=None):
    values = {
        "processor.detect_first_enabled": True,
        "processor.detect_first_triggers": ["opencv", "frigate"],
        "processor.detect_first_window_seconds": 2.5,
        "processor.detect_first_max_frames": 30,
        "processor.detect_first_confirm_min_hits": 2,
        "processor.detect_first_confirm_min_track_seconds": 0.5,
        "processor.min_confidence_to_process": 0.12,
        "processor.min_confidence_binary_bird": 0.12,
        "detection.persist_mode": "binary_track_first",
        "detection.trigger_moratorium_seconds": 0,
        "processor.min_seconds_between_recordings": 0,
    }
    return values.get(key, default)


class TestFrameProcessorAnchorApi(unittest.TestCase):
    def test_confirmed_track_anchor_requires_valid_bbox_track(self):
        fp = FrameProcessor.__new__(FrameProcessor)
        fp.tracks = {
            7: {
                "start_time": 0.0,
                "end_time": 0.8,
                "detector_events": [
                    {"label": "Bird", "confidence": 0.20, "t": 0.0},
                    {"label": "Bird", "confidence": 0.22, "t": 0.4},
                ],
                "classifier_events": [],
                "frames": [
                    {"t": 0.0, "bbox": [0.1, 0.2, 0.3, 0.4]},
                    {"t": 0.4, "bbox": [0.11, 0.2, 0.31, 0.4]},
                ],
                "key_frames": [],
                "best_frame": None,
                "best_frame_score": 0.0,
            }
        }
        cfg = MagicMock()
        cfg.get.side_effect = _cfg_get

        anchor = fp.confirmed_track_anchor(
            app_config=cfg,
            min_track_duration=0.5,
            min_confidence_to_process=0.12,
        )

        self.assertIsNotNone(anchor)
        self.assertEqual(anchor["track_id"], 7)
        self.assertEqual(anchor["bbox"], [0.11, 0.2, 0.31, 0.4])
        self.assertEqual(anchor["detector_label"], "Bird")


class TestRawHitsDetectFirstAnchor(unittest.TestCase):
    def test_build_raw_hits_anchor_from_strategy_candidate(self):
        class _Strategy:
            _detector_frame_shape = (640, 640)
            _overlay_frame_shape = (576, 704)
            _playback_frame_shape_hw = (1080, 1920)

            def _playback_shape_for_storage(self):
                return self._playback_frame_shape_hw

            def get_best_raw_bird_candidate(self):
                return {
                    "track_id": 3,
                    "bbox": [0.2, 0.3, 0.4, 0.5],
                    "confidence": 0.11,
                    "detector_label": "Bird",
                }

        fp = FrameProcessor.__new__(FrameProcessor)
        fp.tracks = {}
        fp.strategy = _Strategy()
        cfg = MagicMock()
        cfg.get.side_effect = _cfg_get

        anchor = build_raw_hits_detect_first_anchor(
            frame_processor=fp,
            app_config=cfg,
            cam_overrides={"min_confidence_binary_bird": 0.06},
            hits=5,
            camera_id="BirdBox",
        )

        self.assertIsNotNone(anchor)
        self.assertEqual(anchor["track_id"], 3)
        self.assertTrue(anchor.get("detect_first_raw_hits_anchor"))
        self.assertNotEqual(anchor["bbox"], [0.2, 0.3, 0.4, 0.5])
        self.assertEqual(anchor["frames"][0]["bbox"], anchor["bbox"])
        self.assertTrue(all(0.0 <= v <= 1.0 for v in anchor["bbox"]))

    def test_raw_hits_anchor_rejected_when_playback_remap_unavailable(self):
        class _Strategy:
            def get_best_raw_bird_candidate(self):
                return {
                    "track_id": 1,
                    "bbox": [0.2, 0.3, 0.4, 0.5],
                    "confidence": 0.15,
                    "detector_label": "Bird",
                }

        fp = FrameProcessor.__new__(FrameProcessor)
        fp.tracks = {}
        fp.strategy = _Strategy()
        cfg = MagicMock()
        cfg.get.side_effect = _cfg_get

        anchor = build_raw_hits_detect_first_anchor(
            frame_processor=fp,
            app_config=cfg,
            cam_overrides={},
            hits=2,
            camera_id="Forest",
        )
        self.assertIsNone(anchor)


class TestBootstrapDetectFirst(unittest.TestCase):
    def test_opencv_trigger_without_anchor_does_not_start_recording(self):
        class _Detector:
            def __init__(self):
                self.pending = 1

            def detect(self):
                if self.pending:
                    self.pending -= 1
                    return True
                raise SystemExit("done")

            def get_triggered_by(self):
                return "opencv"

            def get_triggered_camera(self):
                return "Forest"

        class _API:
            def __init__(self):
                self.notify_calls = 0

            def notify_motion(self):
                self.notify_calls += 1

        class _Session:
            def __init__(self):
                self.motion_detector = _Detector()
                self.api = _API()
                self.run_calls = 0
                self.detect_calls = 0
                self.args = SimpleNamespace(input=None)

            def detect_until_confirmed(self, *, camera_id, trigger_source):
                self.detect_calls += 1
                return None

            def run(self, **kwargs):
                self.run_calls += 1
                return True

        ctx = SimpleNamespace(session=_Session(), file_test=None)
        with patch.object(bootstrap_mod, "check_restart_flag", return_value=None), patch.object(
            bootstrap_mod,
            "requires_detect_first_before_record",
            return_value=True,
        ), patch.object(
            bootstrap_mod.app_config,
            "get",
            side_effect=_cfg_get,
        ), patch.object(bootstrap_mod.time, "sleep", return_value=None):
            with self.assertRaises(SystemExit):
                bootstrap_mod.run_motion_loop(ctx)

        self.assertEqual(ctx.session.detect_calls, 1)
        self.assertEqual(ctx.session.run_calls, 0)
        self.assertEqual(ctx.session.api.notify_calls, 0)

    def test_opencv_trigger_with_anchor_starts_recording_from_anchor(self):
        class _Detector:
            def __init__(self):
                self.pending = 1

            def detect(self):
                if self.pending:
                    self.pending -= 1
                    return True
                raise SystemExit("done")

            def get_triggered_by(self):
                return "opencv"

            def get_triggered_camera(self):
                return "Forest"

        class _API:
            def __init__(self):
                self.notify_calls = 0

            def notify_motion(self):
                self.notify_calls += 1

        class _Session:
            def __init__(self):
                self.motion_detector = _Detector()
                self.api = _API()
                self.run_kwargs = None
                self.args = SimpleNamespace(input=None)

            def detect_until_confirmed(self, *, camera_id, trigger_source):
                return {"track_id": 7, "bbox": [0.1, 0.2, 0.3, 0.4]}

            def run(self, **kwargs):
                self.run_kwargs = dict(kwargs)
                return True

        ctx = SimpleNamespace(session=_Session(), file_test=None)
        with patch.object(bootstrap_mod, "check_restart_flag", return_value=None), patch.object(
            bootstrap_mod,
            "requires_detect_first_before_record",
            return_value=True,
        ), patch.object(
            bootstrap_mod.app_config,
            "get",
            side_effect=_cfg_get,
        ), patch.object(bootstrap_mod.time, "sleep", return_value=None):
            bootstrap_mod.run_motion_loop(ctx)

        self.assertEqual(ctx.session.api.notify_calls, 1)
        self.assertEqual(ctx.session.run_kwargs["detect_first_anchor"]["track_id"], 7)


class TestDetectFirstFusionContract(unittest.TestCase):
    def test_linear_mqtt_helper_without_yolo_bbox_does_not_create_video_row(self):
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: {
            "processor.pipeline_mode": "linear",
            "detection.frigate_standalone_when_no_yolo": True,
            "detection.frigate_standalone_when_no_accepted_species": True,
        }.get(key, default)

        start = datetime.now(timezone.utc)
        rows = build_fused_video_detections(
            [],
            [
                {
                    "source": "frigate",
                    "label": "bird",
                    "species_name": "Bird",
                    "score": 0.92,
                    "confidence": 0.92,
                    "camera": "Forest",
                    "timestamp": start.isoformat(),
                    "_frigate_has_geometry": True,
                    "frigate_bbox_norm": [0.1, 0.2, 0.3, 0.4],
                }
            ],
            start_time=start,
            end_time=start + timedelta(seconds=3),
            app_config=cfg,
            triggered_camera="Forest",
        )

        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
