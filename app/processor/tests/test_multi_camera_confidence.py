"""Tests for multi-camera Frigate confidence boost (#153)."""
import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from multi_camera_confidence import apply_multi_camera_confidence_boost


class TestMultiCameraConfidence(unittest.TestCase):
    def test_no_groups_noop(self):
        dets = [{'species_name': 'Blue Tit', 'confidence': 0.5}]
        ev = []
        cfg = {'processor.multi_camera_groups': []}
        out = apply_multi_camera_confidence_boost(dets, ev, cfg)
        self.assertEqual(out[0]['confidence'], 0.5)

    def test_boost_when_two_cameras_same_group(self):
        mqtt = [
            {
                'source': 'frigate',
                'camera': 'A',
                'species': 'Blue Tit',
            },
            {
                'source': 'frigate',
                'camera': 'B',
                'species': 'Blue Tit',
            },
        ]
        dets = [{'species_name': 'Blue Tit', 'confidence': 0.4}]
        cfg = {
            'processor.multi_camera_groups': [['A', 'B']],
            'processor.multi_camera_confidence_boost': 0.1,
        }
        out = apply_multi_camera_confidence_boost(dets, mqtt, cfg)
        self.assertAlmostEqual(out[0]['confidence'], 0.5)


if __name__ == '__main__':
    unittest.main()
