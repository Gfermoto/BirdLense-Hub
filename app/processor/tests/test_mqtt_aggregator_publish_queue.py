"""Tests for MQTT outbound queue (processor tech debt #224, disconnect policy #238)."""

import json
import os
import sys
import tempfile
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

    def test_on_disconnect_preserves_queue(self):
        self.agg._enqueue_publish("t1", "p", qos=0, retain=False)
        self.agg._enqueue_publish("t2", "p2", qos=1, retain=True)
        self.assertEqual(self.agg._publish_queue.qsize(), 2)
        self.agg._on_disconnect(None, None, 0)
        self.assertEqual(self.agg._publish_queue.qsize(), 2)
        self.assertFalse(self.agg._connected)

    def test_drain_publish_queue_noop_when_disconnected_preserves_queue(self):
        self.agg._enqueue_publish("t1", "p", qos=0, retain=False)
        self.agg._connected = False
        self.agg._drain_publish_queue(500)
        self.assertEqual(self.agg._publish_queue.qsize(), 1)
        self.agg._client.publish.assert_not_called()

    def test_publish_queue_drops_oldest_when_full(self):
        agg = MQTTEventAggregator(
            broker="127.0.0.1",
            ha_discovery=False,
            publish_queue_max=2,
        )
        agg._enqueue_publish("t1", "old", qos=0, retain=False)
        agg._enqueue_publish("t2", "mid", qos=0, retain=False)
        agg._enqueue_publish("t3", "new", qos=0, retain=False)
        queued = [item[0] for item in list(agg._publish_queue.queue)]
        self.assertEqual(queued, ["t2", "t3"])
        self.assertEqual(agg._publish_queue.qsize(), 2)

    def test_publish_enqueues_when_disconnected(self):
        self.agg._connected = False
        self.agg.publish_detection("X", 0.5)
        self.assertEqual(self.agg._publish_queue.qsize(), 5)

    def test_publish_skips_when_stopped(self):
        self.agg._stopped = True
        self.agg.publish_detection("X", 0.5)
        self.assertEqual(self.agg._publish_queue.qsize(), 0)

    def test_publish_skips_when_broker_unset(self):
        self.agg.broker = ""
        self.agg.publish_detection("X", 0.5)
        self.assertEqual(self.agg._publish_queue.qsize(), 0)

    def test_publish_ha_discovery_adds_scale_entities_when_topics_configured(self):
        agg = MQTTEventAggregator(
            broker="127.0.0.1",
            ha_discovery=True,
            scales_topic="birdlense/scale/weight",
            scales_bird_present_topic="birdlense/scale/bird_present",
            scales_unit="g",
        )
        agg._client = MagicMock()
        agg._connected = True

        agg._publish_ha_discovery()

        payloads = [call.args[1] for call in agg._client.publish.call_args_list]
        self.assertTrue(
            any('"unique_id": "birdlense_feeder_weight"' in p for p in payloads if isinstance(p, str))
        )
        self.assertTrue(
            any('"unique_id": "birdlense_feeder_bird_present"' in p for p in payloads if isinstance(p, str))
        )

    def test_publish_ha_discovery_replays_scale_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "feeder_scale_state.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"weight": 12.3, "bird_present": True}, f)

            agg = MQTTEventAggregator(
                broker="127.0.0.1",
                ha_discovery=True,
                scales_topic="birdlense/scale/weight",
                scales_bird_present_topic="birdlense/scale/bird_present",
                scales_data_dir=tmpdir,
                scales_unit="g",
            )
            agg._client = MagicMock()
            agg._connected = True

            agg._publish_ha_discovery()

            calls = [(call.args[0], call.args[1]) for call in agg._client.publish.call_args_list]
            self.assertIn(("birdlense/sensor/feeder_weight/state", "12.3"), calls)
            self.assertIn(("birdlense/binary_sensor/feeder_bird_present/state", "ON"), calls)

    def test_scale_mqtt_messages_enqueue_ha_state_updates(self):
        agg = MQTTEventAggregator(
            broker="127.0.0.1",
            ha_discovery=True,
            scales_topic="birdlense/scale/weight",
            scales_bird_present_topic="birdlense/scale/bird_present",
            scales_unit="g",
        )

        class Msg:
            def __init__(self, topic, payload):
                self.topic = topic
                self.payload = payload

        agg._on_message(None, None, Msg("birdlense/scale/weight", b"45.6"))
        agg._on_message(None, None, Msg("birdlense/scale/bird_present", b"ON"))

        queued = list(agg._publish_queue.queue)
        self.assertIn(("birdlense/sensor/feeder_weight/state", "45.6", 1, True), queued)
        self.assertIn(("birdlense/binary_sensor/feeder_bird_present/state", "ON", 1, True), queued)

    def test_custom_queue_sizes_are_applied(self):
        agg = MQTTEventAggregator(
            broker="127.0.0.1",
            max_events=7,
            publish_queue_max=11,
            feeder_scale_queue_max=13,
        )
        self.assertEqual(agg._events.maxlen, 7)
        self.assertEqual(agg._publish_queue.maxsize, 11)
        self.assertEqual(agg._feeder_scale_queue_max, 13)

    def test_event_fifo_keeps_latest_when_over_capacity(self):
        agg = MQTTEventAggregator(
            broker="127.0.0.1",
            max_events=1,
        )

        class Msg:
            def __init__(self, topic, payload):
                self.topic = topic
                self.payload = payload

        p1 = json.dumps({"after": {"camera": "c1", "label": "bird", "top_score": 0.61}}).encode()
        p2 = json.dumps({"after": {"camera": "c2", "label": "bird", "top_score": 0.74}}).encode()
        agg._on_message(None, None, Msg("frigate/events", p1))
        agg._on_message(None, None, Msg("frigate/events", p2))

        self.assertEqual(len(agg._events), 1)
        self.assertEqual(agg._events[0].get("camera"), "c2")


if __name__ == "__main__":
    unittest.main()
