"""Collect weighted hints from MQTT / config (hints only — no recording gate)."""

from __future__ import annotations

from typing import Iterable, Mapping

from classifier_hints.types import HintPayload, HintSource


def _norm(value: str | None) -> str:
    return str(value or "").strip().lower()


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _frigate_species(ev: dict) -> str:
    # Prefer Frigate sub_label (named species) over generic label=bird.
    for key in ("species", "sub_label", "label"):
        raw = str(ev.get(key) or "").strip()
        if raw and raw.lower() not in {"bird", "unknown"}:
            return raw
    return ""


def collect_birdnet_hints(mqtt_events: Iterable[dict], *, default_weight: float) -> list[HintPayload]:
    best: dict[str, float] = {}
    for ev in mqtt_events or []:
        if _norm(ev.get("source")) not in {"birdnet", "birdnet_mqtt"}:
            continue
        species = _norm(ev.get("species"))
        if not species or species == "unknown":
            continue
        score = _safe_float(ev.get("confidence"))
        if score > best.get(species, 0.0):
            best[species] = score
    return [
        HintPayload(
            source=HintSource.BIRDNET,
            species=species,
            weight=default_weight,
            score=score,
            raw_confidence=score,
        )
        for species, score in best.items()
    ]


def collect_frigate_hints(
    mqtt_events: Iterable[dict],
    *,
    default_weight: float,
    camera_id: str | None = None,
) -> list[HintPayload]:
    best: dict[str, tuple[str, float]] = {}
    camera_key = _norm(camera_id)
    for ev in mqtt_events or []:
        if _norm(ev.get("source")) != "frigate":
            continue
        event_camera = _norm(ev.get("camera"))
        if camera_key and event_camera and event_camera != camera_key:
            continue
        species = _frigate_species(ev)
        if not species:
            continue
        key = _norm(species)
        score = _safe_float(ev.get("confidence"), 0.7)
        prev = best.get(key)
        if prev is None or score > prev[1]:
            best[key] = (species, score)
    return [
        HintPayload(
            source=HintSource.FRIGATE_LABEL,
            species=display,
            weight=default_weight,
            score=score,
            raw_confidence=score,
        )
        for display, score in best.values()
    ]


def collect_ebird_regional_hints(
    app_config: Mapping,
    *,
    default_weight: float,
) -> list[HintPayload]:
    raw = app_config.get("processor.regional_species") or []
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[HintPayload] = []
    for item in raw:
        species = str(item or "").strip()
        if not species:
            continue
        out.append(
            HintPayload(
                source=HintSource.EBIRD_REGIONAL,
                species=species,
                weight=default_weight,
                score=1.0,
                raw_confidence=1.0,
            )
        )
    return out


def collect_hints(
    *,
    camera_id: str | None,
    track: dict | None,
    mqtt_events: Iterable[dict],
    app_config: Mapping,
    window_sec: float = 0.0,
) -> list[HintPayload]:
    """Aggregate external hint signals for one scoring pass."""
    del track, window_sec  # reserved for repeat-confirmation (#641 follow-up)
    from classifier_hints.config import load_hint_weights

    weights = load_hint_weights(app_config)
    hints: list[HintPayload] = []
    hints.extend(collect_birdnet_hints(mqtt_events, default_weight=weights.birdnet_prior))
    hints.extend(collect_frigate_hints(mqtt_events, default_weight=weights.frigate_label, camera_id=camera_id))
    hints.extend(collect_ebird_regional_hints(app_config, default_weight=weights.regional_prior))
    return hints
