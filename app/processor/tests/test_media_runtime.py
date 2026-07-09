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
        from app_config.cameras import validate_go2rtc_detect_streams

        issues = validate_go2rtc_detect_streams(
            [{"id": "yard", "stream_name": "yard_main"}],
            video_source="go2rtc",
        )
        self.assertTrue(issues)

    def test_validate_go2rtc_detect_streams_ok(self):
        from app_config.cameras import validate_go2rtc_detect_streams

        issues = validate_go2rtc_detect_streams(
            [{"id": "yard", "stream_name": "yard_main", "detect_stream_name": "yard_detect"}],
            video_source="go2rtc",
        )
        self.assertEqual(issues, [])

    def test_single_rtsp_read_defaults_false(self):
        from media_runtime import parse_single_rtsp_read_flag

        class _Cfg:
            def __init__(self, data=None):
                self._data = dict(data or {})

            def get(self, key, default=None):
                return self._data.get(key, default)

        self.assertFalse(parse_single_rtsp_read_flag(_Cfg()))
        self.assertFalse(parse_single_rtsp_read_flag(_Cfg({"processor.single_rtsp_read": False})))
        self.assertFalse(parse_single_rtsp_read_flag(_Cfg({"processor.single_rtsp_read": "false"})))

    def test_single_rtsp_read_parses_truthy_strings(self):
        from media_runtime import parse_single_rtsp_read_flag

        class _Cfg:
            def __init__(self, val):
                self._val = val

            def get(self, key, default=None):
                if key == "processor.single_rtsp_read":
                    return self._val
                return default

        self.assertTrue(parse_single_rtsp_read_flag(_Cfg(True)))
        self.assertTrue(parse_single_rtsp_read_flag(_Cfg("1")))

    def test_detect_stream_required_even_when_single_rtsp_read_enabled(self):
        from sources.go2rtc_stream_source import Go2RTCStreamSource

        with self.assertRaises(ValueError) as ctx:
            Go2RTCStreamSource(
                stream_url="rtsp://example/main",
                main_size=(1920, 1080),
                lores_size=(704, 576),
                capture_stream_url="",
                single_rtsp_read=True,
            )
        self.assertIn("detect_stream_name", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
