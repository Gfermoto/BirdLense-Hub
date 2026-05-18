"""Tests for behavior tracklet crops and manifest alignment (#456)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ml_behavior_crop_core import extract_tracklet_crops  # noqa: E402


class TestMlBehaviorCrop(unittest.TestCase):
    def test_crop_meta_matches_manifest_fields(self):
        tracklet = {
            "tracklet_id": "t_demo",
            "video_path": None,
            "boxes": [
                {"t": 0.0, "bbox": [0.1, 0.2, 0.3, 0.35]},
                {"t": 0.1, "bbox": [0.15, 0.22, 0.35, 0.38]},
                {"t": 0.2, "bbox": [0.2, 0.24, 0.4, 0.42]},
                {"t": 0.3, "bbox": [0.25, 0.26, 0.45, 0.45]},
                {"t": 0.4, "bbox": [0.28, 0.28, 0.48, 0.48]},
            ],
            "label": "feeding",
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "crops"
            meta = extract_tracklet_crops(
                tracklet,
                crops_root=root,
                min_blur_score=0.0,
                min_span=0.0,
            )
            self.assertIsNotNone(meta)
            assert meta is not None
            crop_dir = Path(meta["crop_dir"])
            self.assertTrue(crop_dir.is_dir())
            meta_path = crop_dir / "crop_meta.json"
            self.assertTrue(meta_path.is_file())
            on_disk = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(len(on_disk["frame_paths"]), meta["quality"]["frame_count"])
            mean_npy = Path(meta["mean_rgb_npy"])
            self.assertTrue(mean_npy.is_file())
            arr = np.load(mean_npy)
            self.assertEqual(arr.shape[2], 3)
            tracklet.update(meta)
            self.assertEqual(tracklet["crop_dir"], str(crop_dir.resolve()))


if __name__ == "__main__":
    unittest.main()
