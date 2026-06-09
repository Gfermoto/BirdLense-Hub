"""Unit tests for unified frame_geometry (SOTA-06)."""

from __future__ import annotations

import unittest

import numpy as np

from frame_geometry import (
    bbox_iou_norm,
    compute_letterbox_meta,
    letterbox_bgr_to_wh,
    letterbox_roundtrip_iou,
    live_regen_canvas_parity,
    pad_boxes,
    prepare_detector_frame,
    remap_norm_bbox_for_crop,
    unpad_boxes,
)


class TestLetterboxMeta(unittest.TestCase):
    def test_16_9_to_640_square_meta(self):
        meta = compute_letterbox_meta((720, 1280), (640, 640))
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertAlmostEqual(meta.scale, 640 / 1280, places=4)
        self.assertGreater(meta.pad_y, 0)

    def test_roundtrip_iou_high_on_center_box(self):
        iou = letterbox_roundtrip_iou(
            (0.35, 0.35, 0.65, 0.65),
            source_shape_hw=(720, 1280),
            letterbox_shape_hw=(640, 640),
        )
        self.assertGreaterEqual(iou, 0.99)

    def test_unpad_pad_inverse(self):
        src = (480, 848)
        det = (576, 704)
        norm = (0.2, 0.3, 0.5, 0.7)
        back = pad_boxes(
            unpad_boxes(norm, source_shape_hw=src, letterbox_shape_hw=det) or (0, 0, 0, 0),
            source_shape_hw=src,
            letterbox_shape_hw=det,
        )
        self.assertIsNotNone(back)
        self.assertGreaterEqual(bbox_iou_norm(norm, back), 0.99)


class TestLiveRegenParity(unittest.TestCase):
    def test_default_config_canvas_match(self):
        cfg = {
            "processor.inference_lores_wh": [704, 576],
            "processor.detect_use_native_resolution": False,
        }
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        report = live_regen_canvas_parity(frame, cfg)
        self.assertTrue(report["canvas_wh_match"])
        self.assertTrue(report["meta_match"])


class TestRemapNormBboxForCrop(unittest.TestCase):
    def test_dual_stream_detect_to_main_scale(self):
        """Detect 704x576 overlay → main 1920x1080 crop (no letterbox on detector)."""
        bbox = [0.3, 0.35, 0.55, 0.65]
        mapped = remap_norm_bbox_for_crop(
            bbox,
            detector_shape_hw=(576, 704),
            overlay_shape_hw=(576, 704),
            crop_shape_hw=(1080, 1920),
            playback_shape_hw=(1080, 1920),
        )
        self.assertIsNotNone(mapped)
        x1, y1, x2, y2 = mapped  # type: ignore[misc]
        self.assertGreater(x2, x1)
        self.assertGreater(y2, y1)
        self.assertGreaterEqual(x1, 0.0)
        self.assertLessEqual(x2, 1.0)

    def test_pre_letterboxed_detector_to_classification(self):
        """640 square detector letterboxed from 1280x720 classification source."""
        mapped = remap_norm_bbox_for_crop(
            [0.25, 0.25, 0.75, 0.75],
            detector_shape_hw=(640, 640),
            overlay_shape_hw=(640, 640),
            crop_shape_hw=(720, 1280),
        )
        self.assertIsNotNone(mapped)
        x1, y1, x2, y2 = mapped  # type: ignore[misc]
        self.assertAlmostEqual(x1, 0.25, places=2)
        self.assertAlmostEqual(x2, 0.75, places=2)
        self.assertLess(y1, 0.2)
        self.assertGreater(y2, 0.8)

    def test_letterboxed_detect_overlay_to_main(self):
        """Detector letterbox canvas differs from detect overlay (576x704 native)."""
        overlay_norm = [0.3, 0.35, 0.55, 0.65]
        mapped = remap_norm_bbox_for_crop(
            overlay_norm,
            detector_shape_hw=(576, 704),
            overlay_shape_hw=(576, 704),
            crop_shape_hw=(1080, 1920),
            playback_shape_hw=(1080, 1920),
        )
        self.assertIsNotNone(mapped)
        from_shape = (576, 704)
        to_shape = (1080, 1920)
        from frame_geometry import map_norm_bbox_xyxy_between_frame_shapes

        expected = map_norm_bbox_xyxy_between_frame_shapes(
            overlay_norm,
            from_shape_hw=from_shape,
            to_shape_hw=to_shape,
        )
        self.assertEqual(mapped, expected)


class TestPrepareDetectorFrame(unittest.TestCase):
    def test_no_stretch_on_wide(self):
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        out = letterbox_bgr_to_wh(frame, (640, 640))
        self.assertEqual(out.shape[1], 640)
        # Letterbox adds vertical pad on wide frame.
        self.assertEqual(out.shape[0], 640)

    def test_skip_when_native_size(self):
        frame = np.zeros((576, 704, 3), dtype=np.uint8)
        out = prepare_detector_frame(frame, (704, 576))
        self.assertEqual(out.shape[0], 576)
        self.assertEqual(out.shape[1], 704)


if __name__ == "__main__":
    unittest.main()
