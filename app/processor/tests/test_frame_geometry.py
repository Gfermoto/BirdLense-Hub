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
