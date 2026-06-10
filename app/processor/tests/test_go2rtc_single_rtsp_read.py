"""Single RTSP read path: main once per cycle, software lores for detect."""

from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest.mock import patch

import numpy as np

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from sources.go2rtc_stream_source import Go2RTCStreamSource  # noqa: E402


def _minimal_single_read_src(**overrides) -> Go2RTCStreamSource:
    src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
    src._single_rtsp_read = True
    src._dual_stream = True
    src.stream_url = "rtsp://example/main"
    src._capture_stream_url = "rtsp://example/detect"
    src.lores_size = (704, 576)
    src._detect_native = False
    src._read_lock = threading.Lock()
    src._frame_count = 0
    src._last_frame_time = 0
    src._capture_backend_used = "opencv"
    src._ffmpeg_capture_failures = 0
    src._force_opencv_until_ts = 0.0
    src._last_detect_capture_ts = None
    src._last_classifier_crop_skew_sec = 0.0
    src._last_classifier_crop_mismatch = False
    src._last_classifier_source_frame = None
    src._record_frame_buffer = __import__("collections").deque(maxlen=8)
    src._recording = False
    src._record_cap = None
    for key, val in overrides.items():
        setattr(src, key, val)
    return src


class TestDeriveDetectFrame(unittest.TestCase):
    def test_letterboxes_main_to_lores_wh(self):
        src = _minimal_single_read_src()
        main = np.zeros((1080, 1920, 3), dtype=np.uint8)
        out = src._derive_detect_frame(main)
        self.assertEqual(out.shape[0], 576)
        self.assertEqual(out.shape[1], 704)

    def test_native_lores_returns_main_unchanged(self):
        src = _minimal_single_read_src(lores_size=None, _detect_native=True)
        main = np.zeros((1080, 1920, 3), dtype=np.uint8)
        out = src._derive_detect_frame(main)
        self.assertEqual(out.shape, main.shape)


class TestSingleReadCapture(unittest.TestCase):
    def test_capture_reads_once_and_splits_main_vs_detect(self):
        src = _minimal_single_read_src()
        main = np.full((1080, 1920, 3), 42, dtype=np.uint8)
        src._read_frame = lambda: (main, True)
        src._reconnect_if_needed = lambda: False
        src._update_streaming_output = lambda _f: None
        record_reads = {"n": 0}

        def _forbidden_record_read():
            record_reads["n"] += 1
            return None

        src._read_record_classifier_frame = _forbidden_record_read

        detect = src.capture()
        self.assertEqual(record_reads["n"], 0)
        self.assertIsNotNone(detect)
        assert detect is not None
        self.assertEqual(detect.shape[:2], (576, 704))
        self.assertIs(src._last_classifier_source_frame, main)
        self.assertFalse(src.classifier_crop_source_mismatch())
        self.assertIs(src.get_classifier_source_frame(), main)

    def test_live_capture_url_uses_main_stream(self):
        src = _minimal_single_read_src()
        self.assertEqual(src._live_capture_url(), "rtsp://example/main")

    def test_legacy_dual_read_keeps_detect_url(self):
        src = _minimal_single_read_src(_single_rtsp_read=False)
        self.assertEqual(src._live_capture_url(), "rtsp://example/detect")


class TestRecordingRtspFallback(unittest.TestCase):
    def test_live_capture_url_switches_to_detect_while_recording(self):
        src = _minimal_single_read_src()
        src._recording = False
        self.assertEqual(src._live_capture_url(), "rtsp://example/main")
        src._recording = True
        self.assertEqual(src._live_capture_url(), "rtsp://example/detect")

    def test_capture_uses_dual_stream_path_during_recording(self):
        src = _minimal_single_read_src()
        detect = np.full((576, 704, 3), 11, dtype=np.uint8)
        record = np.full((1080, 1920, 3), 22, dtype=np.uint8)
        src._recording = True
        src._read_frame = lambda: (detect, True)
        src._reconnect_if_needed = lambda: False
        src._update_streaming_output = lambda _f: None
        src._read_record_classifier_frame = lambda: record
        src._classifier_record_max_skew_sec = lambda: 0.35

        out = src.capture()
        self.assertIs(out, detect)
        self.assertIsNotNone(src._last_classifier_source_frame)
        self.assertFalse(src.classifier_crop_source_mismatch())

    def test_record_cap_allowed_during_recording_only(self):
        src = _minimal_single_read_src()
        src._recording = False
        self.assertFalse(src._connect_record_cap())
        src._recording = True
        with patch("sources.go2rtc_stream_source.cv2.VideoCapture") as cap_ctor:
            cap = cap_ctor.return_value
            cap.isOpened.return_value = True
            self.assertTrue(src._connect_record_cap())


class TestSingleReadGeometryParity(unittest.TestCase):
    def test_dual_stream_remap_still_applies_with_derived_detect(self):
        from frame_geometry import remap_norm_bbox_for_crop

        src = _minimal_single_read_src()
        main = np.zeros((1080, 1920, 3), dtype=np.uint8)
        detect = src._derive_detect_frame(main)
        bbox = [0.3, 0.35, 0.55, 0.65]
        mapped = remap_norm_bbox_for_crop(
            bbox,
            detector_shape_hw=detect.shape[:2],
            overlay_shape_hw=detect.shape[:2],
            crop_shape_hw=main.shape[:2],
            playback_shape_hw=main.shape[:2],
        )
        self.assertIsNotNone(mapped)
        x1, y1, x2, y2 = mapped  # type: ignore[misc]
        self.assertGreater(x2, x1)
        self.assertGreater(y2, y1)


if __name__ == "__main__":
    unittest.main()
