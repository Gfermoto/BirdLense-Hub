"""Go2RTC live capture backend helpers (#373)."""

import os
import sys
import threading
import time
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestGo2RTCCaptureBackend(unittest.TestCase):
    def test_normalize_capture_backend(self):
        from sources.go2rtc_stream_source import _normalize_capture_backend

        self.assertEqual(_normalize_capture_backend(None), "auto")
        self.assertEqual(_normalize_capture_backend("opencv"), "opencv")
        self.assertEqual(_normalize_capture_backend("ffmpeg_vaapi"), "ffmpeg_vaapi")
        self.assertEqual(_normalize_capture_backend("broken"), "auto")

    def test_ffmpeg_vaapi_capture_cmd_outputs_raw_bgr24(self):
        from sources.go2rtc_stream_source import _ffmpeg_vaapi_capture_cmd

        cmd = _ffmpeg_vaapi_capture_cmd("rtsp://example/stream", (640, 640))
        joined = " ".join(cmd)
        self.assertIn("-hwaccel vaapi", joined)
        self.assertIn("scale_vaapi=w=640:h=640", joined)
        self.assertIn("force_original_aspect_ratio=decrease", joined)
        self.assertIn("pad=w=640:h=640", joined)
        self.assertIn("-pix_fmt bgr24", joined)
        self.assertEqual(cmd[-2:], ["rawvideo", "pipe:1"])

    def test_ffmpeg_record_cmd_for_vaapi_contains_ts_and_audio_guards(self):
        from sources.go2rtc_stream_source import _ffmpeg_record_cmd

        cmd = _ffmpeg_record_cmd(
            stream_url="rtsp://example/stream",
            output="/tmp/out.mp4",
            use_vaapi=True,
            record_stream_codec="h264",
        )
        joined = " ".join(cmd)
        self.assertIn("+genpts+igndts", joined)
        self.assertIn("-avoid_negative_ts make_zero", joined)
        self.assertIn("-max_interleave_delta 0", joined)
        self.assertIn("-map 0:v:0 -map 0:a:0?", joined)
        self.assertIn("-af aresample=async=1:first_pts=0", joined)
        self.assertIn("-c:v h264_vaapi", joined)
        self.assertIn("-c:a aac", joined)

    def test_ffmpeg_record_cmd_for_copy_uses_copy_video(self):
        from sources.go2rtc_stream_source import _ffmpeg_record_cmd

        cmd = _ffmpeg_record_cmd(
            stream_url="rtsp://example/stream",
            output="/tmp/out.mp4",
            use_vaapi=False,
            record_stream_codec="copy",
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

    def test_capture_fallback_reason_matrix(self):
        from sources.go2rtc_stream_source import _capture_fallback_reason

        self.assertEqual(
            _capture_fallback_reason(
                requested_backend="opencv",
                encoding_mode="cpu",
                vaapi_available=False,
            ),
            "requested_opencv",
        )
        self.assertEqual(
            _capture_fallback_reason(
                requested_backend="ffmpeg_vaapi",
                encoding_mode="intel",
                vaapi_available=False,
            ),
            "vaapi_unavailable",
        )
        self.assertEqual(
            _capture_fallback_reason(
                requested_backend="auto",
                encoding_mode="cpu",
                vaapi_available=True,
            ),
            "auto_prefers_opencv_for_non_intel_encoding",
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
        src._capture_backend_used = "ffmpeg_vaapi"
        src._ffmpeg_capture_failures = 0
        src._force_opencv_until_ts = 0.0
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

    def test_should_use_ffmpeg_blocked_during_cooldown(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src._capture_backend = "ffmpeg_vaapi"
        src._encoding_mode = "intel"
        src._force_opencv_until_ts = time.time() + 30
        self.assertFalse(src._should_use_ffmpeg_vaapi_capture())

    def test_capture_forces_opencv_after_repeated_ffmpeg_failures(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        class _Logger:
            def warning(self, *_args, **_kwargs):
                return None

        src = Go2RTCStreamSource.__new__(Go2RTCStreamSource)
        src.logger = _Logger()
        src._read_lock = threading.Lock()
        src._frame_count = 0
        src._last_frame_time = 0
        src._capture_backend_used = "ffmpeg_vaapi"
        src._ffmpeg_capture_failures = 3
        src._force_opencv_until_ts = 0.0
        src.lores_size = (640, 640)
        src._read_frame = lambda: (None, False)
        src._reconnect_if_needed = lambda: False
        src._update_streaming_output = lambda _frame: None

        self.assertIsNone(src.capture())
        self.assertGreater(src._force_opencv_until_ts, time.time())
        self.assertEqual(src._ffmpeg_capture_failures, 0)


if __name__ == "__main__":
    unittest.main()
