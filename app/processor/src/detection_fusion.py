"""Shared fusion layer for live runtime and track regeneration."""
from __future__ import annotations

from typing import Iterable
from datetime import datetime, timezone

from multi_camera_confidence import apply_multi_camera_confidence_boost
from species_normalizer import merge_detections, normalize
from fusion_model import FusionScorer


def _species_mapping(app_config) -> dict:
    return app_config.get('detection.species_mapping') or {}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _aggregate_birdnet_scores(
    mqtt_events: Iterable[dict],
    *,
    end_time,
    species_mapping: dict,
    half_life_hours: float = 6.0,
) -> dict[str, dict]:
    scores: dict[str, dict] = {}
    end_dt = end_time
    if getattr(end_dt, 'tzinfo', None) is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    half_life_hours = max(0.1, float(half_life_hours or 6.0))
    for ev in mqtt_events or []:
        if str((ev or {}).get('source') or '').strip().lower() != 'birdnet':
            continue
        raw_species = (
            ev.get('species')
            or ev.get('common_name')
            or ev.get('label')
            or ''
        )
        species = normalize(str(raw_species), species_mapping)
        if not species or species.lower() == 'unknown':
            continue
        conf = max(0.0, min(1.0, _safe_float(ev.get('confidence'), 0.0)))
        ts = ev.get('timestamp')
        age_hours = 0.0
        if ts:
            try:
                parsed = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age_hours = max(0.0, (end_dt - parsed).total_seconds() / 3600.0)
            except Exception:
                age_hours = 0.0
        weighted = conf * (0.5 ** (age_hours / half_life_hours))
        bucket = scores.setdefault(
            species,
            {
                'score': 0.0,
                'support_count': 0,
                'max_confidence': 0.0,
            },
        )
        bucket['score'] += weighted
        bucket['support_count'] += 1
        bucket['max_confidence'] = max(bucket['max_confidence'], conf)
    return scores


def _attach_audio_evidence(
    detections: list[dict],
    mqtt_events: Iterable[dict],
    *,
    end_time,
    app_config,
) -> list[dict]:
    species_mapping = _species_mapping(app_config)
    birdnet_scores = _aggregate_birdnet_scores(
        mqtt_events,
        end_time=end_time,
        species_mapping=species_mapping,
        half_life_hours=_safe_float(
            app_config.get('processor.birdnet_mqtt_half_life_hours') or 6.0,
            6.0,
        ),
    )
    if not birdnet_scores:
        for d in detections:
            d['_birdnet_prior'] = 0.0
            d['audio_evidence'] = 'none'
        return detections

    top_species, top_bucket = max(
        birdnet_scores.items(),
        key=lambda item: (
            _safe_float(item[1].get('score'), 0.0),
            int(item[1].get('support_count') or 0),
        ),
    )
    top_score = _safe_float(top_bucket.get('score'), 0.0)
    for d in detections:
        species_name = normalize(
            str(d.get('species_name') or d.get('species') or ''),
            species_mapping,
        )
        support = birdnet_scores.get(species_name)
        prior = _safe_float((support or {}).get('score'), 0.0)
        d['_birdnet_prior'] = prior
        if support:
            d['audio_evidence'] = 'support'
            d['audio_support_count'] = int(support.get('support_count') or 0)
            d['audio_support_species'] = species_name
            continue
        if top_score >= 0.35 and top_species != species_name:
            d['audio_evidence'] = 'conflict'
            d['audio_conflict_species'] = top_species
            d['audio_conflict_score'] = top_score
        else:
            d['audio_evidence'] = 'none'
    return detections


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
        try:
            row['_pre_fusion_confidence'] = float(row.get('confidence') or 0.0)
        except (TypeError, ValueError):
            row['_pre_fusion_confidence'] = 0.0
        rows.append(row)
    return rows


def _clamp_fusion_confidence_inflation(detections: list[dict]) -> list[dict]:
    """Prevent Frigate/BirdNET/learned fusion from rescuing weak non-species tracks."""
    for d in detections:
        kind = str(d.get('decision_kind') or '').strip().lower()
        if kind == 'accepted_species':
            continue
        try:
            base = float(d.get('_pre_fusion_confidence') or 0.0)
            cur = float(d.get('confidence') or 0.0)
        except (TypeError, ValueError):
            continue
        if cur > base:
            d['confidence'] = float(base)
            d['_fusion_clamped'] = True
    return detections


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
    fused = _attach_audio_evidence(
        fused,
        mqtt_events,
        end_time=end_time,
        app_config=app_config,
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
    fused = _clamp_fusion_confidence_inflation(fused)
    min_conf_store = float(
        app_config.get('detection.min_confidence_to_store') or 0.05
    )
    return [
        d
        for d in fused
        if float(d.get('confidence') or 0.0) >= min_conf_store
    ]
