"""Bbox/crop SLO gate — ReID, welfare and behavior layers run only when geometry is green (#642)."""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

logger = logging.getLogger(__name__)


def _cfg_bool(cfg: Mapping[str, Any] | None, key: str, default: bool) -> bool:
    if not isinstance(cfg, Mapping):
        return default
    val = cfg.get(key, default)
    if isinstance(val, bool):
        return val
    return str(val or "").strip().lower() in ("1", "true", "yes", "on")


def _cfg_float(cfg: Mapping[str, Any] | None, key: str, default: float) -> float:
    if not isinstance(cfg, Mapping):
        return default
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _iou_p50_from_heartbeat(heartbeat_data: dict[str, Any] | None) -> float | None:
    if not isinstance(heartbeat_data, dict):
        return None
    direct = heartbeat_data.get("bbox_parity_roundtrip_iou_p50")
    if direct is not None:
        try:
            return float(direct)
        except (TypeError, ValueError):
            pass
    runtime = heartbeat_data.get("runtime_stats")
    if isinstance(runtime, dict):
        gauges = runtime.get("gauges")
        if isinstance(gauges, dict) and gauges.get("bbox_parity_roundtrip_iou_p50") is not None:
            try:
                return float(gauges["bbox_parity_roundtrip_iou_p50"])
            except (TypeError, ValueError):
                return None
    return None


def evaluate_bbox_slo_ok(
    app_config: Mapping[str, Any] | None = None,
    *,
    heartbeat_data: dict[str, Any] | None = None,
    funnel_status: str | None = None,
) -> tuple[bool, str]:
    """Return (ok, reason). When False, skip ReID, welfare and behavior video layers."""
    cfg = app_config if isinstance(app_config, Mapping) else {}

    env = (os.environ.get("BIRDLENSE_BBOX_SLO_OK") or "").strip().lower()
    if env in ("0", "false", "no", "off"):
        return False, "env_force_red"
    if env in ("1", "true", "yes", "on"):
        return True, "env_force_green"

    if not _cfg_bool(cfg, "readiness.bbox_slo_gate_enabled", True):
        return True, "gate_disabled"

    min_iou = _cfg_float(cfg, "readiness.bbox_slo_min_iou_p50", 0.45)
    iou_p50 = _iou_p50_from_heartbeat(heartbeat_data)
    if iou_p50 is not None and iou_p50 < min_iou:
        return False, f"bbox_iou_p50={iou_p50:.3f}<{min_iou:.3f}"

    if _cfg_bool(cfg, "readiness.bbox_slo_require_funnel_ok", True):
        if str(funnel_status or "").strip().lower() == "degraded":
            return False, "funnel_degraded"

    if iou_p50 is None and _cfg_bool(cfg, "readiness.bbox_slo_allow_unknown_metrics", True):
        return True, "metrics_unknown_allowed"

    return True, "ok"


def bbox_layers_allowed(
    app_config: Mapping[str, Any] | None = None,
    *,
    heartbeat_data: dict[str, Any] | None = None,
    funnel_status: str | None = None,
) -> bool:
    """Processor-side gate for re-id / welfare / behavior enrichment."""
    ok, reason = evaluate_bbox_slo_ok(
        app_config,
        heartbeat_data=heartbeat_data,
        funnel_status=funnel_status,
    )
    if not ok:
        logger.info("bbox_slo gate red: skip ReID/behavior layers (%s)", reason)
    return ok
