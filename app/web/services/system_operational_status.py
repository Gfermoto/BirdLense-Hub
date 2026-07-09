"""Operational status tiers for System UI (ok / info / warning / critical)."""

from __future__ import annotations

from typing import Any, Callable, Literal

OperationalTier = Literal["ok", "info", "warning", "critical"]

TierSeverity = Literal["success", "info", "warning", "error"]


def birdnet_mqtt_configured(app_config_get: Callable[..., Any]) -> bool:
    """True when broker and a non-empty BirdNET MQTT topic are configured."""
    if not str(app_config_get("mqtt.broker") or "").strip():
        return False
    for key in ("integrations.birdnet.mqtt_topic", "mqtt.birdnet_topic"):
        val = app_config_get(key)
        if val is not None and str(val).strip():
            return True
    return False


def birdnet_fifo_reporting_enabled(app_config_get: Callable[..., Any]) -> bool:
    snap = app_config_get("processor.birdnet_fifo_snapshot_enabled", True)
    persist = app_config_get("processor.birdnet_fifo_persist_enabled", True)
    return bool(snap) or bool(persist)


def frigate_trigger_configured(app_config_get: Callable[..., Any]) -> bool:
    return bool(app_config_get("triggers.frigate.enabled", False))


def tier_to_mui_severity(tier: OperationalTier) -> TierSeverity:
    if tier == "ok":
        return "success"
    if tier == "info":
        return "info"
    if tier == "warning":
        return "warning"
    return "error"


def resolve_birdnet_fifo_operational_status(
    *,
    app_config_get: Callable[..., Any],
    available: bool,
    snapshot_stale: bool = False,
    queue_len: int = 0,
    mqtt_connected: bool | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Classify BirdNET FIFO diagnostics for /system.

    - disabled: no MQTT birdnet topic (intentional, not an incident)
    - ok: events in queue or fresh empty buffer while configured
    - info: empty queue, no stale file — normal quiet period
    - warning: stale snapshot or MQTT down while BirdNET expected
    - critical: configured, reporting on, but no data path at all
    """
    configured = birdnet_mqtt_configured(app_config_get)
    reporting = birdnet_fifo_reporting_enabled(app_config_get)

    if not configured:
        return {
            "operational_tier": "info",
            "operational_code": "birdnet_disabled",
            "operational_summary_key": "system.birdnetFifoStatus.disabled",
            "birdnet_configured": False,
            "birdnet_reporting_enabled": reporting,
        }

    if not reporting:
        return {
            "operational_tier": "info",
            "operational_code": "birdnet_reporting_off",
            "operational_summary_key": "system.birdnetFifoStatus.reportingOff",
            "birdnet_configured": True,
            "birdnet_reporting_enabled": False,
        }

    if not available:
        code = "birdnet_unavailable"
        tier: OperationalTier = "critical"
        if reason == "snapshot_file_missing":
            tier = "warning"
        return {
            "operational_tier": tier,
            "operational_code": code,
            "operational_summary_key": "system.birdnetFifoStatus.unavailable",
            "birdnet_configured": True,
            "birdnet_reporting_enabled": True,
            "operational_reason": reason,
        }

    if snapshot_stale:
        return {
            "operational_tier": "warning",
            "operational_code": "birdnet_snapshot_stale",
            "operational_summary_key": "system.birdnetFifoStatus.stale",
            "birdnet_configured": True,
            "birdnet_reporting_enabled": True,
        }

    if mqtt_connected is False:
        return {
            "operational_tier": "warning",
            "operational_code": "birdnet_mqtt_disconnected",
            "operational_summary_key": "system.birdnetFifoStatus.mqttDown",
            "birdnet_configured": True,
            "birdnet_reporting_enabled": True,
        }

    if int(queue_len or 0) <= 0:
        return {
            "operational_tier": "info",
            "operational_code": "birdnet_queue_empty",
            "operational_summary_key": "system.birdnetFifoStatus.empty",
            "birdnet_configured": True,
            "birdnet_reporting_enabled": True,
        }

    return {
        "operational_tier": "ok",
        "operational_code": "birdnet_active",
        "operational_summary_key": "system.birdnetFifoStatus.active",
        "birdnet_configured": True,
        "birdnet_reporting_enabled": True,
    }


def enrich_birdnet_fifo_response(body: dict, *, app_config_get: Callable[..., Any]) -> dict:
    """Attach operational_* fields to diagnostics/birdnet-fifo JSON."""
    snap = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else {}
    queue_len = int(snap.get("queue_len") or 0) if snap else 0
    mqtt_connected = snap.get("mqtt_connected") if snap else None
    if mqtt_connected is not None:
        mqtt_connected = bool(mqtt_connected)

    status = resolve_birdnet_fifo_operational_status(
        app_config_get=app_config_get,
        available=bool(body.get("available")),
        snapshot_stale=bool(body.get("snapshot_stale")),
        queue_len=queue_len,
        mqtt_connected=mqtt_connected,
        reason=str(body.get("reason") or "") or None,
    )
    return {**body, **status}


def filter_runtime_parity_alerts(
    parity_alerts: dict[str, bool],
    *,
    app_config_get: Callable[..., Any],
) -> dict[str, bool]:
    """Drop Frigate parity noise when Frigate trigger is off in config."""
    out = dict(parity_alerts or {})
    if not frigate_trigger_configured(app_config_get):
        out["frigate_degraded_no_mqtt"] = False
        out["frigate_config_runtime_mismatch"] = False
    return out


def strict_quality_ratio_ok(
    ratio: float | None,
    *,
    sample_count: int,
    threshold: float,
) -> bool:
    """Pass ratio gates when there is nothing to measure in 24h (avoid false yellow)."""
    if sample_count <= 0 or ratio is None:
        return True
    try:
        return float(ratio) >= float(threshold)
    except (TypeError, ValueError):
        return True
