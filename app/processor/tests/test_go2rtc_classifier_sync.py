"""Classifier crop sync: detect timestamp + nearest record frame buffer."""

from __future__ import annotations

import os
import sys
import time
import unittest
from unittest.mock import patch

import numpy as np

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from detection_strategy import resolve_classifier_crop_frame  # noqa: E402
from sources.go2rtc_stream_source import (  # noqa: E402
    CLASSIFIER_RECORD_BUFFER_SIZE,
    Go2RTCStreamSource,
)


class TestResolveClassifierCropFrame(unittest.TestCase):
    def test_mismatch_flag_falls_back_to_detect_and_counts(self):
        detect = np.full((576, 704, 3), 11, dtype=np.uint8)
        record = np.full((1080, 1920, 3), 22, dtype=np.uint8)
        with patch("processor_runtime_stats.inc_counter") as inc:
            out = resolve_classifier_crop_frame(
                detect,
                record,
                profile_overrides={"_classifier_crop_source_mismatch": True},
            )
        self.assertIs(out, detect)
        inc.assert_called_once_with("classifier_crop_source_mismatch_total", 1)

    def test_record_frame_used_when_synced(self):
        detect = np.zeros((576, 704, 3), dtype=np.uint8)
        record = np.zeros((1080, 1920, 3), dtype=np.uint8)
        record[100:200, 100:200] = 99
        out = resolve_classifier_crop_frame(detect, record)
        self.assertIs(out, record)


class TestGo2RTCClassifierBuffer(unittest.TestCase):
    def _make_dual_stream(self) -> Go2RTCStreamSource:
        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src._dual_stream = True
        src._single_rtsp_read = False
        src._record_frame_buffer = __import__("collections").deque(
            maxlen=CLASSIFIER_RECORD_BUFFER_SIZE,
        )
        src._last_detect_capture_ts = None
        src._last_classifier_crop_skew_sec = 0.0
        src._last_classifier_crop_mismatch = False
        src._last_classifier_source_frame = None
        return src

    def test_select_nearest_record_frame_picks_closest_timestamp(self):
        src = self._make_dual_stream()
        f_old = np.zeros((10, 10, 3), dtype=np.uint8)
        f_new = np.ones((10, 10, 3), dtype=np.uint8)
        src._record_frame_buffer.append((1.0, f_old))
        src._record_frame_buffer.append((3.0, f_new))
        picked, skew = src._select_nearest_record_frame(2.8)
        self.assertIs(picked, f_new)
        self.assertAlmostEqual(skew, 0.2)

    def test_mismatch_when_skew_exceeds_grace(self):
        src = self._make_dual_stream()
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        src._record_frame_buffer.append((1.0, frame))
        with patch.object(src, "_classifier_record_max_skew_sec", return_value=0.1):
            picked, skew = src._select_nearest_record_frame(2.0)
        self.assertIs(picked, frame)
        self.assertGreater(skew, 0.1)
        src._last_detect_capture_ts = 2.0
        src._last_classifier_crop_skew_sec = skew
        src._last_classifier_crop_mismatch = skew > 0.1
        self.assertTrue(src.classifier_crop_source_mismatch())
        self.assertIsNone(src.get_classifier_source_frame())

    def test_get_classifier_source_frame_returns_nearest_within_grace(self):
        src = self._make_dual_stream()
        frame = np.full((8, 8, 3), 5, dtype=np.uint8)
        detect_ts = 5.0
        src._record_frame_buffer.append((detect_ts, frame))
        src._last_detect_capture_ts = detect_ts
        src._last_classifier_crop_mismatch = False
        with patch.object(src, "_classifier_record_max_skew_sec", return_value=0.35):
            self.assertIs(src.get_classifier_source_frame(detect_ts), frame)

    def test_record_cap_blocked_during_ffmpeg_recording(self):
        src = self._make_dual_stream()
        src._recording = True
        with patch("sources.go2rtc_stream_source.cv2.VideoCapture") as cap_ctor:
            self.assertFalse(src._connect_record_cap())
            cap_ctor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
