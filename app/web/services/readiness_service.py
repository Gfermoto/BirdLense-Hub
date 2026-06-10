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
from services.status_service import _yolo_inference_ready, parse_yolo_status_from_heartbeat
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


def _parse_heartbeat_data(row) -> dict | None:
    if not row or not row.data:
        return None
    try:
        import json

        parsed = json.loads(row.data) if isinstance(row.data, str) else row.data
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _latest_processor_heartbeat_row(session):
    return session.query(ActivityLog).filter_by(type="heartbeat").order_by(ActivityLog.updated_at.desc()).first()


def _processor_bootstrap_phase(heartbeat_data: dict | None, *, age_seconds: float) -> bool:
    if not isinstance(heartbeat_data, dict):
        return False
    if heartbeat_data.get("bootstrap_error"):
        return False
    status = str(heartbeat_data.get("status") or "").strip().lower()
    if status == "bootstrap":
        return True
    if _yolo_inference_ready(heartbeat_data):
        return False
    try:
        max_boot = int(app_config.get("processor.bootstrap_phase_max_seconds") or 600)
    except (TypeError, ValueError):
        max_boot = 600
    return age_seconds <= max(30.0, float(max_boot))


def _heartbeat_last_motion_age_sec(heartbeat_data: dict | None) -> float | None:
    if not isinstance(heartbeat_data, dict):
        return None
    direct = heartbeat_data.get("last_motion_age_sec")
    if direct is not None:
        try:
            return max(0.0, float(direct))
        except (TypeError, ValueError):
            pass
    runtime = heartbeat_data.get("runtime_stats")
    if isinstance(runtime, dict):
        gauges = runtime.get("gauges")
        if isinstance(gauges, dict) and gauges.get("last_motion_age_sec") is not None:
            try:
                return max(0.0, float(gauges.get("last_motion_age_sec")))
            except (TypeError, ValueError):
                return None
    last_motion_at = heartbeat_data.get("last_motion_at")
    if not last_motion_at:
        return None
    try:
        motion_dt = ensure_utc(datetime.fromisoformat(str(last_motion_at).replace("Z", "+00:00")))
    except (TypeError, ValueError):
        return None
    return max(0.0, (datetime.now(timezone.utc) - motion_dt).total_seconds())


def _build_yolo_detector_check(heartbeat_data: dict | None, yolo_probe: str) -> dict[str, object]:
    """YOLO readiness with between-session idle monitoring (#605 idle ok preserved)."""
    check: dict[str, object] = {"source": "heartbeat"}
    motion_age = _heartbeat_last_motion_age_sec(heartbeat_data)
    if motion_age is not None:
        check["last_motion_age_sec"] = round(motion_age, 3)
    runtime = heartbeat_data.get("runtime_stats") if isinstance(heartbeat_data, dict) else None
    gauges = runtime.get("gauges") if isinstance(runtime, dict) else None
    if isinstance(heartbeat_data, dict):
        backend_eff = heartbeat_data.get("inference_backend_effective")
        if backend_eff:
            check["inference_backend_effective"] = str(backend_eff).strip().lower()
        backend_req = heartbeat_data.get("inference_backend_requested")
        if backend_req:
            check["inference_backend_requested"] = str(backend_req).strip().lower()
    if isinstance(gauges, dict):
        if not check.get("inference_backend_effective") and gauges.get("inference_backend_effective"):
            check["inference_backend_effective"] = str(gauges.get("inference_backend_effective")).strip().lower()
        if not check.get("inference_backend_requested") and gauges.get("inference_backend_requested"):
            check["inference_backend_requested"] = str(gauges.get("inference_backend_requested")).strip().lower()
    blind_alert = 0
    blind_status = ""
    if isinstance(gauges, dict):
        blind_alert = int(gauges.get("yolo_blind_alert") or 0)
        blind_status = str(gauges.get("yolo_blind_status") or "").strip().lower()
    try:
        motion_window = float(app_config.get("detection.yolo_between_motion_max_age_seconds") or 120.0)
    except (TypeError, ValueError):
        motion_window = 120.0
    recent_motion = motion_age is not None and motion_age <= max(5.0, motion_window)
    between_session_blind = bool(
        recent_motion
        and _yolo_inference_ready(heartbeat_data)
        and (blind_alert == 1 or blind_status in ("blind", "degraded", "suspected"))
    )
    if between_session_blind:
        check["between_session_blind"] = True
    status = yolo_probe
    if status == "unknown" and _yolo_inference_ready(heartbeat_data):
        status = "ok"
    if between_session_blind and status == "ok":
        status = "error" if blind_alert == 1 or blind_status == "blind" else "degraded"
    auto_torch_fallback = bool(
        isinstance(heartbeat_data, dict) and heartbeat_data.get("inference_auto_torch_fallback"),
    )
    requested_backend = str(check.get("inference_backend_requested") or "").strip().lower()
    effective_backend = str(check.get("inference_backend_effective") or "").strip().lower()
    if (
        not auto_torch_fallback
        and requested_backend in ("auto", "openvino")
        and effective_backend == "torch"
    ):
        auto_torch_fallback = True
    if auto_torch_fallback and status == "ok":
        status = "degraded"
        check["inference_auto_torch_fallback"] = True
    check["status"] = status
    return check


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
    row = _latest_processor_heartbeat_row(session)
    heartbeat_data = _parse_heartbeat_data(row)
    if not row or not row.updated_at:
        return {
            "status": "error" if prod else "ok",
            "reason": "missing_heartbeat",
            "max_age_seconds": max_age,
            "bootstrap_phase": False,
        }
    if isinstance(heartbeat_data, dict) and heartbeat_data.get("bootstrap_error"):
        return {
            "status": "error",
            "reason": str(heartbeat_data.get("bootstrap_error_code") or "processor_config_error"),
            "message": str(heartbeat_data.get("bootstrap_error") or ""),
            "max_age_seconds": max_age,
            "bootstrap_phase": False,
        }
    try:
        hb_ts = ensure_utc(row.updated_at)
    except (TypeError, ValueError):
        return {
            "status": "error" if prod else "ok",
            "reason": "invalid_heartbeat_timestamp",
            "max_age_seconds": max_age,
            "bootstrap_phase": False,
        }
    now = datetime.now(timezone.utc)
    age = max(0.0, (now - hb_ts).total_seconds())
    stale = hb_ts < (now - timedelta(seconds=max_age))
    bootstrap_phase = _processor_bootstrap_phase(heartbeat_data, age_seconds=age)
    return {
        "status": "error" if (prod and stale) else "ok",
        "reason": "stale_heartbeat" if stale else "ok",
        "max_age_seconds": max_age,
        "age_seconds": round(age, 3),
        "last_heartbeat_utc": hb_ts.isoformat(),
        "bootstrap_phase": bootstrap_phase,
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
    heartbeat_row = _latest_processor_heartbeat_row(session)
    heartbeat_data = _parse_heartbeat_data(heartbeat_row)
    funnel = build_persist_funnel_summary(session)
    checks["pipeline_funnel"] = {
        "status": funnel.get("status", "unknown"),
        "sessions_total": funnel.get("sessions_total"),
        "healthy_persist_rate": funnel.get("healthy_persist_rate"),
        "fusion_drop_rate": funnel.get("fusion_drop_rate"),
        "fp_empty_opencv_rate": funnel.get("fp_empty_opencv_rate"),
        "alerts": funnel.get("alerts") or [],
        "top_root_causes": funnel.get("top_root_causes") or [],
        "persist_substage_breakdown": funnel.get("persist_substage_breakdown") or {},
    }
    core_check_names = ("database", "data_dir", "app_config_dir", "cache_backend", "processor_heartbeat")
    ready = all(checks.get(name, {}).get("status") == "ok" for name in core_check_names)
    hit, cached_components = cache_get("component_status:v1")
    if hit and isinstance(cached_components, dict):
        components_payload = cached_components
    else:
        components_payload = build_component_status_payload_safe(session)
        cache_set("component_status:v1", components_payload, 180)

    yolo_probe = str(components_payload.get("yolo") or "unknown")
    if heartbeat_data and yolo_probe in ("unknown", "ok", "degraded", "error"):
        yolo_probe = parse_yolo_status_from_heartbeat(heartbeat_data)
    checks["yolo_detector"] = _build_yolo_detector_check(heartbeat_data, yolo_probe)
    funnel_status = str(checks["pipeline_funnel"].get("status") or "unknown")
    yolo_ok_for_quality = str(checks["yolo_detector"].get("status") or "") == "ok"
    funnel_ok = funnel_status != "degraded"
    quality_ready = funnel_ok and yolo_ok_for_quality
    if not funnel_ok or str(checks["yolo_detector"].get("status") or "") in ("error", "degraded"):
        ready = False

    payload = {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "quality_ready": quality_ready,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "components": components_payload,
        "pipeline_funnel": funnel,
        "security_gates": build_security_gates_payload(),
    }
    return payload, (200 if ready else 503)
