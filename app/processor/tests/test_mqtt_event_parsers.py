"""MQTT parser helpers live outside the aggregator anchor module."""

from __future__ import annotations

import json
import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from mqtt_event_parsers import (  # noqa: E402
    _parse_bird_present_payload,
    _parse_birdnet_event,
    _parse_frigate_event_dict,
    _parse_scale_payload,
)


class TestMqttEventParsers(unittest.TestCase):
    def test_module_parses_current_mqtt_payload_shapes(self):
        self.assertTrue(_parse_bird_present_payload(b"ON"))
        self.assertFalse(_parse_bird_present_payload(b"false"))
        self.assertEqual(_parse_scale_payload(b'{"Weight": "12,3"}'), 12.3)

        frigate = _parse_frigate_event_dict({"after": {"camera": "cam-a", "label": "bird", "score": "bad"}})
        self.assertIsNotNone(frigate)
        self.assertEqual(frigate["camera"], "cam-a")
        self.assertEqual(frigate["confidence"], 0.0)

        birdnet = _parse_birdnet_event(json.dumps({"CommonName": "Robin", "Confidence": 0.8}).encode("utf-8"))
        self.assertIsNotNone(birdnet)
        self.assertEqual(birdnet["species"], "Robin")


if __name__ == "__main__":
    unittest.main()
