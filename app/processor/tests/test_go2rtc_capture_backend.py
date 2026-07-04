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

    def test_gst_nvmpi_pipeline_format(self):
        """Verify NVMPI_GST_PIPELINE resolves known working pipeline."""
        from sources.go2rtc_stream_source import NVMPI_GST_PIPELINE

        url = "rtsp://test:pass@192.168.1.129/stream1"
        pipeline = NVMPI_GST_PIPELINE % (url, 704, 576)
        self.assertIn("nvv4l2decoder", pipeline)
        self.assertIn("nvv4l2decoder enable-max-performance=1", pipeline)
        self.assertIn("appsink", pipeline)
        self.assertIn("70", pipeline)  # metadata test
        self.assertNotIn("fdsink", pipeline)

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
