"""Blend classifier hints into fusion rows (scoring only)."""

from __future__ import annotations

from typing import Iterable, Mapping

from classifier_hints.collectors import collect_hints
from classifier_hints.config import hints_enabled, load_hint_weights
from classifier_hints.types import HintPayload, HintSource, HintTraceEntry


def _norm(value: str | None) -> str:
    return str(value or "").strip().lower()


def _species_key(row: dict) -> str:
    return _norm(str(row.get("species_name") or row.get("species") or ""))


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _hint_index(hints: Iterable[HintPayload]) -> dict[str, list[HintPayload]]:
    out: dict[str, list[HintPayload]] = {}
    for hint in hints or []:
        key = _norm(hint.species)
        if not key:
            continue
        out.setdefault(key, []).append(hint)
    return out


def _max_hint_score(hints_for_species: list[HintPayload], source: HintSource) -> float:
    scores = [h.score for h in hints_for_species if h.source == source]
    return max(scores) if scores else 0.0


_GENERIC_SPECIES = frozenset({"", "bird", "unknown", "unknown bird", "unidentified"})


def _best_named_frigate_hint(hints: Iterable[HintPayload]) -> HintPayload | None:
    best: HintPayload | None = None
    for hint in hints or []:
        if hint.source != HintSource.FRIGATE_LABEL:
            continue
        if _norm(hint.species) in _GENERIC_SPECIES:
            continue
        if best is None or hint.score > best.score:
            best = hint
    return best


def apply_hints_to_rows(
    rows: list[dict],
    hints: list[HintPayload],
    *,
    app_config: Mapping,
) -> list[dict]:
    """Adjust row confidence from weighted hints. Never creates rows.

    When YOLO/Birder left a generic Bird/Unknown row and Frigate has a named
    sub_label, optionally promote that label onto the existing track row.
    """
    if not rows:
        return rows
    if not hints_enabled(app_config):
        return rows

    weights = load_hint_weights(app_config)
    hint_idx = _hint_index(hints)
    regional_keys = {_norm(h.species) for h in hints if h.source == HintSource.EBIRD_REGIONAL}
    # Hub-first: rename-to-species only with explicit species authority.
    # Score boost from Frigate labels still applies as a prior when hints enabled.
    from visit_contract import frigate_species_authority

    promote_flag = bool(app_config.get("detection.frigate_promote_generic_enabled", False))
    promote_enabled = promote_flag and frigate_species_authority(app_config)
    try:
        promote_min = float(app_config.get("detection.frigate_promote_generic_min_score") or 0.55)
    except (TypeError, ValueError):
        promote_min = 0.55
    promote_min = max(0.0, min(1.0, promote_min))
    best_frigate = _best_named_frigate_hint(hints) if promote_enabled else None
    out: list[dict] = []

    for row in rows:
        species = _species_key(row)
        species_hints = hint_idx.get(species, [])
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
            _max_hint_score(species_hints, HintSource.BIRDNET),
        )
        frigate_prior = _max_hint_score(species_hints, HintSource.FRIGATE_LABEL)
        regional_prior = 1.0 if (species and species in regional_keys) else 0.0
        multi_support = (
            1.0 if bool(row.get("_multi_camera_support")) else min(1.0, _safe_float(row.get("_multi_camera_count")))
        )

        weighted = (
            (base_conf * weights.base_confidence)
            + (detector_conf * weights.detector_confidence)
            + (classifier_conf * weights.classifier_confidence)
            + (min(birdnet_prior, 1.0) * weights.birdnet_prior)
            + (regional_prior * weights.regional_prior)
            + (multi_support * weights.multicam_support)
            + (min(frigate_prior, 1.0) * weights.frigate_label)
        )
        weighted = max(0.0, min(weighted, 1.0))

        trace: list[dict] = []
        if birdnet_prior > 0:
            trace.append(
                HintTraceEntry(
                    "birdnet",
                    species,
                    weights.birdnet_prior * birdnet_prior,
                    weights.birdnet_prior,
                    birdnet_prior,
                ).__dict__
            )
        if frigate_prior > 0:
            trace.append(
                HintTraceEntry(
                    "frigate_label",
                    species,
                    weights.frigate_label * frigate_prior,
                    weights.frigate_label,
                    frigate_prior,
                ).__dict__
            )
        if regional_prior > 0:
            trace.append(
                HintTraceEntry(
                    "ebird_regional",
                    species,
                    weights.regional_prior,
                    weights.regional_prior,
                    regional_prior,
                ).__dict__
            )

        new_row = dict(row)
        new_row["_weighted_arbiter_score"] = round(weighted, 6)
        new_row["confidence"] = round((0.7 * base_conf) + (0.3 * weighted), 6)
        if (
            best_frigate is not None
            and species in _GENERIC_SPECIES
            and float(best_frigate.score) >= promote_min
        ):
            from visit_contract import apply_frigate_named_accept

            promoted = str(best_frigate.species).strip()
            apply_frigate_named_accept(
                new_row,
                species=promoted,
                confidence=float(best_frigate.score),
            )
            # Preserve weighted blend floor when hints already raised confidence.
            new_row["confidence"] = max(
                float(new_row.get("confidence") or 0.0),
                float(best_frigate.score),
                round((0.7 * base_conf) + (0.3 * weighted), 6),
            )
            trace.append(
                HintTraceEntry(
                    "frigate_promote",
                    promoted,
                    float(best_frigate.score),
                    1.0,
                    float(best_frigate.score),
                ).__dict__
            )
        if trace:
            new_row["hint_trace"] = trace
        out.append(new_row)

    return out


def apply_classifier_hints(
    rows: list[dict],
    *,
    mqtt_events: Iterable[dict],
    app_config: Mapping,
    camera_id: str | None = None,
) -> list[dict]:
    """Single entry point: collect + apply hints."""
    hints = collect_hints(
        camera_id=camera_id,
        track=None,
        mqtt_events=mqtt_events,
        app_config=app_config,
    )
    return apply_hints_to_rows(rows, hints, app_config=app_config)
