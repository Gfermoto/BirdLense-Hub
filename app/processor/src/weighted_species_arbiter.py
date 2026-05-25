"""Weighted arbitration layer using BirdNET/regional/multi-camera priors."""

from __future__ import annotations

from typing import Iterable


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _norm(value: str | None) -> str:
    return str(value or "").strip().lower()


def _species_key(row: dict) -> str:
    return _norm(str(row.get("species_name") or row.get("species") or ""))


def _birdnet_event_index(mqtt_events: Iterable[dict]) -> dict[str, float]:
    best: dict[str, float] = {}
    for ev in mqtt_events or []:
        if _norm(ev.get("source")) not in {"birdnet", "birdnet_mqtt"}:
            continue
        key = _norm(ev.get("species"))
        if not key:
            continue
        score = _safe_float(ev.get("confidence"))
        if score > best.get(key, 0.0):
            best[key] = score
    return best


def apply_weighted_species_arbiter(
    rows: list[dict],
    *,
    mqtt_events: Iterable[dict],
    app_config,
) -> list[dict]:
    if not rows:
        return rows
    if not bool(app_config.get("detection.weighted_arbiter_enabled", True)):
        return rows

    try:
        w_conf = float(
            app_config.get("detection.weighted_arbiter_conf_weight") or 0.55
        )
        w_detector = float(
            app_config.get("detection.weighted_arbiter_detector_weight") or 0.15
        )
        w_classifier = float(
            app_config.get("detection.weighted_arbiter_classifier_weight") or 0.12
        )
        w_birdnet = float(
            app_config.get("detection.weighted_arbiter_birdnet_weight") or 0.08
        )
        w_regional = float(
            app_config.get("detection.weighted_arbiter_regional_weight") or 0.05
        )
        w_multi = float(
            app_config.get("detection.weighted_arbiter_multicamera_weight") or 0.05
        )
    except (TypeError, ValueError):
        return rows

    regional = {
        _norm(v)
        for v in (app_config.get("processor.regional_species") or [])
        if _norm(v)
    }
    birdnet_idx = _birdnet_event_index(mqtt_events)
    out: list[dict] = []
    for row in rows:
        species = _species_key(row)
        detector_conf = _safe_float(
            row.get("detector_confidence"),
            _safe_float(row.get("detector_conf")),
        )
        classifier_conf = _safe_float(
            row.get("classifier_confidence"),
            _safe_float(row.get("classifier_conf")),
        )
        base_conf = _safe_float(row.get("confidence"))
        birdnet_prior = max(
            _safe_float(row.get("_birdnet_prior")),
            birdnet_idx.get(species, 0.0),
        )
        regional_prior = 1.0 if (species and species in regional) else 0.0
        multi_support = (
            1.0
            if bool(row.get("_multi_camera_support"))
            else min(1.0, _safe_float(row.get("_multi_camera_count")))
        )

        weighted = (
            (base_conf * w_conf)
            + (detector_conf * w_detector)
            + (classifier_conf * w_classifier)
            + (birdnet_prior * w_birdnet)
            + (regional_prior * w_regional)
            + (multi_support * w_multi)
        )
        weighted = max(0.0, min(weighted, 1.0))
        new_row = dict(row)
        new_row["_weighted_arbiter_score"] = round(weighted, 6)
        # Conservative blend to avoid abrupt behavior changes.
        new_row["confidence"] = round((0.7 * base_conf) + (0.3 * weighted), 6)
        out.append(new_row)
    return out
