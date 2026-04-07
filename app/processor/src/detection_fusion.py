"""Shared fusion layer for live runtime and track regeneration."""
from __future__ import annotations

from typing import Iterable

from multi_camera_confidence import apply_multi_camera_confidence_boost
from species_normalizer import merge_detections, normalize
from fusion_model import FusionScorer


def _species_mapping(app_config) -> dict:
    return app_config.get('detection.species_mapping') or {}


def prepare_track_results_for_fusion(
    track_results: Iterable[dict],
    app_config,
) -> list[dict]:
    """Normalize DecisionMaker/regen rows into the common video detection shape."""
    species_mapping = _species_mapping(app_config)
    rows: list[dict] = []
    for detection in track_results or []:
        raw_name = (
            detection.get('species_name')
            or detection.get('species')
            or detection.get('name')
            or 'unknown'
        )
        normalized_name = normalize(raw_name, species_mapping)
        row = {
            **detection,
            'species_name': normalized_name,
            'species': normalized_name,
            'source': 'video',
            'detection_provider': (
                detection.get('detection_provider') or 'yolo'
            ),
        }
        rows.append(row)
    return rows


def build_fused_video_detections(
    video_detections: Iterable[dict],
    mqtt_events: Iterable[dict],
    *,
    start_time,
    end_time,
    app_config,
) -> list[dict]:
    """Apply shared production fusion rules to video detections.

    BirdNET is excluded from label creation here; its role is confidence
    biasing before DecisionMaker runs. Frigate remains an auxiliary source
    for promotion/boosts only.
    """
    prepared = prepare_track_results_for_fusion(video_detections, app_config)
    merge_window = app_config.get('detection.merge_window_seconds', 5)
    dedup_window = app_config.get('detection.dedup_window_seconds', 45)
    one_per_species = app_config.get('detection.one_per_species', True)
    source_priority = app_config.get('detection.source_priority') or [
        'yolo',
        'frigate',
    ]
    cross_bonus = float(
        app_config.get('detection.cross_source_confidence_bonus') or 0
    )
    frigate_events = [
        ev
        for ev in (mqtt_events or [])
        if str((ev or {}).get('source') or '').strip().lower() == 'frigate'
    ]
    fused = merge_detections(
        prepared,
        frigate_events,
        start_time,
        end_time,
        merge_window,
        dedup_window,
        one_per_species=one_per_species,
        source_priority=source_priority,
        cross_source_confidence_bonus=cross_bonus,
        species_mapping=_species_mapping(app_config),
    )
    fused = apply_multi_camera_confidence_boost(
        fused,
        frigate_events,
        app_config,
    )
    # Optional learned fusion/calibration step. If enabled, the learned scorer
    # produces a calibrated probability from multimodal features and is blended
    # with the existing rule-based confidence.
    try:
        use_learned = bool(app_config.get('detection.use_learned_fusion') or False)
    except Exception:
        use_learned = False
    if use_learned:
        alpha = float(app_config.get('detection.fusion_alpha') or 0.6)
        model_path = app_config.get('detection.fusion_model_path') or None
        scorer = FusionScorer(model_path=model_path)
        for d in fused:
            # Build a small feature vector from available fields.
            features = {
                'detector_conf': (
                    d.get('detector_confidence')
                    or d.get('detector_conf')
                    or d.get('confidence')
                    or 0.0
                ),
                'classifier_conf': (
                    d.get('classifier_confidence')
                    or d.get('classifier_conf')
                    or d.get('confidence')
                    or 0.0
                ),
                'birdnet_prior': float(d.get('_birdnet_prior') or 0.0),
                'key_frame_score': float(d.get('best_frame_score') or 0.0),
                'key_frame_count': int(d.get('key_frame_count') or 0),
                'multi_camera_count': int(d.get('_multi_camera_count') or 0),
            }
            try:
                fused_score = float(scorer.score(features) or 0.0)
            except Exception:
                fused_score = 0.0
            # blend learned score with existing confidence to be conservative by default
            base_conf = float(d.get('confidence') or 0.0)
            final_conf = alpha * fused_score + (1 - alpha) * base_conf
            d['confidence'] = float(final_conf)
            d['_fusion_used'] = 'learned'
            d['_fusion_score'] = fused_score
    min_conf_store = float(
        app_config.get('detection.min_confidence_to_store') or 0.05
    )
    return [
        d
        for d in fused
        if float(d.get('confidence') or 0.0) >= min_conf_store
    ]
