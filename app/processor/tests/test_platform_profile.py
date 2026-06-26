"""Tests for platform_profile."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from platform_profile import DEFAULT_PLATFORM, KNOWN_PLATFORMS, normalize_platform


class TestPlatformProfile(unittest.TestCase):
    def test_default_orin(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(normalize_platform(), DEFAULT_PLATFORM)
            self.assertEqual(normalize_platform(""), DEFAULT_PLATFORM)
            self.assertEqual(DEFAULT_PLATFORM, "orin")

    def test_orin_alias(self):
        self.assertEqual(normalize_platform("orin"), "orin")

    def test_env_override(self):
        with patch.dict(os.environ, {"BIRDLENSE_PLATFORM": "orin"}, clear=False):
            self.assertEqual(normalize_platform(), "orin")

    def test_legacy_platforms_fall_back_to_orin(self):
        self.assertEqual(normalize_platform("intel_nuc"), DEFAULT_PLATFORM)
        self.assertEqual(normalize_platform("jetson_nano"), DEFAULT_PLATFORM)
        self.assertEqual(normalize_platform("raspberry_pi"), DEFAULT_PLATFORM)

    def test_known_platforms_orin_only(self):
        self.assertEqual(KNOWN_PLATFORMS, frozenset({"orin"}))


if __name__ == "__main__":
    unittest.main()
