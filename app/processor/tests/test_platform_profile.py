"""Tests for platform_profile."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from platform_profile import DEFAULT_PLATFORM, normalize_platform


class TestPlatformProfile(unittest.TestCase):
    def test_default_intel_nuc(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(normalize_platform(), DEFAULT_PLATFORM)
            self.assertEqual(normalize_platform(""), DEFAULT_PLATFORM)

    def test_dash_alias(self):
        self.assertEqual(normalize_platform("intel-nuc"), "intel_nuc")
        self.assertEqual(normalize_platform("jetson-nano"), "jetson_nano")

    def test_env_override(self):
        with patch.dict(os.environ, {"BIRDLENSE_PLATFORM": "jetson_nano"}, clear=False):
            self.assertEqual(normalize_platform(), "jetson_nano")

    def test_unknown_falls_back(self):
        self.assertEqual(normalize_platform("raspberry_pi"), DEFAULT_PLATFORM)


if __name__ == "__main__":
    unittest.main()
