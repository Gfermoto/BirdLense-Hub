"""Unit tests for encoding_utils."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class _Cfg:
    def __init__(self, data: dict):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestEncodingUtils(unittest.TestCase):
    def test_resolve_record_hw_encode_prefers_new_key(self):
        from encoding_utils import resolve_record_hw_encode

        self.assertFalse(
            resolve_record_hw_encode(_Cfg({"video.record_hw_encode": False, "video.record_with_vaapi": True}))
        )

    def test_resolve_record_hw_encode_legacy_fallback(self):
        from encoding_utils import resolve_record_hw_encode

        self.assertTrue(resolve_record_hw_encode(_Cfg({"video.record_with_vaapi": True})))
        self.assertFalse(resolve_record_hw_encode(_Cfg({"video.record_with_vaapi": "off"})))

    def test_resolve_record_hw_encode_default_true(self):
        from encoding_utils import resolve_record_hw_encode

        self.assertTrue(resolve_record_hw_encode(_Cfg({})))


if __name__ == "__main__":
    unittest.main()
