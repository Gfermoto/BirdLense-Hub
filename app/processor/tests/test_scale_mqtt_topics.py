"""Парсинг bird_present и запись состояния весов (префикс MQTT)."""

import json
import os
import sys
import tempfile
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from mqtt_aggregator import (  # noqa: E402
    _parse_bird_present_payload,
    write_feeder_scale_state,
)
from mqtt_scale_state import write_feeder_scale_state as write_feeder_scale_state_direct  # noqa: E402


class TestScaleMqttTopics(unittest.TestCase):
    def test_parse_bird_present(self):
        self.assertIs(_parse_bird_present_payload(b""), None)
        self.assertEqual(_parse_bird_present_payload(b"ON"), True)
        self.assertEqual(_parse_bird_present_payload(b"off"), False)
        self.assertEqual(_parse_bird_present_payload(b" true "), True)

    def test_write_feeder_scale_state_merge(self):
        with tempfile.TemporaryDirectory() as d:
            write_feeder_scale_state(d, 12.3, "g", history_max_lines=100)
            path = os.path.join(d, "feeder_scale_state.json")
            with open(path, encoding="utf-8") as f:
                a = json.load(f)
            self.assertEqual(a["weight"], 12.3)
            self.assertEqual(a["unit"], "g")
            write_feeder_scale_state(d, bird_present=True, history_max_lines=100)
            with open(path, encoding="utf-8") as f:
                b = json.load(f)
            self.assertEqual(b["weight"], 12.3)
            self.assertTrue(b["bird_present"])

    def test_write_feeder_scale_state_direct_module(self):
        with tempfile.TemporaryDirectory() as d:
            write_feeder_scale_state_direct(d, 7.5, "g", history_max_lines=100)
            path = os.path.join(d, "feeder_scale_state.json")
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["weight"], 7.5)
            self.assertEqual(data["unit"], "g")


if __name__ == "__main__":
    unittest.main()
