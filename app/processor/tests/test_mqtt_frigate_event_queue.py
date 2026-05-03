"""Queue eligibility tests for Frigate MQTT events."""

import json
import os
import sys
import threading
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

import mqtt_aggregator as ma  # noqa: E402


class TestFrigateEventQueue(unittest.TestCase):
    def test_rejected_camera_filter_event_not_enqueued(self):
        calls = []

        def cb(cam, species):
            calls.append((cam, species))

        agg = ma.MQTTEventAggregator.__new__(ma.MQTTEventAggregator)
        agg._lock = threading.Lock()
        agg._events = deque()
        agg.frigate_topic = "frigate/events"
        agg._frigate_label_exclude = set()
        agg._on_frigate_motion = (
            {"BirdBox"},
            {"bird"},
            cb,
        )

        payload = json.dumps(
            {
                "after": {
                    "camera": "front",
                    "label": "bird",
                    "top_score": 0.81,
                    "box": [0, 0, 1, 1],
                }
            }
        ).encode()
        msg = MagicMock()
        msg.topic = "frigate/events"
        msg.payload = payload

        def cfg_get(key, default=None):
            if key == "motion.frigate_trigger_on_tracked_object":
                return True
            return default

        with patch.object(ma.app_config, "get", side_effect=cfg_get):
            agg._on_message(None, None, msg)

        self.assertEqual(calls, [])
        self.assertEqual(len(agg._events), 0)


if __name__ == "__main__":
    unittest.main()
