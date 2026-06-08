import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from persist_mode import (  # noqa: E402
    binary_track_first_enabled,
    can_binary_track_first_accept,
    defer_static_pinned_reject,
    passes_binary_track_first_store_floor,
    persist_mode_name,
    track_has_bbox_frames,
)


class TestPersistMode(unittest.TestCase):
    def test_default_mode_is_binary_track_first(self):
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: default
        self.assertEqual(persist_mode_name(cfg), "binary_track_first")
        self.assertTrue(binary_track_first_enabled(cfg))

    def test_legacy_persist_mode_maps_to_binary_track_first(self):
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: (
            "legacy" if key == "detection.persist_mode" else default
        )
        self.assertTrue(binary_track_first_enabled(cfg))
        self.assertEqual(persist_mode_name(cfg), "binary_track_first")

    def test_track_has_bbox_frames(self):
        self.assertFalse(track_has_bbox_frames({}))
        self.assertFalse(track_has_bbox_frames({"frames": [{"bbox": [0, 0, 0, 0]}]}))
        self.assertTrue(
            track_has_bbox_frames({"frames": [{"bbox": [0.1, 0.1, 0.4, 0.4], "t": 0.0}]})
        )
        self.assertFalse(
            track_has_bbox_frames({"frames": [{"bbox": [10, 10, 40, 40], "t": 0.0}]})
        )

    def test_can_binary_track_first_accept(self):
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: (
            "binary_track_first" if key == "detection.persist_mode" else default
        )
        track = {"frames": [{"bbox": [0.1, 0.2, 0.3, 0.4]}]}
        self.assertTrue(
            can_binary_track_first_accept(
                app_config=cfg,
                detector_label="Bird",
                detector_conf=0.15,
                min_confidence_to_process=0.12,
                track=track,
            )
        )
        self.assertFalse(
            can_binary_track_first_accept(
                app_config=cfg,
                detector_label="Bird",
                detector_conf=0.08,
                min_confidence_to_process=0.12,
                track=track,
            )
        )

    def test_passes_store_floor_below_threshold_with_bbox(self):
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: {
            "detection.persist_mode": "binary_track_first",
            "processor.min_confidence_to_process": 0.12,
        }.get(key, default)
        row = {
            "detection_provider": "yolo",
            "confidence": 0.15,
            "detector_confidence": 0.15,
            "detector_label": "Bird",
            "decision_reason": "accepted_binary_track_classifier_uncertain",
            "frames": [{"bbox": [0.1, 0.2, 0.3, 0.4]}],
        }
        self.assertTrue(
            passes_binary_track_first_store_floor(
                app_config=cfg,
                row=row,
                min_conf_store=0.20,
            )
        )

    def test_defer_static_pinned_for_bird_bbox_track(self):
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: (
            "binary_track_first" if key == "detection.persist_mode" else default
        )
        track = {
            "frames": [{"bbox": [0.1, 0.1, 0.5, 0.5]}],
            "detector_events": [{"label": "Bird", "confidence": 0.15}],
        }
        self.assertTrue(
            defer_static_pinned_reject(
                app_config=cfg,
                track=track,
                detector_events=track["detector_events"],
                min_confidence_to_process=0.12,
            )
        )

    def test_defer_static_pinned_for_low_conf_bird_in_track(self):
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: (
            "binary_track_first" if key == "detection.persist_mode" else default
        )
        track = {
            "frames": [{"bbox": [0.5, 0.5, 0.6, 0.6]}],
            "detector_events": [{"label": "Bird", "confidence": 0.08}],
        }
        self.assertTrue(
            defer_static_pinned_reject(
                app_config=cfg,
                track=track,
                detector_events=track["detector_events"],
                min_confidence_to_process=0.12,
            )
        )


if __name__ == "__main__":
    unittest.main()
