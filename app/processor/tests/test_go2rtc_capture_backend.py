"""Go2RTC live capture backend helpers (#373) — Orin-only paths."""

import os
import sys
import threading
import time
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class _FakeStderr:
    def __init__(self, text=b""):
        self._text = text

    def read(self):
        return self._text


class TestGo2RTCCaptureBackend(unittest.TestCase):
    def test_normalize_capture_backend(self):
        from sources.go2rtc_stream_source import _normalize_capture_backend

        self.assertEqual(_normalize_capture_backend(None), "auto")
        self.assertEqual(_normalize_capture_backend("opencv"), "opencv")
        self.assertEqual(_normalize_capture_backend("ffmpeg_nvmpi"), "ffmpeg_nvmpi")
        self.assertEqual(_normalize_capture_backend("ffmpeg_vaapi"), "auto")  # not valid on Orin
        self.assertEqual(_normalize_capture_backend("broken"), "auto")

    def test_ffmpeg_record_cmd_for_jetson_uses_nvmpi_codec(self):
        from sources.go2rtc_stream_source import _ffmpeg_record_cmd

        cmd = _ffmpeg_record_cmd(
            stream_url="rtsp://example/stream",
            output="/tmp/out.mp4",
            use_jetson_hw_encode=True,
            record_stream_codec="h264",
            encoding_mode="jetson",
        )
        joined = " ".join(cmd)
        self.assertIn("+genpts+igndts", joined)
        self.assertIn("-avoid_negative_ts make_zero", joined)
        self.assertIn("-max_interleave_delta 0", joined)
        self.assertIn("-vsync 2", joined)
        self.assertIn("-map 0:v:0 -map 0:a:0?", joined)
        self.assertIn("-af aresample=async=1:first_pts=0", joined)
        self.assertIn("-c:a aac", joined)

    def test_ffmpeg_record_cmd_jetson_without_hw_uses_libx264(self):
        from sources.go2rtc_stream_source import _ffmpeg_record_cmd

        cmd = _ffmpeg_record_cmd(
            stream_url="rtsp://example/stream",
            output="/tmp/out.mp4",
            use_jetson_hw_encode=False,
            record_stream_codec="h264",
            encoding_mode="jetson",
        )
        joined = " ".join(cmd)
        self.assertIn("-c:v libx264", joined)
        self.assertNotIn("h264_nvenc", joined)
        self.assertNotIn("h264_vaapi", joined)

    def test_ffmpeg_record_cmd_for_copy_uses_copy_video(self):
        from sources.go2rtc_stream_source import _ffmpeg_record_cmd

        cmd = _ffmpeg_record_cmd(
            stream_url="rtsp://example/stream",
            output="/tmp/out.mp4",
            use_jetson_hw_encode=True,
            record_stream_codec="copy",
            encoding_mode="jetson",
        )
        joined = " ".join(cmd)
        self.assertIn("-c:v copy", joined)
        self.assertIn("-af aresample=async=1:first_pts=0", joined)

    def test_sanitize_ffmpeg_stderr_line_masks_rtsp_credentials(self):
        from sources.go2rtc_stream_source import _sanitize_ffmpeg_stderr_line

        line = "Input #0, rtsp, from 'rtsp://user:secret1@192.168.0.1:8554/cam':"
        out = _sanitize_ffmpeg_stderr_line(line)
        self.assertIn("rtsp://***:***@", out)
        self.assertNotIn("secret1", out)
        self.assertNotIn("user:", out)
        self.assertIn("192.168.0.1:8554", out)

        self.assertEqual(_sanitize_ffmpeg_stderr_line("no url here"), "no url here")
        self.assertEqual(
            _sanitize_ffmpeg_stderr_line("rtsp://nohost/path"),
            "rtsp://nohost/path",
        )

    def test_capture_reconnect_path_has_no_recursion(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def warning(self, *_args, **_kwargs):
                return None

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src._read_lock = threading.Lock()
        src._frame_count = 0
        src._last_frame_time = 0
        src._capture_backend_used = "opencv"
        src._ffmpeg_capture_failures = 0
        src._force_opencv_until_ts = 0.0
        src._soft_restart_failures_threshold = 3
        src._soft_restart_success_streak = 0
        src._soft_restart_max_success_streak = 2
        src._consecutive_read_failures = 0
        src.lores_size = (640, 640)

        calls = {"read": 0, "reconnect": 0}

        def _read_frame():
            calls["read"] += 1
            return None, False

        def _reconnect():
            calls["reconnect"] += 1
            return True

        src._read_frame = _read_frame
        src._reconnect_if_needed = _reconnect
        src._update_streaming_output = lambda _frame: None

        self.assertIsNone(src.capture())
        self.assertEqual(calls["reconnect"], 1)
        self.assertEqual(calls["read"], 2)

    def test_capture_fallback_reason_orin_only(self):
        from sources.go2rtc_stream_source import _capture_fallback_reason

        self.assertEqual(
            _capture_fallback_reason(requested_backend="opencv", encoding_mode="jetson"),
            "requested_opencv",
        )
        self.assertEqual(
            _capture_fallback_reason(
                requested_backend="ffmpeg_nvmpi",
                encoding_mode="jetson",
                nvmpi_available=False,
            ),
            "nvmpi_unavailable",
        )
        self.assertEqual(
            _capture_fallback_reason(
                requested_backend="auto",
                encoding_mode="jetson",
                nvmpi_available=False,
            ),
            "auto_nvmpi_probe_failed",
        )
        self.assertEqual(
            _capture_fallback_reason(requested_backend="auto", encoding_mode="cpu"),
            "auto_prefers_opencv_for_cpu_encoding",
        )

    def test_arm_nvdec_opencv_cooldown_sets_sticky_window(self):
        from sources import go2rtc_stream_source as mod
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def warning(self, *_args, **_kwargs):
                return None

            def info(self, *_args, **_kwargs):
                return None

        mod._NVDEC_OPENCV_COOLDOWN_UNTIL_MONO = 0.0
        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src._nvdec_opencv_cooldown_sec = 120.0
        src._force_opencv_until_ts = 0.0
        before = time.monotonic()
        src._arm_nvdec_opencv_cooldown("nvdec_open_fail")
        self.assertGreaterEqual(src._force_opencv_until_ts, before + 119.0)
        self.assertLessEqual(src._force_opencv_until_ts, before + 121.0)
        self.assertGreaterEqual(mod._NVDEC_OPENCV_COOLDOWN_UNTIL_MONO, before + 119.0)

    def test_process_wide_cooldown_applies_to_new_source_connect(self):
        from sources import go2rtc_stream_source as mod
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def warning(self, *_args, **_kwargs):
                return None

            def info(self, *_args, **_kwargs):
                return None

            def error(self, *_args, **_kwargs):
                return None

            def debug(self, *_args, **_kwargs):
                return None

        mod._NVDEC_OPENCV_COOLDOWN_UNTIL_MONO = time.monotonic() + 120.0
        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src._force_opencv_until_ts = 0.0
        src._capture_backend = "auto"
        src._encoding_mode = "jetson"
        src._source_fps = 0.0
        src._reconnect_delay = 1.0
        src._consecutive_read_failures = 0
        src._soft_restart_success_streak = 0
        src._live_capture_url = lambda: "rtsp://example/detect"
        src._disconnect = lambda: None
        src._apply_stream_probe = lambda: None
        opened = {"nvdec": 0, "opencv": 0}

        class _Cap:
            def isOpened(self):
                return True

            def get(self, _prop):
                return 7.0

            def set(self, *_a, **_k):
                return True

        def _fake_gst(_url):
            opened["nvdec"] += 1
            raise RuntimeError("should not open nvdec in cooldown")

        class _OpenCVCap(_Cap):
            pass

        import sources.go2rtc_stream_source as gmod

        real_gst_avail = gmod._gst_nvdec_capture_available
        real_gst_cls = gmod._GstRtspNvdecCapture
        real_cv2 = gmod.cv2

        class _FakeCv2:
            CAP_FFMPEG = 0
            CAP_PROP_FPS = 5
            CAP_PROP_BUFFERSIZE = 38

            @staticmethod
            def VideoCapture(*_a, **_k):
                opened["opencv"] += 1
                return _OpenCVCap()

        gmod._gst_nvdec_capture_available = lambda: True
        gmod._GstRtspNvdecCapture = _fake_gst
        gmod.cv2 = _FakeCv2
        try:
            self.assertTrue(src._connect())
        finally:
            gmod._gst_nvdec_capture_available = real_gst_avail
            gmod._GstRtspNvdecCapture = real_gst_cls
            gmod.cv2 = real_cv2
            mod._NVDEC_OPENCV_COOLDOWN_UNTIL_MONO = 0.0
        self.assertEqual(opened["nvdec"], 0)
        self.assertEqual(opened["opencv"], 1)
        self.assertEqual(src._capture_backend_used, "opencv")

    def test_reconnect_debounce_skips_same_url(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def info(self, *_args, **_kwargs):
                return None

            def warning(self, *_args, **_kwargs):
                return None

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src.auto_reconnect = True
        src._reconnect_debounce_sec = 3.0
        src._last_reconnect_attempt_ts = time.monotonic()
        src._capture_url_connected = "rtsp://example/detect"
        src._live_capture_url = lambda: "rtsp://example/detect"
        src._reconnect_delay = 0.01
        calls = {"connect": 0}

        def _connect():
            calls["connect"] += 1
            return True

        src._connect = _connect
        self.assertFalse(src._reconnect_if_needed())
        self.assertEqual(calls["connect"], 0)

    def test_capture_soft_restart_before_reconnect(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def info(self, *_args, **_kwargs):
                return None

            def warning(self, *_args, **_kwargs):
                return None

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src._read_lock = threading.Lock()
        src._frame_count = 0
        src._last_frame_time = 0
        src._capture_backend_used = "ffmpeg_nvmpi"
        src._ffmpeg_capture_failures = 0
        src._force_opencv_until_ts = 0.0
        src._soft_restart_failures_threshold = 3
        src._consecutive_read_failures = 3
        src._capture_url_connected = "rtsp://example/detect"
        src._live_capture_url = lambda: "rtsp://example/detect"
        src.lores_size = (640, 640)
        src._single_rtsp_read = False
        src._dual_stream = False
        src._recording = False
        src._update_streaming_output = lambda _frame: None
        src._last_classifier_crop_skew_sec = 0.0
        src._last_classifier_crop_mismatch = False
        src._last_classifier_source_frame = None
        src._record_frame_buffer = []

        calls = {"soft": 0, "reconnect": 0, "read": 0}

        def _read_frame():
            calls["read"] += 1
            if calls["soft"] > 0:
                return object(), True
            return None, False

        def _soft():
            calls["soft"] += 1
            src._consecutive_read_failures = 0
            return True

        def _reconnect():
            calls["reconnect"] += 1
            return False

        src._read_frame = _read_frame
        src._soft_restart_capture = _soft
        src._reconnect_if_needed = _reconnect
        src._arm_nvdec_opencv_cooldown = lambda _reason: None

        frame = src.capture()
        self.assertIsNotNone(frame)
        self.assertEqual(calls["soft"], 1)
        self.assertEqual(calls["reconnect"], 0)

    def test_soft_restart_fail_bypasses_reconnect_debounce(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def info(self, *_args, **_kwargs):
                return None

            def warning(self, *_args, **_kwargs):
                return None

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src._read_lock = threading.Lock()
        src._frame_count = 0
        src._last_frame_time = 0
        src._capture_backend_used = "ffmpeg_nvmpi"
        src._ffmpeg_capture_failures = 0
        src._force_opencv_until_ts = 0.0
        src._nvdec_opencv_cooldown_sec = 120.0
        src._soft_restart_failures_threshold = 2
        src._consecutive_read_failures = 2
        src._last_reconnect_attempt_ts = time.monotonic()
        src._capture_url_connected = "rtsp://example/detect"
        src._live_capture_url = lambda: "rtsp://example/detect"
        src.lores_size = (640, 640)
        src._single_rtsp_read = False
        src._dual_stream = False
        src._recording = False
        src._update_streaming_output = lambda _frame: None
        src._last_classifier_crop_skew_sec = 0.0
        src._last_classifier_crop_mismatch = False
        src._last_classifier_source_frame = None
        src._record_frame_buffer = []

        armed = {"reason": None}
        calls = {"soft": 0, "reconnect": 0}

        def _read_frame():
            return None, False

        def _soft():
            calls["soft"] += 1
            return False

        def _arm(reason):
            armed["reason"] = reason

        def _reconnect():
            calls["reconnect"] += 1
            # Prove debounce was cleared by soft-fail path.
            self.assertEqual(src._last_reconnect_attempt_ts, 0.0)
            return False

        src._read_frame = _read_frame
        src._soft_restart_capture = _soft
        src._arm_nvdec_opencv_cooldown = _arm
        src._reconnect_if_needed = _reconnect

        self.assertIsNone(src.capture())
        self.assertEqual(calls["soft"], 1)
        self.assertEqual(calls["reconnect"], 1)
        self.assertEqual(armed["reason"], "nvdec_read_stall")

    def test_soft_restart_success_streak_forces_cooldown(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def info(self, *_args, **_kwargs):
                return None

            def warning(self, *_args, **_kwargs):
                return None

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src._read_lock = threading.Lock()
        src._frame_count = 0
        src._last_frame_time = 0
        src._capture_backend_used = "ffmpeg_nvmpi"
        src._ffmpeg_capture_failures = 0
        src._force_opencv_until_ts = 0.0
        src._nvdec_opencv_cooldown_sec = 120.0
        src._soft_restart_failures_threshold = 2
        src._soft_restart_success_streak = 2
        src._soft_restart_max_success_streak = 2
        src._consecutive_read_failures = 2
        src._last_reconnect_attempt_ts = time.monotonic()
        src._capture_url_connected = "rtsp://example/detect"
        src._live_capture_url = lambda: "rtsp://example/detect"
        src.lores_size = (640, 640)
        src._single_rtsp_read = False
        src._dual_stream = False
        src._recording = False
        src._update_streaming_output = lambda _frame: None
        src._last_classifier_crop_skew_sec = 0.0
        src._last_classifier_crop_mismatch = False
        src._last_classifier_source_frame = None
        src._record_frame_buffer = []

        armed = {"reason": None}
        calls = {"soft": 0, "reconnect": 0}

        src._read_frame = lambda: (None, False)
        src._soft_restart_capture = lambda: calls.__setitem__("soft", calls["soft"] + 1) or True
        src._arm_nvdec_opencv_cooldown = lambda reason: armed.__setitem__("reason", reason)
        src._reconnect_if_needed = lambda: (calls.__setitem__("reconnect", calls["reconnect"] + 1), False)[1]

        self.assertIsNone(src.capture())
        self.assertEqual(calls["soft"], 0)
        self.assertEqual(calls["reconnect"], 1)
        self.assertEqual(armed["reason"], "nvdec_soft_restart_loop")

    def test_mjpeg_read_does_not_mutate_health_counters(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Cap:
            def isOpened(self):
                return True

            def read(self):
                return True, object()

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src._cap = _Cap()
        src._consecutive_read_failures = 2
        src._soft_restart_success_streak = 1
        frame, ok = src._read_frame(track_health=False)
        self.assertTrue(ok)
        self.assertIsNotNone(frame)
        self.assertEqual(src._consecutive_read_failures, 2)
        self.assertEqual(src._soft_restart_success_streak, 1)

    def test_slow_connect_debounce_allows_soft_path(self):
        """Debounce starts after connect completes so soft can accumulate."""
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def info(self, *_args, **_kwargs):
                return None

            def warning(self, *_args, **_kwargs):
                return None

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src.auto_reconnect = True
        src._reconnect_debounce_sec = 3.0
        src._last_reconnect_attempt_ts = 0.0
        src._capture_url_connected = "rtsp://example/detect"
        src._live_capture_url = lambda: "rtsp://example/detect"
        src._reconnect_delay = 0.01
        src._consecutive_read_failures = 0
        connect_calls = {"n": 0}

        def _slow_connect():
            connect_calls["n"] += 1
            time.sleep(0.05)  # simulate open latency inside connect
            return True

        src._connect = _slow_connect
        src.refresh_record_stream_geometry = lambda: None
        self.assertTrue(src._reconnect_if_needed())
        self.assertEqual(connect_calls["n"], 1)
        after = src._last_reconnect_attempt_ts
        self.assertGreater(after, 0.0)
        # Immediate second attempt must debounce (timestamp is post-connect).
        self.assertFalse(src._reconnect_if_needed())
        self.assertEqual(connect_calls["n"], 1)

        # Capture path: consecutive accumulates across debounced reconnects → soft.
        src._read_lock = threading.Lock()
        src._frame_count = 0
        src._last_frame_time = 0
        src._capture_backend_used = "ffmpeg_nvmpi"
        src._soft_restart_failures_threshold = 3
        src._soft_restart_success_streak = 0
        src._soft_restart_max_success_streak = 2
        src._consecutive_read_failures = 2
        src.lores_size = (640, 640)
        src._single_rtsp_read = False
        src._dual_stream = False
        src._recording = False
        src._update_streaming_output = lambda _frame: None
        src._last_classifier_crop_skew_sec = 0.0
        src._last_classifier_crop_mismatch = False
        src._last_classifier_source_frame = None
        src._record_frame_buffer = []
        soft_calls = {"n": 0}

        def _read_fail(*_a, **_k):
            if soft_calls["n"] > 0:
                src._consecutive_read_failures = 0
                return object(), True
            src._consecutive_read_failures += 1
            return None, False

        def _soft():
            soft_calls["n"] += 1
            src._consecutive_read_failures = 0
            return True

        src._read_frame = _read_fail
        src._soft_restart_capture = _soft
        # Debounce still active → reconnect skipped; soft should run (consec>=3).
        frame = src.capture()
        self.assertIsNotNone(frame)
        self.assertEqual(soft_calls["n"], 1)
        self.assertEqual(connect_calls["n"], 1)

    def test_encoding_utils_normalize_video_encoding(self):
        from encoding_utils import normalize_video_encoding

        self.assertEqual(normalize_video_encoding(None), "jetson")
        self.assertEqual(normalize_video_encoding("jetson"), "jetson")
        self.assertEqual(normalize_video_encoding("orin"), "jetson")
        self.assertEqual(normalize_video_encoding("nvenc"), "jetson")
        self.assertEqual(normalize_video_encoding("nvmpi"), "jetson")
        self.assertEqual(normalize_video_encoding("cpu"), "cpu")
        self.assertEqual(normalize_video_encoding("intel"), "jetson")  # fallback

    def test_encoding_utils_normalize_capture_backend(self):
        from encoding_utils import normalize_capture_backend

        self.assertEqual(normalize_capture_backend(None), "auto")
        self.assertEqual(normalize_capture_backend("auto"), "auto")
        self.assertEqual(normalize_capture_backend("opencv"), "opencv")
        self.assertEqual(normalize_capture_backend("ffmpeg_nvmpi"), "ffmpeg_nvmpi")
        self.assertEqual(normalize_capture_backend("ffmpeg_vaapi"), "auto")  # fallback


if __name__ == "__main__":
    unittest.main()
