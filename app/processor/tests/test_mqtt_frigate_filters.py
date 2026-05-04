"""Frigate filter normalization from YAML (scalar str vs list, #237)."""

import os
import sys
import unittest


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.append(src_path)

import frigate_scope as fs  # noqa: E402


class TestMqttFrigateFilters(unittest.TestCase):
    def test_frigate_camera_filter_scalar_string_is_single_id(self):
        cameras = [{'id': 'cam1'}, {'id': 'cam2'}]
        cfg = {'triggers.frigate.camera_filter': 'front_door'}
        self.assertEqual(fs.frigate_camera_allow_ids(cameras, cfg), ['front_door'])

    def test_frigate_camera_filter_list_passthrough(self):
        cameras = [{'id': 'a'}]
        cfg = {'triggers.frigate.camera_filter': ['x', 'y']}
        self.assertEqual(fs.frigate_camera_allow_ids(cameras, cfg), ['x', 'y'])

    def test_frigate_camera_filter_none_uses_all_camera_ids(self):
        cameras = [{'id': 'c1'}, {'id': 'c2'}]
        self.assertEqual(fs.frigate_camera_allow_ids(cameras, {}), ['c1', 'c2'])

    def test_frigate_camera_filter_empty_list_uses_all_camera_ids(self):
        cameras = [{'id': 'c1'}, {'id': 'c2'}]
        cfg = {
            'triggers.frigate.camera_filter': [],
            'mqtt.frigate_camera_filter': ['should_not_use_when_triggers_present'],
        }
        self.assertEqual(fs.frigate_camera_allow_ids(cameras, cfg), ['c1', 'c2'])

    def test_frigate_camera_filter_mqtt_fallback_when_triggers_absent(self):
        cameras = [{'id': 'a'}]
        cfg = {'mqtt.frigate_camera_filter': ['z']}
        self.assertEqual(fs.frigate_camera_allow_ids(cameras, cfg), ['z'])

    def test_frigate_label_filter_scalar_string_is_single_label(self):
        cfg = {'triggers.frigate.label_filter': 'Bird'}
        out = fs.frigate_label_resolve_set(
            'triggers.frigate.label_filter',
            'mqtt.frigate_label_filter',
            ['bird'],
            cfg,
        )
        self.assertEqual(out, {'Bird'})

    def test_empty_triggers_label_filter_stays_empty_wildcard(self):
        cfg = {
            'triggers.frigate.label_filter': [],
            'mqtt.frigate_label_filter': ['bird', 'Bird'],
        }
        out = fs.frigate_label_resolve_set(
            'triggers.frigate.label_filter',
            'mqtt.frigate_label_filter',
            ['bird'],
            cfg,
        )
        self.assertEqual(out, set())


if __name__ == '__main__':
    unittest.main()
