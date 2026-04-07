"""Tests for track_regenerator / two-stage detection pipeline wiring."""

import os
import sys
import unittest
from unittest.mock import patch


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

import detection_stack as detection_stack_mod

from track_regenerator import build_detection_pipeline, _dedupe_track_detections


class _FakeConfig:
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def _base_cfg(extra=None):
    base = {
        'processor.detection_strategy': 'two_stage',
        'processor.models.binary': '/tmp/binary_detector.pt',
        'processor.models.classifier': '/tmp/classifier.pt',
        'processor.max_record_seconds': 30,
        'processor.max_inactive_seconds': 2,
        'processor.min_track_duration': 1,
        'processor.min_confidence_to_process': 0.4,
        'processor.post_record_seconds': 0,
        'processor.regional_species': [],
        'processor.track_regen_ignore_regional_species': True,
        'detection.min_confidence_to_store': 0.30,
        'processor.classifier_fallback_bird': True,
        'processor.tracker': 'bytetrack.yaml',
    }
    if extra:
        base.update(extra)
    return base


class TestTrackRegeneratorTwoStage(unittest.TestCase):
    """Track regen delegates to ``build_detection_stack`` (two_stage .pt only)."""

    def test_build_detection_stack_called_for_track_regen(self):
        cfg = _FakeConfig(_base_cfg())
        captured = []

        def _capture(app_config, **kwargs):
            captured.append((app_config, kwargs))
            return 'frame_processor', 'decision_maker', {}

        with patch.object(
            detection_stack_mod,
            'build_detection_stack',
            side_effect=_capture,
        ):
            frame_processor, decision_maker = build_detection_pipeline(
                cfg,
                strategy_override='two_stage',
                for_track_regen=True,
            )

        self.assertEqual(frame_processor, 'frame_processor')
        self.assertEqual(decision_maker, 'decision_maker')
        self.assertEqual(len(captured), 1)
        self.assertIs(captured[0][0], cfg)
        kw = captured[0][1]
        self.assertEqual(kw.get('strategy_override'), 'two_stage')
        self.assertTrue(kw.get('for_track_regen'))
        self.assertFalse(kw.get('warn_two_stage_fallback'))

    def test_regional_species_override_is_forwarded_to_stack(self):
        cfg = _FakeConfig(_base_cfg())
        captured = []

        def _capture(app_config, **kwargs):
            captured.append(kwargs)
            return 'fp', 'dm', {}

        with patch.object(
            detection_stack_mod,
            'build_detection_stack',
            side_effect=_capture,
        ):
            build_detection_pipeline(
                cfg,
                strategy_override='two_stage',
                for_track_regen=True,
                regional_species_override=['Eurasian Jay', 'Great Tit'],
            )

        self.assertEqual(
            captured[0].get('regional_species_override'),
            ['Eurasian Jay', 'Great Tit'],
        )

    def test_min_center_dist_override_is_forwarded_to_stack(self):
        cfg = _FakeConfig(_base_cfg())
        captured = []

        def _capture(app_config, **kwargs):
            captured.append(kwargs)
            return 'fp', 'dm', {}

        with patch.object(
            detection_stack_mod,
            'build_detection_stack',
            side_effect=_capture,
        ):
            build_detection_pipeline(
                cfg,
                strategy_override='two_stage',
                for_track_regen=True,
                min_center_dist_override=0.02,
            )

        self.assertEqual(captured[0].get('min_center_dist_override'), 0.02)


class TestTrackRegeneratorDedup(unittest.TestCase):
    """Track regen must collapse duplicate detections for one track."""

    def test_prefers_specific_species_over_unknown_for_same_track(self):
        detections = [
            {
                'species_name': 'Unknown',
                'start_time': 6.0,
                'end_time': 12.0,
                'confidence': 0.45,
                'track_id': 1,
                'frames': [],
                'detection_provider': 'yolo',
            },
            {
                'species_name': 'Eurasian Jay',
                'start_time': 6.0,
                'end_time': 12.0,
                'confidence': 0.45,
                'track_id': 1,
                'frames': [{'t': 6.0, 'bbox': [0.1, 0.1, 0.2, 0.2]}],
                'detection_provider': 'yolo',
            },
        ]

        deduped = _dedupe_track_detections(detections)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]['species_name'], 'Eurasian Jay')
        self.assertEqual(deduped[0]['track_id'], 1)
        self.assertTrue(deduped[0]['frames'])

    def test_keeps_distinct_tracks_separate(self):
        detections = [
            {
                'species_name': 'Unknown',
                'start_time': 6.0,
                'end_time': 12.0,
                'confidence': 0.45,
                'track_id': 1,
                'frames': [],
                'detection_provider': 'yolo',
            },
            {
                'species_name': 'Eurasian Jay',
                'start_time': 6.0,
                'end_time': 12.0,
                'confidence': 0.45,
                'track_id': 2,
                'frames': [],
                'detection_provider': 'yolo',
            },
        ]

        deduped = _dedupe_track_detections(detections)

        self.assertEqual(len(deduped), 2)

    def test_collapses_same_track_even_with_small_time_drift(self):
        detections = [
            {
                'species_name': 'Unknown',
                'start_time': 6.0,
                'end_time': 12.0,
                'confidence': 0.45,
                'track_id': 1,
                'frames': [],
                'detection_provider': 'yolo',
            },
            {
                'species_name': 'Eurasian Jay',
                'start_time': 6.2,
                'end_time': 11.8,
                'confidence': 0.48,
                'track_id': 1,
                'frames': [],
                'detection_provider': 'yolo',
            },
        ]

        deduped = _dedupe_track_detections(detections)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]['species_name'], 'Eurasian Jay')
