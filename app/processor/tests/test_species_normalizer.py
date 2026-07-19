"""Tests for species_normalizer merge_detections and Frigate promotion."""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)
from species_normalizer import merge_detections, normalize


class TestMergeDetections(unittest.TestCase):
    def setUp(self):
        self.video_start = datetime.now(timezone.utc)
        self.video_end = self.video_start + timedelta(seconds=60)

    def test_bird_alone_kept(self):
        yolo = [{'species_name': 'Bird', 'confidence': 0.9, 'start_time': 0, 'end_time': 5}]
        result = merge_detections(yolo, [], self.video_start, self.video_end)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Bird')

    def test_generic_bird_conflict_prefers_specific_species(self):
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
        self.assertIn('Northern Cardinal', names)
        self.assertNotIn('Bird', names)

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
        result = merge_detections(
            yolo, mqtt, self.video_start, self.video_end, frigate_species_authority=True
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Northern Cardinal')
        self.assertEqual(result[0]['decision_reason'], 'promoted_by_frigate')
        self.assertEqual(result[0]['track_id'], 1)
        self.assertEqual(len(result[0]['frames']), 1)

    def test_frigate_promotes_review_only_generic_bird_track(self):
        """Authority on: Frigate sub_label may rewrite generic Bird."""
        yolo = [{
            'species_name': 'Bird',
            'confidence': 0.55,
            'start_time': 0,
            'end_time': 8,
            'detection_provider': 'yolo',
            'decision_reason': 'review_only_generic_bird',
            'detector_label': 'Bird',
            'track_id': 2,
        }]
        mqtt = [{
            'species': 'Great Tit',
            'label': 'bird',
            'source': 'frigate',
            'confidence': 0.88,
            'timestamp': self.video_start.isoformat(),
        }]
        result = merge_detections(
            yolo, mqtt, self.video_start, self.video_end, frigate_species_authority=True
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Great Tit')
        self.assertEqual(result[0]['decision_reason'], 'promoted_by_frigate')
        self.assertEqual(result[0]['decision_kind'], 'accepted_species')

    def test_frigate_promotes_linear_deferred_bird_track(self):
        """Authority on: deferred Bird is promoteable."""
        yolo = [{
            'species_name': 'Bird',
            'confidence': 0.4,
            'start_time': 0,
            'end_time': 6,
            'detection_provider': 'yolo',
            'decision_reason': 'accepted_binary_track_classifier_deferred',
            'decision_kind': 'review_only_generic',
            'detector_label': 'Bird',
            'track_id': 3,
        }]
        mqtt = [{
            'species': 'Hooded Crow',
            'label': 'bird',
            'sub_label': 'Hooded Crow',
            'source': 'frigate',
            'confidence': 0.91,
            'timestamp': self.video_start.isoformat(),
        }]
        result = merge_detections(
            yolo, mqtt, self.video_start, self.video_end, frigate_species_authority=True
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Hooded Crow')
        self.assertEqual(result[0]['decision_kind'], 'accepted_species')
        self.assertEqual(result[0]['outcome_bucket'], 'auto_accept')

    def test_frigate_without_authority_keeps_generic_bird(self):
        """Hub-first default: Frigate is prior only, no species rewrite."""
        yolo = [{
            'species_name': 'Bird',
            'confidence': 0.55,
            'start_time': 0,
            'end_time': 8,
            'detection_provider': 'yolo',
            'decision_reason': 'review_only_generic_bird',
            'detector_label': 'Bird',
            'track_id': 2,
        }]
        mqtt = [{
            'species': 'Great Tit',
            'label': 'bird',
            'source': 'frigate',
            'confidence': 0.88,
            'timestamp': self.video_start.isoformat(),
        }]
        result = merge_detections(yolo, mqtt, self.video_start, self.video_end)
        self.assertEqual(result[0]['species_name'], 'Bird')
        self.assertEqual(result[0].get('frigate_prior_label'), 'Great Tit')
        self.assertNotEqual(result[0].get('decision_reason'), 'promoted_by_frigate')

    def test_conflict_prefers_specific_species_over_generic_bird(self):
        yolo = [{
            'species_name': 'Bird',
            'confidence': 0.85,
            'start_time': 0,
            'end_time': 10,
            'detection_provider': 'yolo',
            'decision_reason': 'fallback_bird',
            'detector_label': 'Bird',
        }]
        mqtt = [{
            'species': 'Great Tit',
            'label': 'bird',
            'source': 'frigate',
            'confidence': 0.9,
            'timestamp': (self.video_start + timedelta(seconds=2)).isoformat(),
        }]
        result = merge_detections(
            yolo, mqtt, self.video_start, self.video_end, frigate_species_authority=True
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Great Tit')
        self.assertEqual(result[0]['decision_reason'], 'promoted_by_frigate')

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

    def test_normalize_supports_scientific_or_common_mapping_keys(self):
        mapping = {
            "Parus major (Great Tit)": "Great Tit",
        }
        self.assertEqual(normalize("Parus major", mapping), "Great Tit")
        self.assertEqual(normalize("great_tit", mapping), "Great Tit")

    def test_mqtt_merge_keeps_raw_aliases_for_audit(self):
        yolo = [{
            'species_name': 'Bird',
            'confidence': 0.58,
            'start_time': 0,
            'end_time': 12,
            'detection_provider': 'yolo',
            'decision_reason': 'fallback_bird',
            'detector_label': 'Bird',
        }]
        mqtt = [{
            'species': 'Parus major',
            'sub_label': 'great_tit',
            'label': 'bird',
            'scientific_name': 'Parus major',
            'source': 'frigate',
            'confidence': 0.91,
            'timestamp': (self.video_start + timedelta(seconds=2)).isoformat(),
        }]
        result = merge_detections(
            yolo,
            mqtt,
            self.video_start,
            self.video_end,
            species_mapping={'Parus major (Great Tit)': 'Great Tit'},
            frigate_species_authority=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Great Tit')
        self.assertIn('Parus major', result[0].get('source_aliases', []))
        self.assertIn('great_tit', result[0].get('source_aliases', []))
        self.assertIn('Parus major', result[0].get('source_scientific_names', []))

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

    def test_equal_rank_conflict_prefers_higher_scored_species(self):
        yolo = [
            {
                'species_name': 'Great Tit',
                'confidence': 0.52,
                'classifier_confidence': 0.49,
                'start_time': 1,
                'end_time': 8,
                'detection_provider': 'yolo',
                'decision_kind': 'accepted_species',
            },
            {
                'species_name': 'Blue Tit',
                'confidence': 0.73,
                'classifier_confidence': 0.69,
                'start_time': 2,
                'end_time': 9,
                'detection_provider': 'yolo',
                'decision_kind': 'accepted_species',
            },
        ]
        result = merge_detections(yolo, [], self.video_start, self.video_end, source_priority=['yolo', 'frigate'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['species_name'], 'Blue Tit')

    def test_equal_rank_conflict_can_be_preserved_for_late_arbitration(self):
        yolo = [
            {
                'species_name': 'Great Tit',
                'confidence': 0.62,
                'classifier_confidence': 0.59,
                'start_time': 1,
                'end_time': 8,
                'detection_provider': 'yolo',
                'decision_kind': 'accepted_species',
            },
            {
                'species_name': 'Blue Tit',
                'confidence': 0.61,
                'classifier_confidence': 0.58,
                'start_time': 2,
                'end_time': 9,
                'detection_provider': 'yolo',
                'decision_kind': 'accepted_species',
            },
        ]
        result = merge_detections(
            yolo,
            [],
            self.video_start,
            self.video_end,
            source_priority=['yolo', 'frigate'],
            preserve_equal_rank_conflicts_for_arbitration=True,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual({row['species_name'] for row in result}, {'Great Tit', 'Blue Tit'})

    def test_one_per_species_keeps_distinct_track_ids(self):
        yolo = [
            {
                'species_name': 'Great Tit',
                'confidence': 0.55,
                'start_time': 0,
                'end_time': 8,
                'track_id': 1,
                'detection_provider': 'yolo',
            },
            {
                'species_name': 'Great Tit',
                'confidence': 0.52,
                'start_time': 20,
                'end_time': 28,
                'track_id': 7,
                'detection_provider': 'yolo',
            },
        ]
        collapsed = merge_detections(
            yolo,
            [],
            self.video_start,
            self.video_end,
            one_per_species=True,
            one_per_species_keep_distinct_tracks=False,
        )
        self.assertEqual(len(collapsed), 1)

        separate = merge_detections(
            yolo,
            [],
            self.video_start,
            self.video_end,
            one_per_species=True,
            one_per_species_keep_distinct_tracks=True,
        )
        self.assertEqual(len(separate), 2)
        self.assertEqual({row['track_id'] for row in separate}, {1, 7})
