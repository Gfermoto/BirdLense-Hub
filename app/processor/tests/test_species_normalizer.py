"""Tests for species_normalizer merge_detections (Bird filter)."""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)
from species_normalizer import merge_detections


class TestMergeBirdFilter(unittest.TestCase):
    """Bird = unknown when alone; dropped when any other species present."""

    def setUp(self):
        self.video_start = datetime.now(timezone.utc)
        self.video_end = self.video_start + timedelta(seconds=60)

    def test_bird_alone_kept(self):
        """Bird alone → keep (unknown species)."""
        yolo = [{'species_name': 'Bird', 'confidence': 0.9, 'start_time': 0, 'end_time': 5}]
        mqtt = []
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Bird')

    def test_bird_with_other_dropped(self):
        """Bird + Northern Cardinal → drop Bird, keep Northern Cardinal."""
        yolo = [
            {'species_name': 'Bird', 'confidence': 0.9, 'start_time': 0, 'end_time': 5},
            {'species_name': 'Northern Cardinal', 'confidence': 0.5, 'start_time': 2, 'end_time': 7},
        ]
        mqtt = []
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        names = [d['species_name'] for d in result]
        self.assertNotIn('Bird', names)
        self.assertIn('Northern Cardinal', names)

    def test_bird_from_mqtt_dropped_when_yolo_has_other(self):
        """MQTT Bird + YOLO Northern Cardinal → drop Bird."""
        yolo = [{'species_name': 'Northern Cardinal', 'confidence': 0.6, 'start_time': 0, 'end_time': 5}]
        mqtt = [{'species': 'Bird', 'confidence': 0.95, 'timestamp': self.video_start.isoformat()}]
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        names = [d['species_name'] for d in result]
        self.assertNotIn('Bird', names)
        self.assertIn('Northern Cardinal', names)

    def test_bird_frames_transferred_to_other(self):
        """Bird (YOLO, has frames) + Northern Cardinal (MQTT, no frames) → keep NC with frames."""
        yolo = [
            {'species_name': 'Bird', 'confidence': 0.9, 'start_time': 0, 'end_time': 5,
             'frames': [{'t': 1.0, 'bbox': [0.1, 0.2, 0.3, 0.4]}], 'track_id': 1},
        ]
        mqtt = [{'species': 'Northern Cardinal', 'confidence': 0.8, 'timestamp': self.video_start.isoformat()}]
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Northern Cardinal')
        self.assertIn('frames', result[0])
        self.assertEqual(len(result[0]['frames']), 1)

    def test_frigate_event_outside_video_window_is_skipped(self):
        """Frigate event far before the clip must not create a negative-duration detection."""
        yolo = []
        mqtt = [{
            'species': 'Eurasian Jay',
            'source': 'frigate',
            'confidence': 0.82,
            'timestamp': (self.video_start - timedelta(seconds=40)).isoformat(),
        }]

        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)

        self.assertEqual(result, [])

    def test_species_mapping_normalizes_mqtt_before_merge(self):
        yolo = [{
            'species_name': 'Garrulus glandarius (Eurasian Jay)',
            'confidence': 0.61,
            'start_time': 10,
            'end_time': 18,
            'detection_provider': 'yolo',
        }]
        mqtt = [{
            'species': 'Eurasian Jay',
            'source': 'frigate',
            'confidence': 0.83,
            'timestamp': (self.video_start + timedelta(seconds=12)).isoformat(),
        }]

        result = merge_detections(
            yolo,
            mqtt,
            self.video_start,
            self.video_end,
            species_mapping={'eurasian_jay': 'Garrulus glandarius (Eurasian Jay)'},
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Garrulus glandarius (Eurasian Jay)')
        self.assertEqual(result[0]['detection_provider'], 'yolo')
        self.assertEqual(result[0]['contributing_providers'], ['frigate', 'yolo'])

    def test_one_per_species_preserves_all_contributing_providers(self):
        yolo = [{
            'species_name': 'Eurasian Jay',
            'confidence': 0.61,
            'start_time': 10,
            'end_time': 18,
            'detection_provider': 'yolo',
            'contributing_providers': ['yolo', 'birdnet_mqtt'],
        }]
        mqtt = [{
            'species': 'Eurasian Jay',
            'source': 'frigate',
            'confidence': 0.83,
            'timestamp': (self.video_start + timedelta(seconds=12)).isoformat(),
        }]

        result = merge_detections(
            yolo,
            mqtt,
            self.video_start,
            self.video_end,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]['contributing_providers'],
            ['birdnet_mqtt', 'frigate', 'yolo'],
        )

    def test_two_mqtt_only_events_merge_when_one_per_species(self):
        """MQTT-only buckets must not overwrite prior same-species events (#226 review)."""
        video_end = self.video_start + timedelta(seconds=120)
        yolo = []
        mqtt = [
            {
                'species': 'Eurasian Jay',
                'source': 'frigate',
                'confidence': 0.7,
                'timestamp': (self.video_start + timedelta(seconds=10)).isoformat(),
            },
            {
                'species': 'Eurasian Jay',
                'source': 'frigate',
                'confidence': 0.8,
                'timestamp': (self.video_start + timedelta(seconds=100)).isoformat(),
            },
        ]
        result = merge_detections(
            yolo,
            mqtt,
            self.video_start,
            video_end,
            dedup_window_seconds=45,
            one_per_species=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Eurasian Jay')
        self.assertLessEqual(result[0]['start_time'], 10)
        self.assertGreaterEqual(result[0]['end_time'], 95)

    def test_two_mqtt_only_separate_when_not_one_per_species(self):
        video_end = self.video_start + timedelta(seconds=120)
        yolo = []
        mqtt = [
            {
                'species': 'Eurasian Jay',
                'source': 'frigate',
                'confidence': 0.7,
                'timestamp': (self.video_start + timedelta(seconds=10)).isoformat(),
            },
            {
                'species': 'Eurasian Jay',
                'source': 'frigate',
                'confidence': 0.8,
                'timestamp': (self.video_start + timedelta(seconds=100)).isoformat(),
            },
        ]
        result = merge_detections(
            yolo,
            mqtt,
            self.video_start,
            video_end,
            dedup_window_seconds=45,
            one_per_species=False,
        )
        self.assertEqual(len(result), 2)
