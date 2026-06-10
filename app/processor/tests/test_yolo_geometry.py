"""Letterbox перед YOLO (без некорректного stretch)."""

import os
import sys
import unittest


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

import numpy as np

from yolo_geometry import (
    letterbox_bgr_to_wh,
    map_norm_bbox_xyxy_between_frame_shapes,
    resolve_binary_track_imgsz,
    unmap_letterbox_norm_xyxy_to_source_norm_xyxy,
)


class TestLetterboxBGR(unittest.TestCase):
    def test_output_shape_wide_frame(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        out = letterbox_bgr_to_wh(frame, (640, 640))
        self.assertEqual(out.shape, (640, 640, 3))
        self.assertTrue(out.flags["C_CONTIGUOUS"])

    def test_letterbox_differs_from_naive_resize_on_wide(self):
        rng = np.random.default_rng(0)
        frame = rng.integers(0, 256, size=(540, 960, 3), dtype=np.uint8)
        import cv2

        stretched = cv2.resize(frame, (640, 640))
        boxed = letterbox_bgr_to_wh(frame, (640, 640))
        self.assertFalse(np.array_equal(stretched, boxed))

    def test_unmap_letterbox_norm_xyxy_to_source(self):
        # 1280x720 → letterbox 640x640; bbox center square in letterbox maps to source band.
        mapped = unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
            [0.25, 0.25, 0.75, 0.75],
            source_shape=(720, 1280),
            letterbox_shape=(640, 640),
        )
        self.assertIsNotNone(mapped)
        x1, y1, x2, y2 = mapped  # type: ignore[misc]
        self.assertGreater(x2, x1)
        self.assertGreater(y2, y1)
        self.assertAlmostEqual(x1, 0.25, places=2)
        self.assertAlmostEqual(x2, 0.75, places=2)
        self.assertLess(y1, 0.2)
        self.assertGreater(y2, 0.8)

    def test_resolve_binary_track_imgsz_native_lores_torch(self):
        frame = np.zeros((576, 704, 3), dtype=np.uint8)
        cfg = {
            "processor.inference_lores_wh": [704, 576],
            "processor.binary_imgsz": 704,
            "processor.inference_backend": "torch",
        }
        self.assertEqual(resolve_binary_track_imgsz(frame, cfg), [576, 704])

    def test_resolve_binary_track_imgsz_openvino_native_lores(self):
        frame = np.zeros((576, 704, 3), dtype=np.uint8)
        cfg = {
            "processor.inference_lores_wh": [704, 576],
            "processor.binary_imgsz": 704,
            "processor.inference_backend": "openvino",
            "processor.openvino_native_lores_imgsz": True,
        }
        self.assertEqual(resolve_binary_track_imgsz(frame, cfg), [576, 704])

    def test_resolve_binary_track_imgsz_openvino_square_when_disabled(self):
        frame = np.zeros((576, 704, 3), dtype=np.uint8)
        cfg = {
            "processor.inference_lores_wh": [704, 576],
            "processor.binary_imgsz": 704,
            "processor.inference_backend": "openvino",
            "processor.openvino_native_lores_imgsz": False,
        }
        self.assertEqual(resolve_binary_track_imgsz(frame, cfg), 704)

    def test_map_norm_bbox_between_detect_and_playback_shapes(self):
        src_bbox = [0.2, 0.2, 0.5, 0.6]
        mapped = map_norm_bbox_xyxy_between_frame_shapes(
            src_bbox,
            from_shape_hw=(576, 704),
            to_shape_hw=(1080, 1920),
        )
        self.assertIsNotNone(mapped)
        x1, y1, x2, y2 = mapped  # type: ignore[misc]
        self.assertGreater(x2, x1)
        self.assertGreater(y2, y1)
        self.assertGreaterEqual(x1, 0.0)
        self.assertLessEqual(x2, 1.0)

    def test_storage_bbox_overlay_detect_to_main(self):
        from detection_strategy import _storage_bbox_norm_for_overlay

        det_bbox = [0.3, 0.35, 0.55, 0.65]
        out = _storage_bbox_norm_for_overlay(
            det_bbox,
            detector_frame_shape=(576, 704),
            overlay_frame_shape=(576, 704),
            playback_frame_shape=(1080, 1920),
        )
        self.assertEqual(len(out), 4)
        self.assertGreater(out[2], out[0])
        self.assertGreater(out[3], out[1])

    def test_crop_remap_detect_overlay_to_main(self):
        from detection_strategy import _crop_coords_from_letterboxed_bbox_norm

        coords = _crop_coords_from_letterboxed_bbox_norm(
            bbox_norm=[0.3, 0.35, 0.55, 0.65],
            detector_frame_shape=(576, 704),
            overlay_frame_shape=(576, 704),
            classification_frame_shape=(1080, 1920),
            playback_frame_shape=(1080, 1920),
        )
        self.assertIsNotNone(coords)
        x1, y1, x2, y2 = coords  # type: ignore[misc]
        self.assertGreater(x2, x1)
        self.assertGreater(y2, y1)
        self.assertGreaterEqual(x1, 0)
        self.assertLessEqual(x2, 1920)
        self.assertGreaterEqual(y1, 0)
        self.assertLessEqual(y2, 1080)

    def test_map_norm_bbox_same_shape_identity(self):
        src_bbox = [0.12, 0.23, 0.63, 0.74]
        mapped = map_norm_bbox_xyxy_between_frame_shapes(
            src_bbox,
            from_shape_hw=(720, 1280),
            to_shape_hw=(720, 1280),
        )
        self.assertEqual(tuple(src_bbox), mapped)
