"""media_runtime helpers."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
_app_path = os.path.abspath(os.path.join(_current_dir, "../../"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
if _app_path not in sys.path:
    sys.path.insert(0, _app_path)


class TestMediaRuntimeHelpers(unittest.TestCase):
    def test_resolve_capture_stream_url_accepts_direct_rtsp(self):
        from media_runtime import _resolve_capture_stream_url

        direct = "rtsp://cam.local:554/stream1"
        self.assertEqual(
            _resolve_capture_stream_url(
                go2rtc_url="http://go2rtc:1984",
                detect_stream_name=direct,
                username="user",
                password="pass",
            ),
            direct,
        )

    def test_resolve_capture_stream_url_builds_from_stream_name(self):
        from media_runtime import _resolve_capture_stream_url

        self.assertEqual(
            _resolve_capture_stream_url(
                go2rtc_url="http://192.168.1.11:1984",
                detect_stream_name="Forest_detect",
                username="u",
                password="p",
            ),
            "rtsp://u:p@192.168.1.11:8554/Forest_detect",
        )

    def test_resolve_capture_stream_url_none_for_empty_value(self):
        from media_runtime import _resolve_capture_stream_url

        self.assertIsNone(
            _resolve_capture_stream_url(
                go2rtc_url="http://192.168.1.11:1984",
                detect_stream_name="",
            ),
        )

    def test_validate_go2rtc_detect_streams_raises_when_missing(self):
        from media_runtime import _validate_go2rtc_detect_streams

        with self.assertRaises(RuntimeError):
            _validate_go2rtc_detect_streams(
                [{"id": "yard", "stream_name": "yard_main"}],
            )

    def test_validate_go2rtc_detect_streams_ok(self):
        from media_runtime import _validate_go2rtc_detect_streams

        _validate_go2rtc_detect_streams(
            [{"id": "yard", "stream_name": "yard_main", "detect_stream_name": "yard_detect"}],
        )


if __name__ == "__main__":
    unittest.main()
