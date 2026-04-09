"""Frigate MQTT: geometry fallback when label not in filter (#reliability)."""

import json
import os
import sys
import threading
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

import mqtt_aggregator as ma  # noqa: E402


class TestFrigateGeometryTrigger(unittest.TestCase):
    def test_labels_match_exclude_case_insensitive(self):
        self.assertTrue(
            ma._frigate_labels_match_exclude({'Cat', ''}, {'cat'}),
        )
        self.assertFalse(
            ma._frigate_labels_match_exclude({'bird'}, {'cat'}),
        )

    def test_parse_frigate_event_dict_bad_score(self):
        d = {
            'after': {
                'camera': 'c1',
                'label': 'bird',
                'score': 'nope',
            }
        }
        ev = ma._parse_frigate_event_dict(d)
        self.assertIsNotNone(ev)
        self.assertEqual(ev['confidence'], 0.0)

    def test_tracked_geometry_detects_box(self):
        self.assertTrue(
            ma._frigate_after_has_tracked_geometry({'box': [0.1, 0.2, 0.5, 0.6]}),
        )
        self.assertFalse(ma._frigate_after_has_tracked_geometry({}))

    def test_tracked_geometry_detects_snapshot_box(self):
        """Новые версии Frigate держат box внутри snapshot, не только в корне after."""
        self.assertTrue(
            ma._frigate_after_has_tracked_geometry({
                'label': 'jay',
                'snapshot': {'box': [10, 20, 100, 200]},
            }),
        )
        self.assertTrue(
            ma._frigate_after_has_tracked_geometry({
                'snapshot': {'region': [0, 0, 640, 480]},
            }),
        )

    def test_on_message_triggers_on_box_when_label_mismatch(self):
        calls = []

        def cb(cam, species):
            calls.append((cam, species))

        agg = ma.MQTTEventAggregator.__new__(ma.MQTTEventAggregator)
        agg._lock = threading.Lock()
        agg._events = deque()
        agg.frigate_topic = 'frigate/events'
        agg._frigate_label_exclude = set()
        agg._on_frigate_motion = (
            set(),
            {'bird'},
            cb,
        )
        payload = json.dumps(
            {
                'after': {
                    'camera': 'BirdBox',
                    'label': 'strange_tf_label',
                    'box': [0, 0, 1, 1],
                }
            }
        ).encode()
        msg = MagicMock()
        msg.topic = 'frigate/events'
        msg.payload = payload

        def cfg_get(key, default=None):
            if key == 'motion.frigate_trigger_on_tracked_object':
                return True
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'BirdBox')



    def test_snapshot_topic_triggers_recording_when_events_missing(self):
        calls = []

        def cb(cam, species):
            calls.append((cam, species))

        agg = ma.MQTTEventAggregator.__new__(ma.MQTTEventAggregator)
        agg._lock = threading.Lock()
        agg._events = deque()
        agg.frigate_topic = 'frigate/events'
        agg._frigate_snapshot_topic = 'frigate/+/+/snapshot'
        agg._frigate_label_exclude = set()
        agg._on_frigate_motion = (set(), {'bird'}, cb)

        msg = MagicMock()
        msg.topic = 'frigate/BirdBox/bird/snapshot'
        msg.payload = b'/api/events/x/snapshot.jpg'
        msg.retain = False

        with patch.object(ma.app_config, 'get', return_value=True):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'BirdBox')
        self.assertGreaterEqual(len(agg._events), 1)

    def test_empty_label_filter_means_any_label(self):
        calls = []

        def cb(cam, species):
            calls.append((cam, species))

        agg = ma.MQTTEventAggregator.__new__(ma.MQTTEventAggregator)
        agg._lock = threading.Lock()
        agg._events = deque()
        agg.frigate_topic = 'frigate/events'
        agg._frigate_label_exclude = set()
        agg._on_frigate_motion = (
            set(),
            set(),
            cb,
        )
        payload = json.dumps(
            {
                'after': {
                    'camera': 'BirdBox',
                    'label': 'jay',
                }
            }
        ).encode()
        msg = MagicMock()
        msg.topic = 'frigate/events'
        msg.payload = payload

        with patch.object(ma.app_config, 'get', return_value=True):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'BirdBox')

    def test_excluded_cat_still_triggers_recording_not_queued_for_merge(self):
        """frigate_label_exclude must not return() before motion; event must not enter _events."""
        calls = []

        def cb(cam, species):
            calls.append((cam, species))

        agg = ma.MQTTEventAggregator.__new__(ma.MQTTEventAggregator)
        agg._lock = threading.Lock()
        agg._events = deque()
        agg.frigate_topic = 'frigate/events'
        agg._frigate_label_exclude = {'cat', 'dog'}
        agg._on_frigate_motion = (
            set(),
            {'bird'},
            cb,
        )
        payload = json.dumps(
            {
                'after': {
                    'camera': 'BirdBox',
                    'label': 'cat',
                    'box': [0.02, 0.02, 0.2, 0.25],
                }
            }
        ).encode()
        msg = MagicMock()
        msg.topic = 'frigate/events'
        msg.payload = payload

        def cfg_get(key, default=None):
            if key == 'motion.frigate_trigger_on_tracked_object':
                return True
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(agg._events), 0)


if __name__ == '__main__':
    unittest.main()
