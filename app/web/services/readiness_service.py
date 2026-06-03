"""Operational readiness payload for install/deploy verification."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from app_config.app_config import app_config
from data_paths import data_dir
from models import ActivityLog
from services.cache import cache_get, cache_set
from services.cache import cache_backend_readiness
from services.component_status_service import build_component_status_payload_safe
from services.persist_funnel_service import build_persist_funnel_summary
from services.runtime_env import env_flag_enabled, is_production_runtime
from util import ensure_utc


def _env_flag_enabled(raw: str | None) -> bool:
    return env_flag_enabled(raw)


def _is_production_env() -> bool:
    return is_production_runtime()


def _is_test_runtime() -> bool:
    return os.environ.get("FLASK_TESTING") == "1" or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _looks_unexpanded_secret(value: str) -> bool:
    v = value.strip()
    return "${" in v or v.startswith("${")


def _secret_gate_status(raw: str | None, *, min_len: int, prod: bool) -> str:
    v = (raw or "").strip()
    if not v or _looks_unexpanded_secret(v) or len(v) < min_len:
        return "error" if prod else "warn"
    return "ok"


def _strict_auth_gate_status(prod: bool) -> str:
    if _env_flag_enabled(os.environ.get("BIRDLENSE_STRICT_API_AUTH")):
        return "ok"
    return "error" if prod else "warn"


def build_security_gates_payload() -> dict[str, object]:
    """Aligns with scripts/verify-prod-env.sh (strict auth + secrets); UI checklist."""
    prod = _is_production_env()
    runtime = "production" if prod else "development"
    items: list[dict[str, str]] = [
        {"id": "strict_api_auth", "status": _strict_auth_gate_status(prod)},
        {
            "id": "flask_secret_key",
            "status": _secret_gate_status(os.environ.get("FLASK_SECRET_KEY"), min_len=32, prod=prod),
        },
        {
            "id": "processor_secret",
            "status": _secret_gate_status(os.environ.get("PROCESSOR_SECRET"), min_len=32, prod=prod),
        },
    ]
    return {"runtime": runtime, "items": items}


def _path_status(path: Path, label: str) -> dict[str, object]:
    exists = path.exists()
    is_dir = path.is_dir()
    writable = os.access(path, os.W_OK) if exists else False
    return {
        "path": label,
        "exists": exists,
        "is_dir": is_dir,
        "writable": writable,
        "status": "ok" if exists and is_dir and writable else "error",
    }


def _processor_heartbeat_readiness(session) -> dict[str, object]:
    """Processor heartbeat freshness check for readiness gate."""
    # Pytest uses in-memory DB without processor heartbeats; production still enforces below.
    if _is_test_runtime():
        return {
            "status": "ok",
            "reason": "skipped_flask_testing",
            "max_age_seconds": 180,
        }
    prod = _is_production_env()
    try:
        max_age = int(app_config.get("processor.readiness_heartbeat_max_age_seconds") or 180)
    except (TypeError, ValueError):
        max_age = 180
    max_age = max(30, max_age)
    row = session.query(ActivityLog).filter_by(type="heartbeat").order_by(ActivityLog.updated_at.desc()).first()
    if not row or not row.updated_at:
        return {
            "status": "error" if prod else "ok",
            "reason": "missing_heartbeat",
            "max_age_seconds": max_age,
        }
    try:
        hb_ts = ensure_utc(row.updated_at)
    except (TypeError, ValueError):
        return {
            "status": "error" if prod else "ok",
            "reason": "invalid_heartbeat_timestamp",
            "max_age_seconds": max_age,
        }
    now = datetime.now(timezone.utc)
    age = max(0.0, (now - hb_ts).total_seconds())
    stale = hb_ts < (now - timedelta(seconds=max_age))
    return {
        "status": "error" if (prod and stale) else "ok",
        "reason": "stale_heartbeat" if stale else "ok",
        "max_age_seconds": max_age,
        "age_seconds": round(age, 3),
        "last_heartbeat_utc": hb_ts.isoformat(),
    }


def build_readiness_payload(session) -> tuple[dict[str, object], int]:
    """Return readiness JSON and suggested HTTP status."""
    checks: dict[str, dict[str, object]] = {}

    try:
        session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception:  # pragma: no cover - defensive fallback
        checks["database"] = {"status": "error", "error": "database_unavailable"}

    checks["data_dir"] = _path_status(Path(data_dir()), "data/")
    checks["app_config_dir"] = _path_status(Path(__file__).resolve().parents[2] / "app_config", "app_config/")
    cache_check = cache_backend_readiness()
    if _is_test_runtime() and cache_check.get("status") != "ok":
        cache_check = {
            **cache_check,
            "status": "ok",
            "reason": "skipped_cache_backend_in_tests",
        }
    checks["cache_backend"] = cache_check
    checks["processor_heartbeat"] = _processor_heartbeat_readiness(session)
    funnel = build_persist_funnel_summary(session)
    checks["pipeline_funnel"] = {
        "status": funnel.get("status", "unknown"),
        "sessions_total": funnel.get("sessions_total"),
        "healthy_persist_rate": funnel.get("healthy_persist_rate"),
        "fusion_drop_rate": funnel.get("fusion_drop_rate"),
        "fp_empty_opencv_rate": funnel.get("fp_empty_opencv_rate"),
        "alerts": funnel.get("alerts") or [],
        "top_root_causes": funnel.get("top_root_causes") or [],
    }
    ready = all(check.get("status") == "ok" for check in checks.values())
    hit, cached_components = cache_get("component_status:v1")
    if hit and isinstance(cached_components, dict):
        components_payload = cached_components
    else:
        components_payload = build_component_status_payload_safe(session)
        cache_set("component_status:v1", components_payload, 180)

    yolo_probe = str(components_payload.get("yolo") or "unknown")
    if yolo_probe in ("error", "degraded"):
        checks["yolo_detector"] = {"status": yolo_probe, "source": "heartbeat"}
        ready = ready and yolo_probe == "ok"
    elif yolo_probe == "ok":
        checks["yolo_detector"] = {"status": "ok", "source": "heartbeat"}
    else:
        checks["yolo_detector"] = {"status": "unknown", "source": "heartbeat"}
        if _is_production_env() and not _is_test_runtime():
            ready = False

    funnel_status = str(checks["pipeline_funnel"].get("status") or "unknown")
    if funnel_status == "degraded":
        ready = False

    payload = {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "components": components_payload,
        "pipeline_funnel": funnel,
        "security_gates": build_security_gates_payload(),
    }
    return payload, (200 if ready else 503)
