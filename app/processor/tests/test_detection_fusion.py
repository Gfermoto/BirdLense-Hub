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


def test_frigate_standalone_disabled_keeps_empty_without_yolo():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=20)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.36,
        'detection.frigate_standalone_when_no_yolo': False,
        'detection.frigate_standalone_min_score': 0.62,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt = [
        {
            'source': 'frigate',
            'species': 'bird',
            'label': 'bird',
            'confidence': 0.9,
            'timestamp': (start + timedelta(seconds=2)).isoformat(),
        },
    ]
    out = build_fused_video_detections(
        [],
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert out == []


def test_frigate_standalone_creates_row_when_no_yolo():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=20)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.36,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_min_score': 0.62,
        'detection.frigate_standalone_missing_score_fallback': 0.0,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt = [
        {
            'source': 'frigate',
            'species': 'bird',
            'label': 'bird',
            'confidence': 0.88,
            'timestamp': (start + timedelta(seconds=2)).isoformat(),
        },
    ]
    out = build_fused_video_detections(
        [],
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert len(out) == 1
    assert out[0]['species_name'] == 'Bird'
    assert out[0]['decision_kind'] == 'frigate_standalone'
    assert out[0].get('frigate_standalone') is True


def test_frigate_standalone_uses_missing_score_fallback():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=15)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.36,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_min_score': 0.60,
        'detection.frigate_standalone_missing_score_fallback': 0.72,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt = [
        {
            'source': 'frigate',
            'species': 'bird',
            'label': 'bird',
            'confidence': 0.0,
            'timestamp': (start + timedelta(seconds=1)).isoformat(),
        },
    ]
    out = build_fused_video_detections(
        [],
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert len(out) == 1
    assert out[0]['species_name'] == 'Bird'


def test_frigate_standalone_excluded_label_no_telegram_eligible():
    """Cat/dog (merge suppressed): save visit when YOLO empty; not eligible for Telegram."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=25)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.34,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_excluded_min_score': 0.0,
        'detection.frigate_standalone_excluded_missing_score_fallback': 0.58,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt = [
        {
            'source': 'frigate',
            'species': 'cat',
            'label': 'cat',
            'confidence': 0.0,
            'timestamp': (start + timedelta(seconds=3)).isoformat(),
            '_frigate_merge_suppressed': True,
        },
    ]
    out = build_fused_video_detections(
        [],
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert len(out) == 1
    assert out[0]['species_name'] == 'Cat'
    assert out[0]['decision_kind'] == 'frigate_standalone_excluded'
    assert out[0].get('notification_eligible') is False


def test_merge_skips_suppressed_frigate_for_yolo_promotion():
    """Suppressed Frigate must not merge into an existing YOLO row."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=20)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.05,
        'detection.min_confidence_to_store': 0.34,
        'detection.frigate_standalone_when_no_yolo': False,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    yolo = {
        'track_id': 1,
        'species_name': 'Great Tit',
        'confidence': 0.55,
        'start_time': 0.0,
        'end_time': 8.0,
        'detection_provider': 'yolo',
        'decision_reason': 'accepted_species',
        'decision_kind': 'accepted_species',
    }
    mqtt = [
        {
            'source': 'frigate',
            'species': 'cat',
            'label': 'cat',
            'confidence': 0.95,
            'timestamp': (start + timedelta(seconds=2)).isoformat(),
            '_frigate_merge_suppressed': True,
        },
    ]
    out = build_fused_video_detections(
        [yolo],
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert len(out) == 1
    assert out[0]['species_name'] == 'Great Tit'


def test_frigate_standalone_drops_wrong_camera_when_hub_scoped():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=20)
    cfg = DummyConfig({
        'video.cameras': [{'id': 'feeder', 'stream_name': 'feeder'}],
        'motion.frigate_camera_filter': [],
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.36,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_min_score': 0.62,
        'detection.frigate_standalone_missing_score_fallback': 0.0,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt = [
        {
            'source': 'frigate',
            'camera': 'garage',
            'species': 'bird',
            'label': 'bird',
            'confidence': 0.88,
            'timestamp': (start + timedelta(seconds=2)).isoformat(),
        },
    ]
    out = build_fused_video_detections(
        [],
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert out == []


def test_frigate_standalone_keeps_matching_camera_when_hub_scoped():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=20)
    cfg = DummyConfig({
        'video.cameras': [{'id': 'feeder', 'stream_name': 'feeder'}],
        'motion.frigate_camera_filter': [],
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.36,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_min_score': 0.62,
        'detection.frigate_standalone_missing_score_fallback': 0.0,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt = [
        {
            'source': 'frigate',
            'camera': 'feeder',
            'species': 'bird',
            'label': 'bird',
            'confidence': 0.88,
            'timestamp': (start + timedelta(seconds=2)).isoformat(),
        },
    ]
    out = build_fused_video_detections(
        [],
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert len(out) == 1
    assert out[0]['decision_kind'] == 'frigate_standalone'
