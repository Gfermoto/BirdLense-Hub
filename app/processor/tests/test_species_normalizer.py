"""Tests for species_normalizer merge_detections and Frigate promotion."""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)
from species_normalizer import merge_detections


class TestMergeDetections(unittest.TestCase):
    def setUp(self):
        self.video_start = datetime.now(timezone.utc)
        self.video_end = self.video_start + timedelta(seconds=60)

    def test_bird_alone_kept(self):
        yolo = [{'species_name': 'Bird', 'confidence': 0.9, 'start_time': 0, 'end_time': 5}]
        result = merge_detections(yolo, [], self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Bird')

    def test_bird_can_coexist_with_other_species(self):
        """Без поля classifier / accepted_species второй ряд не считается «уверенным видом»."""
        yolo = [
            {'species_name': 'Bird', 'confidence': 0.9, 'start_time': 0, 'end_time': 5},
            {
                'species_name': 'Northern Cardinal',
                'confidence': 0.5,
                'start_time': 2,
                'end_time': 7,
            },
        ]
        result = merge_detections(yolo, [], self.video_start, self.video_end)
        names = [d['species_name'] for d in result]
        self.assertIn('Bird', names)
        self.assertIn('Northern Cardinal', names)

    def test_generic_bird_absorbed_when_overlapping_classified_jay(self):
        yolo = [
            {
                'species_name': 'Bird',
                'confidence': 0.45,
                'start_time': 0,
                'end_time': 40,
                'detection_provider': 'yolo',
                'decision_reason': 'fallback_bird',
            },
            {
                'species_name': 'Eurasian Jay',
                'confidence': 0.62,
                'start_time': 5,
                'end_time': 35,
                'detection_provider': 'yolo',
                'classifier_confidence': 0.55,
                'decision_kind': 'accepted_species',
            },
        ]
        result = merge_detections(yolo, [], self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Eurasian Jay')
        self.assertIn('absorbed_generic_bird', result[0].get('_fusion_used', ''))

    def test_frigate_does_not_create_detection_without_yolo(self):
        mqtt = [{
            'species': 'Northern Cardinal',
            'source': 'frigate',
            'confidence': 0.95,
            'timestamp': self.video_start.isoformat(),
        }]
        result = merge_detections([], mqtt, self.video_start, self.video_end)
        self.assertEqual(result, [])

    def test_birdnet_does_not_create_detection_without_yolo(self):
        mqtt = [{
            'species': 'Northern Cardinal',
            'source': 'birdnet',
            'confidence': 0.95,
            'timestamp': self.video_start.isoformat(),
        }]
        result = merge_detections([], mqtt, self.video_start, self.video_end)
        self.assertEqual(result, [])

    def test_frigate_merges_into_same_species_yolo_detection(self):
        yolo = [{
            'species_name': 'Northern Cardinal',
            'confidence': 0.6,
            'start_time': 0,
            'end_time': 5,
            'detection_provider': 'yolo',
        }]
        mqtt = [{
            'species': 'Northern Cardinal',
            'source': 'frigate',
            'confidence': 0.95,
            'timestamp': self.video_start.isoformat(),
        }]
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Northern Cardinal')
        self.assertEqual(result[0]['contributing_providers'], ['frigate', 'yolo'])

    def test_frigate_promotes_generic_bird_track(self):
        yolo = [{
            'species_name': 'Bird',
            'confidence': 0.6,
            'start_time': 0,
            'end_time': 5,
            'detection_provider': 'yolo',
            'decision_reason': 'fallback_bird',
            'detector_label': 'Bird',
            'frames': [{'t': 1.0, 'bbox': [0.1, 0.2, 0.3, 0.4]}],
            'track_id': 1,
        }]
        mqtt = [{
            'species': 'Northern Cardinal',
            'label': 'bird',
            'source': 'frigate',
            'confidence': 0.95,
            'timestamp': self.video_start.isoformat(),
        }]
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Northern Cardinal')
        self.assertEqual(result[0]['decision_reason'], 'promoted_by_frigate')
        self.assertEqual(result[0]['track_id'], 1)
        self.assertEqual(len(result[0]['frames']), 1)

    def test_frigate_event_outside_video_window_is_skipped(self):
        yolo = [{
            'species_name': 'Bird',
            'confidence': 0.6,
            'start_time': 10,
            'end_time': 15,
            'detection_provider': 'yolo',
            'decision_reason': 'fallback_bird',
            'detector_label': 'Bird',
        }]
        mqtt = [{
            'species': 'Eurasian Jay',
            'source': 'frigate',
            'confidence': 0.82,
            'timestamp': (self.video_start - timedelta(seconds=40)).isoformat(),
        }]
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Bird')

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
        self.assertEqual(result[0]['contributing_providers'], ['frigate', 'yolo'])

    def test_one_per_species_preserves_all_contributing_providers(self):
        yolo = [{
            'species_name': 'Eurasian Jay',
            'confidence': 0.61,
            'start_time': 10,
            'end_time': 18,
            'detection_provider': 'yolo',
            'contributing_providers': ['birdnet_mqtt', 'yolo'],
        }]
        mqtt = [{
            'species': 'Eurasian Jay',
            'source': 'frigate',
            'confidence': 0.83,
            'timestamp': (self.video_start + timedelta(seconds=12)).isoformat(),
        }]
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]['contributing_providers'],
            ['birdnet_mqtt', 'frigate', 'yolo'],
        )

    def test_rodent_fallback_is_not_promoted_by_bird_frigate_event(self):
        yolo = [{
            'species_name': 'Rodent',
            'confidence': 0.7,
            'start_time': 0,
            'end_time': 5,
            'detection_provider': 'yolo',
            'decision_reason': 'fallback_rodent',
            'detector_label': 'Rodent',
        }]
        mqtt = [{
            'species': 'Great Tit',
            'label': 'bird',
            'source': 'frigate',
            'confidence': 0.9,
            'timestamp': self.video_start.isoformat(),
        }]
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Rodent')
