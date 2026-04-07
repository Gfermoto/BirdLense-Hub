"""Lower classifier thresholds for species recently reported by BirdNET MQTT (#129)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def merge_birdnet_mqtt_bias_into_overrides(
    base_overrides: dict[str, float],
    app_config,
    mqtt_aggregator,
) -> dict[str, float]:
    """Return copy of base_overrides with extra per-species thresholds for recent BirdNET MQTT.

    Manual ``processor.species_confidence_overrides`` and eBird auto keys in ``base_overrides``
    are preserved (this function only adds keys not already present).

    Disabled when ``processor.birdnet_mqtt_auto_confidence`` is false or broker/aggregator missing.
    """
    out = dict(base_overrides)
    try:
        enabled = bool(app_config.get('processor.birdnet_mqtt_auto_confidence', False))
    except Exception:
        enabled = False
    if not enabled or mqtt_aggregator is None:
        return out

    try:
        window = float(app_config.get('processor.birdnet_mqtt_bias_window_seconds', 120))
    except (TypeError, ValueError):
        window = 120.0
    window = max(10.0, min(window, 3600.0))
    try:
        prior_window_hours = float(
            app_config.get('processor.birdnet_mqtt_prior_window_hours', 24)
        )
    except (TypeError, ValueError):
        prior_window_hours = 24.0
    try:
        prior_ttl_hours = float(
            app_config.get('processor.birdnet_mqtt_prior_ttl_hours', 25)
        )
    except (TypeError, ValueError):
        prior_ttl_hours = 25.0
    try:
        half_life_hours = float(
            app_config.get('processor.birdnet_mqtt_prior_half_life_hours', 6)
        )
    except (TypeError, ValueError):
        half_life_hours = 6.0
    try:
        min_prior_confidence = float(
            app_config.get('processor.birdnet_mqtt_prior_min_confidence', 0.0)
        )
    except (TypeError, ValueError):
        min_prior_confidence = 0.0

    try:
        base = float(app_config.get('processor.min_confidence_to_process', 0.3))
    except (TypeError, ValueError):
        base = 0.3
    try:
        delta = float(app_config.get('processor.birdnet_mqtt_bias_delta', 0.05))
    except (TypeError, ValueError):
        delta = 0.05
    try:
        floor_v = float(app_config.get('processor.birdnet_mqtt_bias_floor', 0.05))
    except (TypeError, ValueError):
        floor_v = 0.05

    delta = max(0.0, min(delta, 0.5))
    base = max(0.01, min(base, 0.99))
    floor_v = max(0.01, min(floor_v, base))
    auto_val = max(floor_v, base - delta)
    auto_val = max(0.01, min(auto_val, 0.99))

    now = datetime.now(timezone.utc)
    low = now - timedelta(seconds=window)
    high = now

    from species_normalizer import normalize

    species_mapping = app_config.get('detection.species_mapping') or {}
    adjusted = 0
    try:
        prior_scores = mqtt_aggregator.get_birdnet_prior_scores(
            now=now,
            window_hours=prior_window_hours,
            ttl_hours=prior_ttl_hours,
            half_life_hours=half_life_hours,
            min_confidence=min_prior_confidence,
        )
    except Exception as e:
        logger.warning('BirdNET MQTT bias: get_birdnet_prior_scores failed: %s', e)
        prior_scores = {}

    if not prior_scores:
        try:
            events = mqtt_aggregator.get_events_in_window(
                low, high, window_seconds=0, lookback_seconds=window
            )
        except Exception as e:
            logger.warning('BirdNET MQTT bias: get_events_in_window failed: %s', e)
            return out
        for ev in events or []:
            if (ev or {}).get('source') != 'birdnet':
                continue
            raw = (ev.get('species') or '').strip()
            if not raw or raw.lower() == 'unknown':
                continue
            prior_scores[raw] = {'score': 1.0}

    for raw_name, meta in prior_scores.items():
        bl = normalize(raw_name, species_mapping)
        if not bl or bl.lower() == 'unknown':
            continue
        if bl in out:
            continue
        try:
            raw_score = float((meta or {}).get('score') or 0.0)
        except (TypeError, ValueError):
            raw_score = 0.0
        strength = max(0.0, min(raw_score, 1.0))
        adjusted_val = max(floor_v, base - (delta * strength))
        adjusted_val = max(0.01, min(adjusted_val, 0.99))
        out[bl] = adjusted_val
        adjusted += 1

    if adjusted:
        logger.info(
            'BirdNET MQTT auto-confidence: +%d species (recent_window=%.0fs prior_window=%.1fh '
            'ttl=%.1fh half_life=%.1fh base=%.3f delta=%.3f)',
            adjusted,
            window,
            prior_window_hours,
            prior_ttl_hours,
            half_life_hours,
            base,
            delta,
        )
    return out
