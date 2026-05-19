import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

import detection_fusion as detection_fusion_mod
from birdnet_merge_key import reset_birdnet_merge_key_cache_for_tests
from detection_fusion import build_fused_video_detections, skip_frigate_ev_for_standalone
from hypothesis_arbitration import apply_hypothesis_arbitration
from species_normalizer import merge_detections


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


def test_build_fused_video_detections_marks_birdnet_timestamp_parse_failure():
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
            'timestamp': 'broken-iso-value',
        }
    ]
    out = build_fused_video_detections(
        [_base_detection('Great Tit')],
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert out[0]['_birdnet_timestamp_parse_failed'] is True
    assert out[0]['audio_top_species'] == 'Great Tit'
    assert out[0]['audio_top_score'] > 0


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


def test_build_fused_video_detections_birdnet_top_species_tie_is_stable():
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
    base_det = [_base_detection('Great Tit')]
    mqtt_a = [
        {'source': 'birdnet', 'species': 'Blue Tit', 'confidence': 0.7, 'timestamp': end.isoformat()},
        {'source': 'birdnet', 'species': 'Great Tit', 'confidence': 0.7, 'timestamp': end.isoformat()},
    ]
    mqtt_b = list(reversed(mqtt_a))
    out_a = build_fused_video_detections(
        base_det,
        mqtt_a,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    out_b = build_fused_video_detections(
        base_det,
        mqtt_b,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert out_a[0]['audio_top_species'] == out_b[0]['audio_top_species']


def test_build_fused_video_detections_marks_learned_fusion_failure_status(monkeypatch):
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
        'detection.use_learned_fusion': True,
        'detection.fusion_alpha': 0.6,
        'detection.fusion_model_path': '/tmp/fusion-test.onnx',
    })

    class _BoomScorer:
        def __init__(self, model_path=None):
            self.model_path = model_path

        def score(self, features):
            raise RuntimeError('boom')

    monkeypatch.setattr(detection_fusion_mod, 'FusionScorer', _BoomScorer)
    out = build_fused_video_detections(
        [_base_detection('Great Tit')],
        [],
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert out[0]['_fusion_scorer_status'] == 'error'
    assert out[0]['_fusion_model_path'] == '/tmp/fusion-test.onnx'
    assert out[0]['_fusion_score'] == 0.0


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
    assert out[0]['primary_provider'] == 'frigate'
    assert out[0]['primary_signal'] == 'frigate_standalone'
    assert out[0]['threshold_path'] == 'frigate_standalone_min_score'
    assert out[0]['fallback_used'] is True
    assert out[0]['fallback_reason'] == 'frigate_standalone'
    assert out[0]['yolo_track_present'] is False


def test_frigate_standalone_keeps_rows_frameless_to_avoid_stuck_overlay_bbox():
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
            'frigate_bbox_norm': [0.1, 0.2, 0.55, 0.65],
            '_frigate_has_geometry': True,
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
    assert not out[0].get('frames')


def test_frigate_standalone_requires_geometry_by_default():
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
            '_frigate_has_geometry': False,
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


def test_frigate_standalone_accepts_session_trigger_snapshot_without_geometry():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=20)
    cfg = DummyConfig({
        'video.cameras': [
            {'id': 'Forest', 'stream_name': 'Forest'},
            {'id': 'BirdBox', 'stream_name': 'BirdBox'},
        ],
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.36,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_min_score': 0.45,
        'detection.frigate_standalone_missing_score_fallback': 0.0,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt = [
        {
            'source': 'frigate',
            'camera': 'Forest',
            'species': 'Hooded Crow',
            'label': 'bird',
            'sub_label': 'Hooded Crow',
            'confidence': 0.66,
            'timestamp': (start + timedelta(seconds=1)).isoformat(),
            '_frigate_has_geometry': False,
            '_session_trigger_snapshot': True,
        },
    ]
    out = build_fused_video_detections(
        [],
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
        triggered_camera='Forest',
    )
    assert len(out) == 1
    assert out[0]['decision_kind'] == 'frigate_standalone'
    assert out[0]['species_name'] == 'Hooded Crow'


def test_frigate_standalone_ignores_stale_events_outside_age_window():
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
        'detection.frigate_standalone_max_event_age_seconds': 8,
        'detection.frigate_standalone_missing_score_fallback': 0.0,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    mqtt = [
        {
            'source': 'frigate',
            'species': 'bird',
            'label': 'bird',
            'confidence': 0.92,
            'timestamp': (start - timedelta(seconds=20)).isoformat(),
            '_frigate_has_geometry': True,
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


def test_frigate_standalone_injects_when_yolo_only_generic():
    """YOLO accepted only generic Bird — still add Frigate standalone rows (regression guard)."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=20)
    base_cfg = {
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.34,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_when_no_accepted_species': True,
        'detection.frigate_standalone_min_score': 0.48,
        'detection.frigate_standalone_missing_score_fallback': 0.0,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    }
    video = [
        {
            **_base_detection('Bird'),
            'confidence': 0.44,
            'classifier_confidence': None,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_bird',
            'start_time': 0.0,
            'end_time': 18.0,
        },
    ]
    mqtt = [
        {
            'source': 'frigate',
            'species': 'Great Tit',
            'label': 'Great Tit',
            'confidence': 0.88,
            'timestamp': (start + timedelta(seconds=2)).isoformat(),
        },
    ]
    out_on = build_fused_video_detections(
        video,
        mqtt,
        start_time=start,
        end_time=end,
        app_config=DummyConfig(base_cfg),
    )
    kinds_on = {str(d.get('decision_kind') or '') for d in out_on}
    assert 'frigate_standalone' in kinds_on or any(
        str(d.get('species_name') or '') == 'Great Tit' for d in out_on
    )

    cfg_off = DummyConfig({**base_cfg, 'detection.frigate_standalone_when_no_accepted_species': False})
    out_off = build_fused_video_detections(
        video,
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg_off,
    )
    kinds_off = {str(d.get('decision_kind') or '') for d in out_off}
    assert 'frigate_standalone' not in kinds_off


def test_frigate_standalone_injects_when_yolo_has_no_accepted_species():
    """If YOLO returns only review/generic rows, Frigate standalone must still rescue clip."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=20)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.34,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_when_no_accepted_species': True,
        'detection.frigate_standalone_min_score': 0.48,
        'detection.frigate_standalone_missing_score_fallback': 0.0,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    video = [
        {
            **_base_detection('Great Tit'),
            'confidence': 0.39,
            'classifier_confidence': 0.17,
            'decision_kind': 'review_only_generic',
            'decision_reason': 'weak_generic_review',
            'accepted': False,
            'visit_eligible': False,
            'start_time': 0.0,
            'end_time': 18.0,
        },
    ]
    mqtt = [
        {
            'source': 'frigate',
            'species': 'Great Tit',
            'label': 'Great Tit',
            'confidence': 0.82,
            'timestamp': (start + timedelta(seconds=2)).isoformat(),
        },
    ]

    out = build_fused_video_detections(
        video,
        mqtt,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert any(str(d.get('decision_kind') or '') == 'frigate_standalone' for d in out)


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


def test_fusion_birdnet_locale_resolved_via_scientific_name(monkeypatch):
    """Русское common в MQTT + Parus major → тот же ключ, что у YOLO Great Tit (SQLite каталог)."""
    reset_birdnet_merge_key_cache_for_tests()
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.execute(
            'CREATE TABLE species_taxon ('
            'id INTEGER PRIMARY KEY, taxon_key TEXT UNIQUE NOT NULL, '
            'scientific_name TEXT, common_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT \'active\')'
        )
        conn.execute(
            'CREATE TABLE species_alias ('
            'id INTEGER PRIMARY KEY, alias TEXT NOT NULL UNIQUE, '
            'alias_key TEXT NOT NULL, taxon_id INTEGER NOT NULL)'
        )
        conn.execute(
            "INSERT INTO species_taxon (id, taxon_key, scientific_name, common_name) "
            "VALUES (1, 'pm', 'Parus major', 'Great Tit')"
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(detection_fusion_mod, 'sqlite_path_for_birdnet_merge', lambda: path)

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
                'species': 'Большая синица',
                'common_name': 'Большая синица',
                'scientific_name': 'Parus major',
                'confidence': 0.92,
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
        assert out[0]['audio_evidence'] == 'support'
        assert out[0]['audio_support_species'] == 'Great Tit'
        assert out[0]['_birdnet_prior'] > 0
    finally:
        reset_birdnet_merge_key_cache_for_tests()
        try:
            os.unlink(path)
        except OSError:
            pass


def test_arbitration_keeps_strongest_species_with_multi_source_consensus():
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
    detections = [
        {
            **_base_detection('Great Tit'),
            'confidence': 0.68,
            'classifier_confidence': 0.68,
            'start_time': 0.0,
            'end_time': 8.0,
            'decision_kind': 'accepted_species',
        },
        {
            **_base_detection('Blue Tit'),
            'track_id': 2,
            'confidence': 0.54,
            'classifier_confidence': 0.54,
            'start_time': 1.0,
            'end_time': 7.5,
            'decision_kind': 'accepted_species',
        },
    ]
    mqtt_events = [
        {
            'source': 'birdnet',
            'species': 'Great Tit',
            'confidence': 0.93,
            'timestamp': end.isoformat(),
        },
        {
            'source': 'frigate',
            'camera': 'cam-a',
            'species': 'Great Tit',
            'confidence': 0.81,
            'timestamp': end.isoformat(),
        },
        {
            'source': 'frigate',
            'camera': 'cam-b',
            'species': 'Great Tit',
            'confidence': 0.79,
            'timestamp': end.isoformat(),
        },
    ]
    out = build_fused_video_detections(
        detections,
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert len(out) == 1
    assert out[0]['species_name'] == 'Great Tit'
    assert out[0]['decision_reason'] == 'species_won_by_multi_source_consensus'
    assert out[0].get('arbitration_reason') == 'species_won_by_multi_source_consensus'
    assert out[0].get('detection_provider') == 'arbitration'
    assert out[0].get('arbitrated_primary_provider') == 'yolo'


def test_arbitration_absorbs_generic_bird_into_species_with_cross_source_support():
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
    detections = [
        {
            **_base_detection('Bird'),
            'confidence': 0.56,
            'classifier_confidence': None,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_bird',
            'start_time': 0.0,
            'end_time': 10.0,
        },
        {
            **_base_detection('Great Tit'),
            'track_id': 2,
            'confidence': 0.51,
            'classifier_confidence': 0.18,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_detector_generic',
            'start_time': 1.0,
            'end_time': 9.0,
        },
    ]
    mqtt_events = [
        {
            'source': 'birdnet',
            'species': 'Great Tit',
            'confidence': 0.91,
            'timestamp': end.isoformat(),
        },
        {
            'source': 'frigate',
            'camera': 'cam-a',
            'species': 'Great Tit',
            'confidence': 0.78,
            'timestamp': end.isoformat(),
        },
        {
            'source': 'frigate',
            'camera': 'cam-b',
            'species': 'Great Tit',
            'confidence': 0.76,
            'timestamp': end.isoformat(),
        },
    ]
    out = build_fused_video_detections(
        detections,
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert len(out) == 1
    assert out[0]['species_name'] == 'Great Tit'
    assert out[0].get('arbitration_reason') == 'absorbed_generic_into_species'


def test_arbitration_downgrades_weak_conflict_to_single_generic_review():
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
    detections = [
        {
            **_base_detection('Great Tit'),
            'confidence': 0.51,
            'classifier_confidence': 0.19,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_detector_generic',
            'start_time': 0.0,
            'end_time': 8.0,
        },
        {
            **_base_detection('Blue Tit'),
            'track_id': 2,
            'confidence': 0.5,
            'classifier_confidence': 0.18,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_detector_generic',
            'start_time': 0.5,
            'end_time': 8.5,
        },
    ]
    out = build_fused_video_detections(
        detections,
        [],
        start_time=start,
        end_time=end,
        app_config=cfg,
    )
    assert len(out) == 1
    assert out[0]['species_name'] == 'Bird'
    assert out[0]['decision_reason'] == 'downgraded_to_generic_due_to_conflict'
    assert out[0]['decision_kind'] == 'review_only_generic'
    assert out[0]['visit_eligible'] is False
    assert out[0]['outcome_bucket'] == 'review_only'


def test_learned_fusion_preserves_arbitration_trace(monkeypatch):
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=30)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.05,
        'detection.use_learned_fusion': True,
        'detection.fusion_alpha': 0.6,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [['cam-a', 'cam-b']],
        'processor.multi_camera_confidence_boost': 0.05,
    })
    detections = [
        {
            **_base_detection('Bird'),
            'confidence': 0.56,
            'classifier_confidence': None,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_bird',
            'start_time': 0.0,
            'end_time': 10.0,
        },
        {
            **_base_detection('Great Tit'),
            'track_id': 2,
            'confidence': 0.51,
            'classifier_confidence': 0.18,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_detector_generic',
            'start_time': 1.0,
            'end_time': 9.0,
        },
    ]
    mqtt_events = [
        {
            'source': 'birdnet',
            'species': 'Great Tit',
            'confidence': 0.91,
            'timestamp': end.isoformat(),
        },
        {
            'source': 'frigate',
            'camera': 'cam-a',
            'species': 'Great Tit',
            'confidence': 0.78,
            'timestamp': end.isoformat(),
        },
        {
            'source': 'frigate',
            'camera': 'cam-b',
            'species': 'Great Tit',
            'confidence': 0.76,
            'timestamp': end.isoformat(),
        },
    ]

    class _Scorer:
        def __init__(self, model_path=None):
            self.model_path = model_path

        def score(self, features):
            return 0.8

    monkeypatch.setattr(detection_fusion_mod, 'FusionScorer', _Scorer)

    out = build_fused_video_detections(
        detections,
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )

    assert len(out) == 1
    assert 'learned' in out[0]['_fusion_used']
    assert 'absorbed_generic_into_species' in out[0]['_fusion_used']


def test_arbitration_downgrades_strong_unresolved_conflict_to_review_only():
    rows = [
        {
            **_base_detection('Great Tit'),
            'track_id': 1,
            'accepted': True,
            'visit_eligible': True,
            'confidence': 0.63,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_detector_generic',
            'start_time': 0.0,
            'end_time': 6.0,
        },
        {
            **_base_detection('Blue Tit'),
            'track_id': 2,
            'accepted': True,
            'visit_eligible': True,
            'confidence': 0.63,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_detector_generic',
            'start_time': 0.2,
            'end_time': 6.2,
        },
    ]
    out = apply_hypothesis_arbitration(rows)
    assert len(out) == 1
    assert out[0]['species_name'] == 'Bird'
    assert out[0]['decision_kind'] == 'review_only_generic'
    assert out[0]['decision_reason'] == 'downgraded_to_generic_due_to_strong_conflict'
    assert out[0]['outcome_bucket'] == 'review_only'


def test_arbitration_keeps_visually_anchored_species_when_gap_is_small():
    rows = [
        {
            **_base_detection('Great Tit'),
            'track_id': 1,
            'accepted': True,
            'visit_eligible': True,
            'confidence': 0.67,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_detector_generic',
            'start_time': 0.0,
            'end_time': 6.0,
            'detection_provider': 'yolo',
            'contributing_providers': ['yolo'],
            'classifier_confidence': 0.20,
        },
        {
            **_base_detection('Blue Tit'),
            'track_id': -2,
            'accepted': True,
            'visit_eligible': True,
            'confidence': 0.53,
            'decision_kind': 'frigate_standalone',
            'decision_reason': 'frigate_standalone',
            'start_time': 0.2,
            'end_time': 6.2,
            'detection_provider': 'frigate',
            'contributing_providers': ['frigate'],
            'classifier_confidence': None,
        },
    ]
    out = apply_hypothesis_arbitration(rows)
    assert len(out) == 1
    assert out[0]['species_name'] == 'Great Tit'
    assert out[0]['decision_reason'] == 'species_kept_by_visual_anchor'


def test_arbitration_absorbs_generic_bird_into_strong_frigate_species():
    rows = [
        {
            **_base_detection('Bird'),
            'track_id': -2,
            'species_name': 'Bird',
            'species': 'Bird',
            'confidence': 0.76,
            'start_time': 0.0,
            'end_time': 48.2,
            'detection_provider': 'frigate',
            'decision_kind': 'frigate_standalone',
            'decision_reason': 'frigate_standalone',
            'classifier_confidence': None,
        },
        {
            **_base_detection('Eurasian Jay'),
            'track_id': -1,
            'species_name': 'Eurasian Jay',
            'species': 'Eurasian Jay',
            'confidence': 0.84,
            'start_time': 0.0,
            'end_time': 48.2,
            'detection_provider': 'frigate',
            'decision_kind': 'frigate_standalone',
            'decision_reason': 'frigate_standalone',
            'classifier_confidence': None,
        },
    ]

    out = apply_hypothesis_arbitration(rows)

    assert len(out) == 1
    assert out[0]['species_name'] == 'Eurasian Jay'
    assert out[0]['decision_reason'] == 'absorbed_generic_into_frigate_species'
    assert out[0]['decision_reason_before_arbitration'] == 'frigate_standalone'
    assert 'absorbed_generic_into_frigate_species' in out[0].get('_fusion_used', '')


def test_arbitration_keeps_generic_bird_when_frigate_species_is_weak():
    rows = [
        {
            **_base_detection('Bird'),
            'track_id': -2,
            'species_name': 'Bird',
            'species': 'Bird',
            'confidence': 0.76,
            'start_time': 0.0,
            'end_time': 48.2,
            'detection_provider': 'frigate',
            'decision_kind': 'frigate_standalone',
            'decision_reason': 'frigate_standalone',
            'classifier_confidence': None,
        },
        {
            **_base_detection('Eurasian Jay'),
            'track_id': -1,
            'species_name': 'Eurasian Jay',
            'species': 'Eurasian Jay',
            'confidence': 0.61,
            'start_time': 0.0,
            'end_time': 48.2,
            'detection_provider': 'frigate',
            'decision_kind': 'frigate_standalone',
            'decision_reason': 'frigate_standalone',
            'classifier_confidence': None,
        },
    ]

    out = apply_hypothesis_arbitration(rows)

    assert len(out) == 2
    assert sorted(row['species_name'] for row in out) == ['Bird', 'Eurasian Jay']


def test_build_fused_video_detections_absorbs_generic_bird_into_frigate_species():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=48)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 45,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.05,
        'detection.frigate_standalone_when_no_yolo': True,
        'detection.frigate_standalone_notify': True,
        'detection.frigate_standalone_min_score': 0.4,
        'detection.frigate_standalone_missing_score_fallback': 0.68,
        'processor.multi_camera_groups': [],
        'video.cameras': [],
    })
    mqtt_events = [
        {
            'source': 'frigate',
            'species': 'Eurasian Jay',
            'confidence': 0.86296875,
            'timestamp': start.isoformat(),
        },
        {
            'source': 'frigate',
            'species': 'Bird',
            'confidence': 0.76171875,
            'timestamp': start.isoformat(),
        },
    ]

    out = build_fused_video_detections(
        [],
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
    )

    assert len(out) == 1
    assert out[0]['species_name'] == 'Eurasian Jay'
    assert out[0]['decision_reason'] == 'absorbed_generic_into_frigate_species'
    assert out[0]['decision_reason_before_arbitration'] == 'frigate_standalone'
    assert out[0]['detection_provider'] == 'frigate'


def test_build_fused_video_detections_keeps_fragmented_generic_bird_visits_separate():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=60)
    cfg = DummyConfig({
        'detection.merge_window_seconds': 5,
        'detection.dedup_window_seconds': 10,
        'detection.one_per_species': True,
        'detection.source_priority': ['yolo', 'frigate'],
        'detection.cross_source_confidence_bonus': 0.0,
        'detection.min_confidence_to_store': 0.05,
        'processor.birdnet_mqtt_half_life_hours': 6.0,
        'processor.multi_camera_groups': [],
    })
    detections = [
        {
            **_base_detection('Bird'),
            'track_id': 1,
            'confidence': 0.61,
            'classifier_confidence': 0.17,
            'start_time': 1.0,
            'end_time': 3.0,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_bird',
            'frames': [{'t': 1.0}],
        },
        {
            **_base_detection('Bird'),
            'track_id': 2,
            'confidence': 0.73,
            'classifier_confidence': 0.31,
            'start_time': 31.0,
            'end_time': 39.0,
            'decision_kind': 'accepted_generic',
            'decision_reason': 'fallback_bird',
            'frames': [{'t': 31.0}],
        },
    ]

    out = build_fused_video_detections(
        detections,
        [],
        start_time=start,
        end_time=end,
        app_config=cfg,
    )

    assert len(out) == 2
    assert [(row['track_id'], row['start_time'], row['end_time']) for row in out] == [
        (1, 1.0, 3.0),
        (2, 31.0, 39.0),
    ]


def test_fusion_clamp_non_species_respects_slack():
    rows = [
        {
            'decision_kind': 'accepted_generic',
            '_pre_fusion_confidence': 0.40,
            'confidence': 0.50,
        }
    ]
    cfg = DummyConfig({'detection.fusion_non_species_confidence_slack': 0.02})
    out = detection_fusion_mod._clamp_fusion_confidence_inflation(rows, cfg)
    assert abs(out[0]['confidence'] - 0.42) < 1e-9
    assert out[0].get('_fusion_clamped') is True


def test_fusion_clamp_non_species_zero_slack_legacy():
    rows = [
        {
            'decision_kind': 'accepted_generic',
            '_pre_fusion_confidence': 0.40,
            'confidence': 0.50,
        }
    ]
    cfg = DummyConfig({'detection.fusion_non_species_confidence_slack': 0.0})
    out = detection_fusion_mod._clamp_fusion_confidence_inflation(rows, cfg)
    assert abs(out[0]['confidence'] - 0.40) < 1e-9


def test_fusion_clamp_skips_accepted_species():
    rows = [
        {
            'decision_kind': 'accepted_species',
            '_pre_fusion_confidence': 0.40,
            'confidence': 0.90,
        }
    ]
    out = detection_fusion_mod._clamp_fusion_confidence_inflation(
        rows,
        DummyConfig({'detection.fusion_non_species_confidence_slack': 0.0}),
    )
    assert abs(out[0]['confidence'] - 0.90) < 1e-9


def test_merge_adjacent_yolo_fragments_same_species_small_gap():
    rows = [
        {
            'track_id': 10,
            'species_name': 'Great Tit',
            'confidence': 0.61,
            'start_time': 0.0,
            'end_time': 2.0,
            'detection_provider': 'yolo',
            'detector_confidence': 0.62,
            'frames': [{'t': 1.9, 'bbox': [0.10, 0.10, 0.30, 0.30]}],
        },
        {
            'track_id': 11,
            'species_name': 'Great Tit',
            'confidence': 0.64,
            'start_time': 2.4,
            'end_time': 4.0,
            'detection_provider': 'yolo',
            'detector_confidence': 0.66,
            'frames': [{'t': 2.4, 'bbox': [0.11, 0.10, 0.31, 0.30]}],
        },
    ]
    cfg = DummyConfig({
        'detection.track_fragment_merge_enabled': True,
        'detection.track_fragment_merge_gap_sec': 1.2,
        'detection.track_fragment_merge_min_iou': 0.08,
        'detection.track_fragment_merge_max_center_dist': 0.18,
    })
    out = detection_fusion_mod._merge_adjacent_yolo_fragments(rows, cfg)
    assert len(out) == 1
    assert out[0]['track_fragment_merged'] is True
    assert out[0]['merged_track_ids'] == [10, 11]
    assert float(out[0]['end_time']) == 4.0


def test_merge_adjacent_yolo_fragments_keeps_distant_rows_separate():
    rows = [
        {
            'track_id': 10,
            'species_name': 'Great Tit',
            'confidence': 0.61,
            'start_time': 0.0,
            'end_time': 2.0,
            'detection_provider': 'yolo',
            'frames': [{'t': 1.9, 'bbox': [0.10, 0.10, 0.30, 0.30]}],
        },
        {
            'track_id': 11,
            'species_name': 'Great Tit',
            'confidence': 0.64,
            'start_time': 2.4,
            'end_time': 4.0,
            'detection_provider': 'yolo',
            'frames': [{'t': 2.4, 'bbox': [0.70, 0.70, 0.90, 0.90]}],
        },
    ]
    cfg = DummyConfig({
        'detection.track_fragment_merge_enabled': True,
        'detection.track_fragment_merge_gap_sec': 1.2,
        'detection.track_fragment_merge_min_iou': 0.08,
        'detection.track_fragment_merge_max_center_dist': 0.18,
    })
    out = detection_fusion_mod._merge_adjacent_yolo_fragments(rows, cfg)
    assert len(out) == 2


def test_merge_detections_conflict_result_stable_across_mqtt_order():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=12)
    yolo = [
        {
            "species_name": "Blue Tit",
            "species": "Blue Tit",
            "confidence": 0.6,
            "start_time": 0.0,
            "end_time": 6.0,
            "detection_provider": "yolo",
            "source": "video",
            "track_id": 1,
            "decision_kind": "accepted_species",
            "classifier_confidence": 0.6,
        },
        {
            "species_name": "Great Tit",
            "species": "Great Tit",
            "confidence": 0.6,
            "start_time": 0.0,
            "end_time": 6.0,
            "detection_provider": "yolo",
            "source": "video",
            "track_id": 2,
            "decision_kind": "accepted_species",
            "classifier_confidence": 0.6,
        },
    ]
    mqtt_a = [
        {"source": "frigate", "species": "Great Tit", "camera": "a", "timestamp": end.isoformat(), "confidence": 0.8},
        {"source": "frigate", "species": "Blue Tit", "camera": "b", "timestamp": end.isoformat(), "confidence": 0.8},
    ]
    mqtt_b = list(reversed(mqtt_a))
    out_a = merge_detections(
        yolo,
        mqtt_a,
        start,
        end,
        merge_window_seconds=5,
        dedup_window_seconds=45,
        one_per_species=True,
        source_priority=["yolo", "frigate"],
    )
    out_b = merge_detections(
        yolo,
        mqtt_b,
        start,
        end,
        merge_window_seconds=5,
        dedup_window_seconds=45,
        one_per_species=True,
        source_priority=["yolo", "frigate"],
    )
    assert [row["species_name"] for row in out_a] == [row["species_name"] for row in out_b]
    assert len(out_a) == len(out_b) == 1


def test_skip_frigate_ev_for_standalone_respects_config():
    cfg = DummyConfig({'detection.frigate_standalone_skip_labels': ['person', 'human']})
    assert skip_frigate_ev_for_standalone({'label': 'Person'}, cfg)
    assert skip_frigate_ev_for_standalone({'species': 'human'}, cfg)
    assert not skip_frigate_ev_for_standalone({'label': 'crow'}, cfg)
    assert not skip_frigate_ev_for_standalone({'label': 'person'}, DummyConfig({}))


def test_frigate_standalone_requires_blind_confirmation_by_default():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=6)
    cfg = DummyConfig(
        {
            "detection.merge_window_seconds": 5,
            "detection.dedup_window_seconds": 45,
            "detection.one_per_species": True,
            "detection.source_priority": ["yolo", "frigate"],
            "detection.cross_source_confidence_bonus": 0.0,
            "detection.min_confidence_to_store": 0.05,
            "detection.frigate_standalone_when_no_yolo": True,
            "detection.frigate_standalone_when_no_accepted_species": True,
            "detection.frigate_standalone_require_blind_yolo": True,
            "detection.frigate_standalone_min_score": 0.4,
            "detection.frigate_standalone_missing_score_fallback": 0.7,
            "processor.multi_camera_groups": [],
        }
    )
    mqtt_events = [
        {
            "source": "frigate",
            "species": "Great Tit",
            "label": "bird",
            "camera": "BirdBox",
            "confidence": 0.8,
            "timestamp": end.isoformat(),
            "_session_trigger_snapshot": True,
        }
    ]
    out = build_fused_video_detections(
        [],
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
        yolo_blind_confirmed=False,
    )
    assert out == []


def test_frigate_standalone_allowed_when_blind_confirmed():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=30)
    cfg = DummyConfig(
        {
            "detection.merge_window_seconds": 5,
            "detection.dedup_window_seconds": 45,
            "detection.one_per_species": True,
            "detection.source_priority": ["yolo", "frigate"],
            "detection.cross_source_confidence_bonus": 0.0,
            "detection.min_confidence_to_store": 0.05,
            "detection.frigate_standalone_when_no_yolo": True,
            "detection.frigate_standalone_when_no_accepted_species": True,
            "detection.frigate_standalone_require_blind_yolo": True,
            "detection.frigate_standalone_min_score": 0.4,
            "detection.frigate_standalone_missing_score_fallback": 0.7,
            "processor.multi_camera_groups": [],
        }
    )
    mqtt_events = [
        {
            "source": "frigate",
            "species": "Great Tit",
            "label": "bird",
            "camera": "BirdBox",
            "confidence": 0.8,
            "timestamp": end.isoformat(),
            "_session_trigger_snapshot": True,
        }
    ]
    out = build_fused_video_detections(
        [],
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
        yolo_blind_confirmed=True,
    )
    assert len(out) == 1
    assert out[0]["detection_provider"] == "frigate"
    assert out[0]["source_reason"] == "blind_yolo"
    assert out[0]["confidence_level"] == "low"


def test_frigate_standalone_forced_after_timeout_without_blind_confirmation():
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=32)
    cfg = DummyConfig(
        {
            "detection.merge_window_seconds": 5,
            "detection.dedup_window_seconds": 45,
            "detection.one_per_species": True,
            "detection.source_priority": ["yolo", "frigate"],
            "detection.cross_source_confidence_bonus": 0.0,
            "detection.min_confidence_to_store": 0.05,
            "detection.frigate_standalone_when_no_yolo": True,
            "detection.frigate_standalone_when_no_accepted_species": True,
            "detection.frigate_standalone_require_blind_yolo": True,
            "detection.frigate_standalone_force_after_no_yolo_seconds": 10,
            "detection.frigate_standalone_min_score": 0.4,
            "detection.frigate_standalone_missing_score_fallback": 0.7,
            "processor.multi_camera_groups": [],
        }
    )
    mqtt_events = [
        {
            "source": "frigate",
            "species": "Great Tit",
            "label": "bird",
            "camera": "BirdBox",
            "confidence": 0.8,
            "timestamp": end.isoformat(),
            "_session_trigger_snapshot": True,
        }
    ]
    out = build_fused_video_detections(
        [],
        mqtt_events,
        start_time=start,
        end_time=end,
        app_config=cfg,
        yolo_blind_confirmed=False,
        yolo_blind_score=0.2,
    )
    assert len(out) == 1
    assert out[0]["detection_provider"] == "frigate"
