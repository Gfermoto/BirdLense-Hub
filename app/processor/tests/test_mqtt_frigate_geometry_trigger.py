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
from motion_detectors.frigate_mqtt import FrigateMotionFromAggregator  # noqa: E402


class TestFrigateGeometryTrigger(unittest.TestCase):
    def test_frigate_motion_queue_preserves_burst_events(self):
        det = FrigateMotionFromAggregator(None, camera_filter=set(), label_filter={'bird'})
        det._on_motion('BirdBox', 'bird', 0.7, {'timestamp': '2026-01-01T00:00:00+00:00'})
        det._on_motion('BirdBox', 'bird', 0.8, {'timestamp': '2026-01-01T00:00:01+00:00'})
        self.assertTrue(det.check_pending())
        self.assertTrue(det.check_pending())
        self.assertFalse(det.check_pending())

    def test_frigate_motion_mark_pending_requeues_active_event(self):
        det = FrigateMotionFromAggregator(None, camera_filter=set(), label_filter={'bird'})
        det._on_motion('BirdBox', 'bird', 0.7, {'timestamp': '2026-01-01T00:00:00+00:00'})
        self.assertTrue(det.check_pending())
        det.mark_pending()
        self.assertTrue(det.check_pending())

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
            if key == 'triggers.frigate.trigger_on_tracked_object':
                return True
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'BirdBox')
        self.assertEqual(len(agg._events), 1)
        self.assertTrue(agg._events[0].get('_frigate_merge_suppressed'))



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

        def cfg_get(key, default=None):
            if key == 'triggers.frigate.trigger_on_tracked_object':
                return True
            if key == 'triggers.frigate.min_trigger_score':
                return 0.0
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
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

    def test_min_trigger_score_blocks_low_confidence_event(self):
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
                    'label': 'bird',
                    'top_score': 0.31,
                    'box': [0, 0, 1, 1],
                }
            }
        ).encode()
        msg = MagicMock()
        msg.topic = 'frigate/events'
        msg.payload = payload

        def cfg_get(key, default=None):
            if key == 'triggers.frigate.trigger_on_tracked_object':
                return True
            if key == 'triggers.frigate.min_trigger_score':
                return 0.5
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 0)
        self.assertEqual(len(agg._events), 1)

    def test_camera_specific_min_trigger_score_overrides_global(self):
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
                    'label': 'bird',
                    'top_score': 0.57,
                    'box': [0, 0, 1, 1],
                }
            }
        ).encode()
        msg = MagicMock()
        msg.topic = 'frigate/events'
        msg.payload = payload

        def cfg_get(key, default=None):
            if key == 'triggers.frigate.trigger_on_tracked_object':
                return True
            if key == 'triggers.frigate.min_trigger_score':
                return 0.5
            if key == 'triggers.frigate.min_trigger_score_by_camera':
                return {'birdbox': 0.62}
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 0)
        self.assertEqual(len(agg._events), 1)

    def test_excluded_cat_still_triggers_recording_queued_with_merge_suppressed(self):
        """Excluded labels: motion fires; event is stored for Frigate standalone, not for YOLO merge."""
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
            if key == 'triggers.frigate.trigger_on_tracked_object':
                return True
            if key == 'triggers.frigate.min_trigger_score':
                return 0.0
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(agg._events), 1)
        stored = agg._events[0]
        self.assertTrue(stored.get('_frigate_merge_suppressed'))
        self.assertEqual(stored.get('label'), 'cat')
        self.assertEqual(stored.get('frigate_bbox_norm'), [0.02, 0.02, 0.2, 0.25])

    def test_geometry_fallback_blocks_person_label(self):
        calls = []

        def cb(cam, species):
            calls.append((cam, species))

        agg = ma.MQTTEventAggregator.__new__(ma.MQTTEventAggregator)
        agg._lock = threading.Lock()
        agg._events = deque()
        agg.frigate_topic = 'frigate/events'
        agg._frigate_label_exclude = set()
        agg._on_frigate_motion = (set(), {'bird'}, cb)
        agg._geometry_fallback_last_emit = {}
        payload = json.dumps(
            {'after': {'camera': 'Forest', 'label': 'person', 'top_score': 0.77, 'box': [0, 0, 1, 1]}}
        ).encode()
        msg = MagicMock()
        msg.topic = 'frigate/events'
        msg.payload = payload

        def cfg_get(key, default=None):
            if key == 'triggers.frigate.trigger_on_tracked_object':
                return True
            if key == 'triggers.frigate.geometry_fallback_enabled':
                return True
            if key == 'triggers.frigate.geometry_fallback_label_exclude':
                return ['person']
            if key == 'triggers.frigate.min_trigger_score':
                return 0.5
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 0)
        self.assertEqual(len(agg._events), 0)

    def test_geometry_fallback_has_cooldown_for_same_camera_label(self):
        calls = []

        def cb(cam, species):
            calls.append((cam, species))

        agg = ma.MQTTEventAggregator.__new__(ma.MQTTEventAggregator)
        agg._lock = threading.Lock()
        agg._events = deque()
        agg.frigate_topic = 'frigate/events'
        agg._frigate_label_exclude = set()
        agg._on_frigate_motion = (set(), {'bird'}, cb)
        agg._geometry_fallback_last_emit = {}
        payload = json.dumps(
            {'after': {'camera': 'Forest', 'label': 'unknown_label', 'top_score': 0.77, 'box': [0, 0, 1, 1]}}
        ).encode()
        msg = MagicMock()
        msg.topic = 'frigate/events'
        msg.payload = payload

        def cfg_get(key, default=None):
            if key == 'triggers.frigate.trigger_on_tracked_object':
                return True
            if key == 'triggers.frigate.geometry_fallback_enabled':
                return True
            if key == 'triggers.frigate.geometry_fallback_label_exclude':
                return []
            if key == 'triggers.frigate.geometry_fallback_cooldown_seconds':
                return 999.0
            if key == 'triggers.frigate.min_trigger_score':
                return 0.5
            return default

        with patch.object(ma.app_config, 'get', side_effect=cfg_get):
            agg._on_message(None, None, msg)
            agg._on_message(None, None, msg)

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(agg._events), 1)


if __name__ == '__main__':
    unittest.main()
