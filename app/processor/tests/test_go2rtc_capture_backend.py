"""Go2RTC live capture backend helpers (#373)."""

import os
import sys
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
        self.assertIn("-pix_fmt bgr24", joined)
        self.assertEqual(cmd[-2:], ["rawvideo", "pipe:1"])

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


if __name__ == "__main__":
    unittest.main()
