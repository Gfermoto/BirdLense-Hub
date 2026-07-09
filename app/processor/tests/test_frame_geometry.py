"""Unit tests for unified frame_geometry (SOTA-06)."""

from __future__ import annotations

import unittest

import numpy as np
import pytest

from frame_geometry import (
    bbox_iou_norm,
    compute_letterbox_meta,
    letterbox_bgr_to_wh,
    letterbox_roundtrip_iou,
    live_regen_canvas_parity,
    pad_boxes,
    prepare_detector_frame,
    prepare_yolo_detector_frame,
    remap_norm_bbox_for_crop,
    unpad_boxes,
)
from processor_config_defaults import (  # noqa: E402
    BINARY_IMGSZ,
    DETECT_USE_NATIVE_RESOLUTION,
    INFERENCE_LORES_WH,
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

    def test_birdbox_main_2688x1520_from_detect_704x576(self):
        """Prod BirdBox: main 2688×1520, detect lores 704×576 (non-16:9 parity)."""
        overlay_norm = [0.3, 0.35, 0.55, 0.65]
        mapped = remap_norm_bbox_for_crop(
            overlay_norm,
            detector_shape_hw=(576, 704),
            overlay_shape_hw=(576, 704),
            crop_shape_hw=(1520, 2688),
            playback_shape_hw=(1520, 2688),
        )
        self.assertIsNotNone(mapped)
        from frame_geometry import map_norm_bbox_xyxy_between_frame_shapes

        expected = map_norm_bbox_xyxy_between_frame_shapes(
            overlay_norm,
            from_shape_hw=(576, 704),
            to_shape_hw=(1520, 2688),
        )
        self.assertEqual(mapped, expected)
        x1, y1, x2, y2 = mapped  # type: ignore[misc]
        self.assertGreater(x2, x1)
        self.assertGreater(y2, y1)
        self.assertGreaterEqual(x1, 0.0)
        self.assertLessEqual(x2, 1.0)


class TestPrepareDetectorFrame(unittest.TestCase):
    def test_yolo_detector_canvas_is_lores_not_main_native(self):
        """Main-sized frame must letterbox to inference_lores_wh before YOLO (not 1080p native)."""
        main_hw = (1080, 1920)
        main_frame = np.zeros((*main_hw, 3), dtype=np.uint8)
        cfg = {
            "processor.inference_lores_wh": list(INFERENCE_LORES_WH),
            "processor.detect_use_native_resolution": DETECT_USE_NATIVE_RESOLUTION,
            "processor.binary_imgsz": BINARY_IMGSZ,
        }
        _det, det_hw, overlay_hw = prepare_yolo_detector_frame(main_frame, cfg)
        lores_hw = (INFERENCE_LORES_WH[1], INFERENCE_LORES_WH[0])
        self.assertEqual(overlay_hw, main_hw)
        self.assertEqual(det_hw, lores_hw)
        self.assertNotEqual(det_hw, main_hw)

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


class TestDetectorGeometryOverlay(unittest.TestCase):
    def test_box_center_overlay_norm_after_square_letterbox(self):
        from frame_geometry import DetectorGeometry, box_center_overlay_norm

        geometry = DetectorGeometry(detector_shape_hw=(704, 704), overlay_shape_hw=(576, 704))
        # Active image top band: y≈80 on detector canvas (64px pad + ~16px into 576 content)
        cx, cy = box_center_overlay_norm((300, 80, 400, 160), geometry=geometry)
        self.assertGreater(cx, 0.4)
        self.assertLess(cy, 0.15)
        self.assertGreater(cy, 0.02)


if __name__ == "__main__":
    unittest.main()


@pytest.mark.parametrize(
    ("main_wh", "det_wh", "letterbox_wh", "bbox"),
    [
        ((1920, 1080), (704, 576), None, (0.3, 0.35, 0.55, 0.65)),
        ((1280, 720), (640, 480), None, (0.2, 0.25, 0.6, 0.7)),
        ((1920, 1080), (704, 576), (640, 640), (0.35, 0.35, 0.65, 0.65)),
        ((2688, 1520), (704, 576), None, (0.28, 0.32, 0.52, 0.62)),
        ((1600, 900), (800, 600), (800, 800), (0.3, 0.3, 0.7, 0.7)),
    ],
)
def test_geometry_roundtrip_iou_parametrized(main_wh, det_wh, letterbox_wh, bbox):
    """Arbitrary main×detect resolutions: letterbox roundtrip IoU ≥ 0.99."""
    from frame_geometry import (
        letterbox_roundtrip_iou,
        map_norm_bbox_xyxy_between_frame_shapes,
        prepare_detector_pipeline_frame,
        remap_norm_bbox_for_crop,
    )
    from shared.frame_shape import wh_to_hw

    main_hw = wh_to_hw(main_wh)
    det_hw = wh_to_hw(det_wh)
    overlay_frame = np.zeros((det_hw[0], det_hw[1], 3), dtype=np.uint8)

    if letterbox_wh is not None:
        cfg = {
            "processor.inference_lores_wh": list(letterbox_wh),
            "processor.detect_use_native_resolution": False,
            "processor.inference_backend": "torch",
        }
        _det_frame, det_shape, overlay_shape, _meta = prepare_detector_pipeline_frame(
            overlay_frame,
            cfg,
        )
        iou = letterbox_roundtrip_iou(
            bbox,
            source_shape_hw=overlay_shape,
            letterbox_shape_hw=det_shape,
        )
        assert iou >= 0.99
        mapped = remap_norm_bbox_for_crop(
            list(bbox),
            detector_shape_hw=det_shape,
            overlay_shape_hw=overlay_shape,
            crop_shape_hw=main_hw,
            playback_shape_hw=main_hw,
        )
    else:
        mapped = remap_norm_bbox_for_crop(
            list(bbox),
            detector_shape_hw=det_hw,
            overlay_shape_hw=det_hw,
            crop_shape_hw=main_hw,
            playback_shape_hw=main_hw,
        )
        expected = map_norm_bbox_xyxy_between_frame_shapes(
            list(bbox),
            from_shape_hw=det_hw,
            to_shape_hw=main_hw,
        )
        assert mapped == expected

    assert mapped is not None
    x1, y1, x2, y2 = mapped
    assert x2 > x1 and y2 > y1
    assert 0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0
