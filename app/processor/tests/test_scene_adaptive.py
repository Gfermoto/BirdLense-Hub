"""Tests for universal scene-adaptive MOG2 gate (no fixed polygons)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from scene_adaptive import SceneAdaptiveAnalyzer, SceneAdaptiveConfig  # noqa: E402


class TestSceneAdaptive(unittest.TestCase):
    def test_mog2_rejects_static_blob_after_warmup(self):
        cfg = SceneAdaptiveConfig(bg_warmup_frames=5, bg_min_foreground_ratio=0.12)
        analyzer = SceneAdaptiveAnalyzer(cfg)
        frame = np.full((120, 160, 3), 40, dtype=np.uint8)
        for _ in range(8):
            analyzer.update(frame)
        box = {"crop_coords": (20, 20, 80, 80)}
        reason = analyzer.background_reject_reason(box, frame_shape=frame.shape)
        self.assertIsNotNone(reason)
        self.assertIn("bg_sub_no_foreground", reason or "")

    def test_mog2_accepts_moving_foreground(self):
        cfg = SceneAdaptiveConfig(bg_warmup_frames=5, bg_min_foreground_ratio=0.05)
        analyzer = SceneAdaptiveAnalyzer(cfg)
        bg = np.full((120, 160, 3), 50, dtype=np.uint8)
        for _ in range(6):
            analyzer.update(bg)
        moving = bg.copy()
        cv2.rectangle(moving, (60, 40), (100, 80), (220, 220, 220), -1)
        analyzer.update(moving)
        box = {"crop_coords": (60, 40, 100, 80)}
        reason = analyzer.background_reject_reason(box, frame_shape=moving.shape)
        self.assertIsNone(reason)

    def test_adaptive_conf_boost_on_static_scene(self):
        cfg = SceneAdaptiveConfig(
            adaptive_conf_enabled=True,
            adaptive_static_boost=0.12,
            adaptive_conf_cap=0.50,
        )
        analyzer = SceneAdaptiveAnalyzer(cfg)
        f1 = np.full((64, 64, 3), 30, dtype=np.uint8)
        f2 = f1.copy()
        analyzer.update(f1)
        analyzer.update(f2)
        floor = analyzer.bird_confidence_floor(0.28)
        self.assertGreaterEqual(floor, 0.36)


if __name__ == "__main__":
    unittest.main()
