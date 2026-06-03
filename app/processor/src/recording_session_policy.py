"""Recording session policy helpers — standalone-first product rules."""

from __future__ import annotations

from app_config.app_config import app_config


def effective_frigate_hold_seconds(
    configured_hold: float,
    trigger_source: str | None,
    *,
    cfg=None,
) -> float:
    """
    Frigate MQTT may extend an active clip only when that clip was Frigate-triggered.

    OpenCV / weight / ESPHome sessions rely on own YOLO activity — not Frigate aux.
    """
    try:
        hold = float(configured_hold or 0.0)
    except (TypeError, ValueError):
        hold = 0.0
    if hold <= 0:
        return 0.0
    c = cfg if cfg is not None else app_config
    only_frigate = bool(c.get("processor.frigate_hold_only_when_frigate_trigger", True))
    trig = str(trigger_source or "").strip().lower()
    if only_frigate and trig != "frigate":
        return 0.0
    return hold
