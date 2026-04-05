"""Tests for MQTT outbound queue (processor tech debt #224)."""

import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from mqtt_aggregator import MQTTEventAggregator  # noqa: E402


class TestMqttAggregatorPublishQueue(unittest.TestCase):
    def setUp(self):
        self.agg = MQTTEventAggregator(
            broker="127.0.0.1",
            ha_discovery=True,
        )
        self.agg._client = MagicMock()
        self.agg._connected = True

    def test_publish_detection_does_not_call_client_publish_directly(self):
        self.agg.publish_detection("Robin", 0.88, source="yolo")
        self.agg._client.publish.assert_not_called()
        self.assertEqual(self.agg._publish_queue.qsize(), 5)

    def test_drain_publish_queue_flushes_to_client(self):
        self.agg.publish_detection("Robin", 0.88, source="yolo")
        self.agg._drain_publish_queue(500)
        self.assertEqual(self.agg._publish_queue.qsize(), 0)
        self.assertEqual(self.agg._client.publish.call_count, 5)

    def test_on_disconnect_clears_queue(self):
        self.agg._enqueue_publish("t1", "p", qos=0, retain=False)
        self.agg._enqueue_publish("t2", "p2", qos=1, retain=True)
        self.assertEqual(self.agg._publish_queue.qsize(), 2)
        self.agg._on_disconnect(None, None, 0)
        self.assertEqual(self.agg._publish_queue.qsize(), 0)
        self.assertFalse(self.agg._connected)

    def test_publish_skips_when_disconnected(self):
        self.agg._connected = False
        self.agg.publish_detection("X", 0.5)
        self.assertEqual(self.agg._publish_queue.qsize(), 0)

    def test_publish_skips_when_stopped(self):
        self.agg._stopped = True
        self.agg.publish_detection("X", 0.5)
        self.assertEqual(self.agg._publish_queue.qsize(), 0)


if __name__ == "__main__":
    unittest.main()
