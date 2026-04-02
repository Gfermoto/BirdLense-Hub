"""Tests for track_regenerator model path handling."""

import os
import sys
import unittest
from types import ModuleType
from unittest.mock import patch


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from track_regenerator import build_detection_pipeline, _dedupe_track_detections


class _FakeConfig:
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


class TestTrackRegeneratorModelPath(unittest.TestCase):
    """Track regen must honor configured NCNN directories."""

    def test_single_stage_keeps_directory_model_path(self):
        """A configured NCNN directory must not fall back to yolov8n.pt."""
        cfg = _FakeConfig({
            'processor.detection_strategy': 'single_stage',
            'processor.models.single_stage': '/tmp/nabirds_yolov8n_ncnn_model',
            'processor.single_stage_coco_animals_only_auto': True,
            'processor.max_record_seconds': 30,
            'processor.max_inactive_seconds': 2,
            'processor.min_track_duration': 1,
            'processor.min_confidence_to_process': 0.4,
            'processor.post_record_seconds': 0,
        })

        fake_detection_strategy = ModuleType('detection_strategy')
        fake_detection_strategy.SingleStageStrategy = object()
        fake_detection_strategy.TwoStageStrategy = object()
        fake_frame_processor = ModuleType('frame_processor')
        fake_frame_processor.FrameProcessor = object()
        fake_decision_maker = ModuleType('decision_maker')
        fake_decision_maker.DecisionMaker = object()
        fake_ebird = ModuleType('ebird_regional_confidence')
        fake_ebird.merge_species_confidence_overrides_with_ebird_top = object()

        with patch.dict(
            sys.modules,
            {
                'detection_strategy': fake_detection_strategy,
                'frame_processor': fake_frame_processor,
                'decision_maker': fake_decision_maker,
                'ebird_regional_confidence': fake_ebird,
            },
        ), patch('track_regenerator.os.path.isfile', return_value=False), patch(
            'track_regenerator.os.path.isdir',
            side_effect=lambda path: path == '/tmp/nabirds_yolov8n_ncnn_model',
        ), patch(
            'detection_strategy.SingleStageStrategy',
        ) as single_stage_cls, patch(
            'detection_strategy.TwoStageStrategy',
        ), patch(
            'ebird_regional_confidence.merge_species_confidence_overrides_with_ebird_top',
            return_value={},
        ), patch(
            'frame_processor.FrameProcessor',
            return_value='frame_processor',
        ), patch(
            'decision_maker.DecisionMaker',
            return_value='decision_maker',
        ):
            frame_processor, decision_maker = build_detection_pipeline(
                cfg,
                strategy_override='single_stage',
                for_track_regen=True,
            )

        self.assertEqual(frame_processor, 'frame_processor')
        self.assertEqual(decision_maker, 'decision_maker')
        single_stage_cls.assert_called_once()
        self.assertEqual(
            single_stage_cls.call_args.kwargs['model_path'],
            '/tmp/nabirds_yolov8n_ncnn_model',
        )

    def test_regional_species_override_is_honored_for_track_regen(self):
        """An explicit local scope must bypass ignore_regional reset."""
        cfg = _FakeConfig({
            'processor.detection_strategy': 'single_stage',
            'processor.models.single_stage': '/tmp/nabirds_yolov8n_ncnn_model',
            'processor.single_stage_coco_animals_only_auto': True,
            'processor.track_regen_ignore_regional_species': True,
            'processor.max_record_seconds': 30,
            'processor.max_inactive_seconds': 2,
            'processor.min_track_duration': 1,
            'processor.min_confidence_to_process': 0.4,
            'processor.post_record_seconds': 0,
        })

        fake_detection_strategy = ModuleType('detection_strategy')
        fake_detection_strategy.SingleStageStrategy = object()
        fake_detection_strategy.TwoStageStrategy = object()
        fake_frame_processor = ModuleType('frame_processor')
        fake_frame_processor.FrameProcessor = object()
        fake_decision_maker = ModuleType('decision_maker')
        fake_decision_maker.DecisionMaker = object()
        fake_ebird = ModuleType('ebird_regional_confidence')
        fake_ebird.merge_species_confidence_overrides_with_ebird_top = object()

        with patch.dict(
            sys.modules,
            {
                'detection_strategy': fake_detection_strategy,
                'frame_processor': fake_frame_processor,
                'decision_maker': fake_decision_maker,
                'ebird_regional_confidence': fake_ebird,
            },
        ), patch('track_regenerator.os.path.isfile', return_value=False), patch(
            'track_regenerator.os.path.isdir',
            side_effect=lambda path: path == '/tmp/nabirds_yolov8n_ncnn_model',
        ), patch(
            'detection_strategy.SingleStageStrategy',
        ) as single_stage_cls, patch(
            'detection_strategy.TwoStageStrategy',
        ), patch(
            'ebird_regional_confidence.merge_species_confidence_overrides_with_ebird_top',
            return_value={},
        ), patch(
            'frame_processor.FrameProcessor',
            return_value='frame_processor',
        ), patch(
            'decision_maker.DecisionMaker',
            return_value='decision_maker',
        ):
            build_detection_pipeline(
                cfg,
                strategy_override='single_stage',
                for_track_regen=True,
                regional_species_override=['Eurasian Jay', 'Great Tit'],
            )

        self.assertEqual(
            single_stage_cls.call_args.kwargs['regional_species'],
            ['Eurasian Jay', 'Great Tit'],
        )

    def test_min_center_dist_override_is_forwarded(self):
        """Track regen override must relax edge filtering when requested."""
        cfg = _FakeConfig({
            'processor.detection_strategy': 'single_stage',
            'processor.models.single_stage': '/tmp/nabirds_yolov8n_ncnn_model',
            'processor.single_stage_coco_animals_only_auto': True,
            'processor.max_record_seconds': 30,
            'processor.max_inactive_seconds': 2,
            'processor.min_track_duration': 1,
            'processor.min_confidence_to_process': 0.4,
            'processor.post_record_seconds': 0,
        })

        fake_detection_strategy = ModuleType('detection_strategy')
        fake_detection_strategy.SingleStageStrategy = object()
        fake_detection_strategy.TwoStageStrategy = object()
        fake_frame_processor = ModuleType('frame_processor')
        fake_frame_processor.FrameProcessor = object()
        fake_decision_maker = ModuleType('decision_maker')
        fake_decision_maker.DecisionMaker = object()
        fake_ebird = ModuleType('ebird_regional_confidence')
        fake_ebird.merge_species_confidence_overrides_with_ebird_top = object()

        with patch.dict(
            sys.modules,
            {
                'detection_strategy': fake_detection_strategy,
                'frame_processor': fake_frame_processor,
                'decision_maker': fake_decision_maker,
                'ebird_regional_confidence': fake_ebird,
            },
        ), patch('track_regenerator.os.path.isfile', return_value=False), patch(
            'track_regenerator.os.path.isdir',
            side_effect=lambda path: path == '/tmp/nabirds_yolov8n_ncnn_model',
        ), patch(
            'detection_strategy.SingleStageStrategy',
        ) as single_stage_cls, patch(
            'detection_strategy.TwoStageStrategy',
        ), patch(
            'ebird_regional_confidence.merge_species_confidence_overrides_with_ebird_top',
            return_value={},
        ), patch(
            'frame_processor.FrameProcessor',
            return_value='frame_processor',
        ), patch(
            'decision_maker.DecisionMaker',
            return_value='decision_maker',
        ):
            build_detection_pipeline(
                cfg,
                strategy_override='single_stage',
                for_track_regen=True,
                min_center_dist_override=0.02,
            )

        self.assertEqual(
            single_stage_cls.call_args.kwargs['min_center_dist'],
            0.02,
        )


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

