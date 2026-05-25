"""Per-camera OpenCV mask resolution."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from motion_detectors.opencv_camera_masks import (  # noqa: E402
    resolve_opencv_mask_specs,
)


class TestOpenCvCameraMasks(unittest.TestCase):
    def test_per_camera_only(self):
        cameras = [
            {"id": "BirdBox", "opencv_masks": ["0,0,1,0,1,0.1,0,0.1"]},
            {"id": "Forest", "opencv_masks": ["0.2,0.2,0.8,0.2,0.8,0.9,0.2,0.9"]},
        ]
        bird = resolve_opencv_mask_specs(
            camera_id="BirdBox",
            cameras_config=cameras,
        )
        forest = resolve_opencv_mask_specs(
            camera_id="Forest",
            cameras_config=cameras,
        )
        self.assertEqual(bird, ["0,0,1,0,1,0.1,0,0.1"])
        self.assertEqual(forest[0], "0.2,0.2,0.8,0.2,0.8,0.9,0.2,0.9")

    def test_no_global_fallback(self):
        cameras = [{"id": "BirdBox"}]
        out = resolve_opencv_mask_specs(
            camera_id="BirdBox",
            cameras_config=cameras,
        )
        self.assertEqual(out, [])

    def test_unknown_camera_empty(self):
        out = resolve_opencv_mask_specs(
            camera_id="Missing",
            cameras_config=[{"id": "BirdBox", "opencv_masks": ["0,0,1,0,1,1,0,1"]}],
        )
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
