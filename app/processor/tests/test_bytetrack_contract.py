"""Tests for ByteTrack vs track(conf) contract."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from bytetrack_contract import inspect_bytetrack_conf_contract  # noqa: E402


class TestBytetrackContract(unittest.TestCase):
    def test_ok_when_thresholds_below_conf(self):
        yaml_text = """
tracker_type: bytetrack
track_high_thresh: 0.06
new_track_thresh: 0.06
track_low_thresh: 0.03
track_buffer: 12
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write(yaml_text)
            path = fh.name
        try:
            info = inspect_bytetrack_conf_contract(path, 0.12)
            self.assertTrue(info["contract_ok"])
        finally:
            os.unlink(path)

    def test_risk_when_thresholds_gte_conf(self):
        yaml_text = """
tracker_type: bytetrack
track_high_thresh: 0.15
new_track_thresh: 0.14
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write(yaml_text)
            path = fh.name
        try:
            info = inspect_bytetrack_conf_contract(path, 0.12)
            self.assertFalse(info["contract_ok"])
            self.assertEqual(info["risk"], "thresholds_gte_track_conf")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
