"""Frigate filter normalization from YAML (scalar str vs list, #237)."""

import os
import sys
import unittest
from unittest.mock import patch


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.append(src_path)

import mqtt_runtime as mqtt_runtime_mod  # noqa: E402


class TestMqttFrigateFilters(unittest.TestCase):
    def test_frigate_camera_filter_scalar_string_is_single_id(self):
        cameras = [{'id': 'cam1'}, {'id': 'cam2'}]

        def fake_get(key, default=None):
            if key in ('motion.frigate_camera_filter', 'mqtt.frigate_camera_filter'):
                return 'front_door'
            return default

        with patch.object(mqtt_runtime_mod.app_config, 'get', side_effect=fake_get):
            self.assertEqual(
                mqtt_runtime_mod._frigate_camera_filter_list(cameras),
                ['front_door'],
            )

    def test_frigate_camera_filter_list_passthrough(self):
        cameras = [{'id': 'a'}]

        def fake_get(key, default=None):
            if key in ('motion.frigate_camera_filter', 'mqtt.frigate_camera_filter'):
                return ['x', 'y']
            return default

        with patch.object(mqtt_runtime_mod.app_config, 'get', side_effect=fake_get):
            self.assertEqual(
                mqtt_runtime_mod._frigate_camera_filter_list(cameras),
                ['x', 'y'],
            )

    def test_frigate_camera_filter_none_uses_all_camera_ids(self):
        cameras = [{'id': 'c1'}, {'id': 'c2'}]

        def fake_get(key, default=None):
            return default

        with patch.object(mqtt_runtime_mod.app_config, 'get', side_effect=fake_get):
            self.assertEqual(
                mqtt_runtime_mod._frigate_camera_filter_list(cameras),
                ['c1', 'c2'],
            )

    def test_frigate_label_filter_scalar_string_is_single_label(self):
        def fake_get(key, default=None):
            if key == 'motion.frigate_label_filter':
                return 'Bird'
            if key == 'mqtt.frigate_label_filter':
                return None
            return default

        with patch.object(mqtt_runtime_mod.app_config, 'get', side_effect=fake_get):
            out = mqtt_runtime_mod._frigate_label_set(
                'motion.frigate_label_filter',
                'mqtt.frigate_label_filter',
                ['bird'],
            )
            self.assertEqual(out, {'Bird'})

    def test_empty_motion_label_filter_stays_empty_wildcard(self):
        def fake_get(key, default=None):
            if key == 'motion.frigate_label_filter':
                return []
            if key == 'mqtt.frigate_label_filter':
                return ['bird', 'Bird']
            return default

        with patch.object(mqtt_runtime_mod.app_config, 'get', side_effect=fake_get):
            out = mqtt_runtime_mod._frigate_label_set(
                'motion.frigate_label_filter',
                'mqtt.frigate_label_filter',
                ['bird'],
            )
            self.assertEqual(out, set())

