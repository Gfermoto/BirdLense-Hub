"""Single RTSP read path: main once per cycle, software lores for detect."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
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
    src.logger = logging.getLogger("test_go2rtc_single_rtsp_read")
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


class TestSingleReadDefaults(unittest.TestCase):
    def test_single_read_idle_false_when_flag_off(self):
        src = _minimal_single_read_src(_single_rtsp_read=False, _recording=False)
        self.assertFalse(src._single_read_idle())

    def test_single_read_idle_false_while_recording_even_when_flag_on(self):
        src = _minimal_single_read_src(_recording=True)
        self.assertFalse(src._single_read_idle())


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
        self.assertEqual(len(src._record_frame_buffer), 1)
        self.assertIs(src._record_frame_buffer[0][1], main)
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

    def test_record_cap_blocked_while_ffmpeg_recording(self):
        src = _minimal_single_read_src()
        src._recording = False
        self.assertFalse(src._connect_record_cap())
        src._recording = True
        with patch("sources.go2rtc_stream_source.cv2.VideoCapture") as cap_ctor:
            self.assertFalse(src._connect_record_cap())
            cap_ctor.assert_not_called()

    def test_recording_uses_buffered_main_without_record_cap(self):
        src = _minimal_single_read_src()
        main = np.full((1080, 1920, 3), 42, dtype=np.uint8)
        detect = np.full((576, 704, 3), 11, dtype=np.uint8)
        src._read_frame = lambda: (detect, True)
        src._reconnect_if_needed = lambda: False
        src._update_streaming_output = lambda _f: None
        src._classifier_record_max_skew_sec = lambda: 0.35
        src._record_frame_buffer.append((time.monotonic(), main))
        src._recording = True

        with patch("sources.go2rtc_stream_source.cv2.VideoCapture") as cap_ctor:
            out = src.capture()
            cap_ctor.assert_not_called()
        self.assertIs(out, detect)
        self.assertIs(src._last_classifier_source_frame, main)
        self.assertFalse(src.classifier_crop_source_mismatch())


class TestReconnectCaptureLock(unittest.TestCase):
    def test_reconnect_holds_read_lock_during_connect(self):
        src = _minimal_single_read_src()
        src._capture_url_connected = "rtsp://example/detect"
        src._recording = False
        src.main_size = (1920, 1080)
        lock_held: dict[str, bool] = {"during_connect": False}

        def _connect_under_lock() -> bool:
            lock_held["during_connect"] = src._read_lock.locked()
            return True

        src._connect = _connect_under_lock  # type: ignore[method-assign]
        src.refresh_record_stream_geometry = lambda: src.main_size  # type: ignore[method-assign]
        src._reconnect_capture_if_url_changed()
        self.assertTrue(lock_held["during_connect"])

    def test_capture_blocks_while_reconnect_holds_lock(self):
        src = _minimal_single_read_src()
        src._capture_url_connected = "rtsp://example/detect"
        src._recording = False
        src.main_size = (1920, 1080)
        reconnect_has_lock = threading.Event()
        release_reconnect = threading.Event()

        def _slow_connect() -> bool:
            reconnect_has_lock.set()
            release_reconnect.wait(timeout=2.0)
            return True

        src._connect = _slow_connect  # type: ignore[method-assign]
        src.refresh_record_stream_geometry = lambda: src.main_size  # type: ignore[method-assign]

        blocked = {"v": False}

        def _try_capture_read() -> None:
            blocked["v"] = not src._read_lock.acquire(blocking=False)

        t_reconnect = threading.Thread(target=src._reconnect_capture_if_url_changed)
        t_reconnect.start()
        self.assertTrue(reconnect_has_lock.wait(timeout=1.0))
        t_capture = threading.Thread(target=_try_capture_read)
        t_capture.start()
        t_capture.join(timeout=1.0)
        self.assertTrue(blocked["v"])
        release_reconnect.set()
        t_reconnect.join(timeout=1.0)
        self.assertTrue(src._read_lock.acquire(blocking=False))
        src._read_lock.release()


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
