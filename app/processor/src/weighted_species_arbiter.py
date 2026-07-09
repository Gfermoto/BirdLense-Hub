"""Weighted arbitration layer — thin wrapper over classifier_hints (#641)."""

from __future__ import annotations

from typing import Iterable

from classifier_hints import apply_classifier_hints


def apply_weighted_species_arbiter(
    rows: list[dict],
    *,
    mqtt_events: Iterable[dict],
    app_config,
    camera_id: str | None = None,
) -> list[dict]:
    return apply_classifier_hints(
        rows,
        mqtt_events=mqtt_events,
        app_config=app_config,
        camera_id=camera_id,
    )
