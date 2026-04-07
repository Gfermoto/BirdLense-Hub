import os
import sys
from datetime import datetime, timedelta, timezone

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from detection_fusion import build_fused_video_detections


class DummyConfig(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def _base_detection(species_name='Great Tit'):
    return {
        'track_id': 1,
        'species_name': species_name,
        'confidence': 0.62,
        'start_time': 0.0,
        'end_time': 5.0,
        'detection_provider': 'yolo',
        'detector_confidence': 0.7,
        'classifier_confidence': 0.62,
        'decision_reason': 'accepted_species',
    }


def test_build_fused_video_detections_marks_birdnet_support():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=30)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.05,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt_events = [
        {
            'source': 'birdnet',
            'species': 'Great Tit',
            'confidence': 0.92,
            'timestamp': end.isoformat(),
        }
    ]
    out = build_fused_video_detections(
        [_base_detection('Great Tit')],
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert out[0]['audio_evidence'] == 'support'
    assert out[0]['audio_support_species'] == 'Great Tit'
    assert out[0]['_birdnet_prior'] > 0


def test_build_fused_video_detections_marks_birdnet_conflict_and_multi_camera_support():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=30)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.05,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [['cam-a', 'cam-b']],
        'processor.multi_camera_confidence_boost': 0.05,
    })
    mqtt_events = [
        {
            'source': 'birdnet',
            'species': 'Blue Tit',
            'confidence': 0.95,
            'timestamp': end.isoformat(),
        },
        {
            'source': 'frigate',
            'camera': 'cam-a',
            'species': 'Great Tit',
            'confidence': 0.8,
            'timestamp': end.isoformat(),
        },
        {
            'source': 'frigate',
            'camera': 'cam-b',
            'species': 'Great Tit',
            'confidence': 0.78,
            'timestamp': end.isoformat(),
        },
    ]
    out = build_fused_video_detections(
        [_base_detection('Great Tit')],
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert out[0]['audio_evidence'] == 'conflict'
    assert out[0]['audio_conflict_species'] == 'Blue Tit'
    assert out[0]['_multi_camera_count'] == 2
    assert out[0]['_multi_camera_support'] is True
