"""Обработчики JSON/истории для system metrics, visitors, observability (#293)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from auth import check_visitor_track_rate_limit
from models import (
    SiteVisitor,
    SystemResourceSample,
    Video,
    VideoSpecies,
    db,
)
from services.activity_notify_insights_service import (
    ingest_gate_reason_counts_24h,
    notify_delivery_24h,
    notify_fallback_by_reason_24h,
    notify_preview_by_source_24h,
    notify_preview_generated_by_source_24h,
    notify_suppressed_reason_counts_24h,
)
from services.cache import cache_delete_prefix
from services.ml_health_stats_service import ml_health_snapshot
from services.ml_lineage_service import current_model_lineage_snapshot
from services.prometheus_metrics_service import prometheus_metrics_body
from services.system_live_metrics_service import collect_live_system_metrics
from services.system_metrics_constants import (
    SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS,
    SYSTEM_METRICS_HISTORY_MAX_HOURS,
    SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP,
    SYSTEM_METRICS_RETENTION_HOURS,
    SYSTEM_METRICS_SAMPLE_INTERVAL_SEC,
)
from services.visitor_stats_service import (
    browser_hash,
    collect_visitor_stats,
    device_class_from_user_agent,
    downsample_evenly,
)

if TYPE_CHECKING:
    from flask import Flask

_log = logging.getLogger(__name__)

_BROWSER_ID_RE = re.compile(r"[A-Za-z0-9._:-]{16,128}")


def build_metrics_summary_dict(flask_app: Flask) -> dict[str, Any]:
    sys_m = collect_live_system_metrics(flask_app)
    detections = db.session.query(func.count(VideoSpecies.id)).scalar() or 0
    species_count = db.session.query(VideoSpecies.species_id).distinct().count()
    videos_count = db.session.query(func.count(Video.id)).scalar() or 0
    preview = notify_preview_by_source_24h()
    preview_generated = notify_preview_generated_by_source_24h()
    fallback = notify_fallback_by_reason_24h()
    delivery = notify_delivery_24h()
    ingest_gate = ingest_gate_reason_counts_24h()
    notify_suppressed = notify_suppressed_reason_counts_24h()
    payload: dict[str, Any] = {
        "service": "birdlense-hub",
        "cpu_usage_percent": float(sys_m["cpu"]["percent"]),
        "memory_used_percent": float(sys_m["memory"]["percent"]),
        "memory_used_bytes": int(sys_m["memory"]["used_bytes"]),
        "memory_total_bytes": int(sys_m["memory"]["total_bytes"]),
        "disk_used_percent": float(sys_m["disk"]["percent"]),
        "detections_total": int(detections),
        "species_count": int(species_count),
        "videos_total": int(videos_count),
        "notify_preview_24h": preview,
        "notify_preview_generated_24h": preview_generated,
        "notify_fallback_24h": fallback,
        "notify_delivery_24h": delivery,
        "ingest_gate_24h": ingest_gate,
        "notify_suppressed_24h": notify_suppressed,
        # Retention metrics
        "retention_last_run": None,
        "retention_last_deleted_count": 0,
        "retention_last_freed_bytes": 0,
        "retention_mode": "cascade",
    }
    # Fetch latest retention metrics from service
    try:
        from services.retention_service import _fetch_metrics
        m = _fetch_metrics()
        payload["retention_last_run"] = m.get("retention_last_run")
        payload["retention_last_deleted_count"] = m.get("retention_last_deleted_count", 0)
        payload["retention_last_freed_bytes"] = m.get("retention_last_freed_bytes", 0)
        payload["retention_mode"] = m.get("retention_mode", "cascade")
    except Exception:
        pass  # best effort
    if sys_m["gpu_percent"] is not None:
        payload["gpu_usage_percent"] = float(sys_m["gpu_percent"])
    return payload


def metrics_summary_json_or_error(flask_app: Flask) -> tuple[dict, int]:
    try:
        return build_metrics_summary_dict(flask_app), 200
    except Exception as e:
        _log.error("metrics summary: %s", e)
        return {"error": "Failed to build metrics summary"}, 500


def prometheus_text_or_error(flask_app: Flask) -> tuple[str, int]:
    try:
        return prometheus_metrics_body(flask_app), 200
    except Exception as e:
        _log.error("Error getting Prometheus metrics: %s", e)
        return "# Error\n", 500


def system_metrics_live_payload_or_error(flask_app: Flask) -> tuple[dict, int]:
    try:
        m = collect_live_system_metrics(flask_app)
        return {
            "cpu": m["cpu"],
            "memory": m["memory"],
            "disk": m["disk"],
            "encoding": m["encoding"],
            "gpu_percent": m["gpu_percent"],
        }, 200
    except Exception as e:
        _log.error("Error getting system metrics: %s", e)
        return {"error": "Failed to get system metrics"}, 500


def observability_payload_or_error() -> tuple[dict, int]:
    try:
        preview = notify_preview_by_source_24h()
        preview_generated = notify_preview_generated_by_source_24h()
        fallback = notify_fallback_by_reason_24h()
        delivery = notify_delivery_24h()
        ingest_gate = ingest_gate_reason_counts_24h()
        notify_suppressed = notify_suppressed_reason_counts_24h()
        return {
            "notify_preview_24h": preview,
            "notify_preview_generated_24h": preview_generated,
            "notify_fallback_24h": fallback,
            "notify_delivery_24h": delivery,
            "ingest_gate_24h": ingest_gate,
            "notify_suppressed_24h": notify_suppressed,
            "ml_health": {
                "rolling_7d": ml_health_snapshot(7),
                "rolling_30d": ml_health_snapshot(30),
            },
            "model_lineage": current_model_lineage_snapshot(),
            "hub_metrics": {
                "prometheus_text": "/metrics",
                "prometheus_text_alt": "/api/metrics",
                "json_summary": "/api/metrics/summary",
            },
        }, 200
    except Exception as e:
        _log.error("observability: %s", e)
        return {"error": "Failed"}, 500


def parse_visitors_days(raw: str | None) -> int:
    try:
        return int(raw or "7")
    except (TypeError, ValueError):
        return 7


def visitor_stats_or_error(days: int) -> tuple[Any, int]:
    try:
        return collect_visitor_stats(days), 200
    except Exception as e:
        _log.error("Error getting visitor stats: %s", e)
        return {"error": "Failed to get visitor stats"}, 500


def track_site_visitor(
    client_ip: str,
    browser_id_raw: str,
    user_agent: str,
) -> tuple[dict, int]:
    try:
        if not check_visitor_track_rate_limit(client_ip):
            return {"error": "Too many requests"}, 429

        raw_browser_id = str(browser_id_raw or "").strip()
        if not _BROWSER_ID_RE.fullmatch(raw_browser_id):
            return {"error": "Invalid browser_id"}, 400

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        seen_day = now_utc.strftime("%Y-%m-%d")
        bh = browser_hash(raw_browser_id)
        device_class = device_class_from_user_agent(user_agent)

        row = (
            db.session.query(SiteVisitor)
            .filter(
                SiteVisitor.browser_hash == bh,
                SiteVisitor.seen_day == seen_day,
            )
            .first()
        )
        if row is None:
            row = SiteVisitor(
                browser_hash=bh,
                seen_day=seen_day,
                device_class=device_class,
                first_seen_at=now_utc,
                last_seen_at=now_utc,
            )
            db.session.add(row)
        else:
            row.last_seen_at = now_utc
            row.device_class = device_class
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            row = (
                db.session.query(SiteVisitor)
                .filter(
                    SiteVisitor.browser_hash == bh,
                    SiteVisitor.seen_day == seen_day,
                )
                .first()
            )
            if row is None:
                raise
            row.last_seen_at = now_utc
            row.device_class = device_class
            db.session.commit()
        cache_delete_prefix("system_visitors:")
        return {"ok": True}, 200
    except Exception as e:
        db.session.rollback()
        _log.error("Error tracking site visitor: %s", e)
        return {"error": "Failed to track site visitor"}, 500


def clamp_metrics_history_hours(raw: str | None) -> int:
    try:
        hours = int(raw or "24")
    except (TypeError, ValueError):
        hours = 24
    return max(1, min(hours, SYSTEM_METRICS_HISTORY_MAX_HOURS))


def clamp_metrics_history_max_points(raw: str | None) -> int:
    try:
        max_points = int(
            raw or str(SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS),
        )
    except (TypeError, ValueError):
        max_points = SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS
    return max(50, min(max_points, SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP))


def metrics_history_payload_or_error(hours: int, max_points: int) -> tuple[dict, int]:
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)
        rows = db.session.scalars(
            select(SystemResourceSample)
            .where(SystemResourceSample.recorded_at >= start)
            .order_by(SystemResourceSample.recorded_at.asc())
        ).all()
        rows = downsample_evenly(rows, max_points)
        return {
            "samples": [
                {
                    "t": r.recorded_at.isoformat(),
                    "cpu": round(r.cpu_percent, 2),
                    "memory": round(r.memory_percent, 2),
                    "disk": round(r.disk_percent, 2),
                    "gpu": None if r.gpu_percent is None else round(r.gpu_percent, 2),
                }
                for r in rows
            ],
            "sample_interval_seconds": SYSTEM_METRICS_SAMPLE_INTERVAL_SEC,
            "retention_hours": SYSTEM_METRICS_RETENTION_HOURS,
            "hours_requested": hours,
        }, 200
    except Exception as e:
        _log.error("Error getting system metrics history: %s", e)
        return {"error": "Failed to get system metrics history"}, 500
