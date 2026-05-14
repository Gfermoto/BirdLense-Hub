"""Operational readiness payload for install/deploy verification."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from data_paths import data_dir
from services.component_status_service import build_component_status_payload_safe
from services.runtime_env import env_flag_enabled, is_production_runtime


def _env_flag_enabled(raw: str | None) -> bool:
    return env_flag_enabled(raw)


def _is_production_env() -> bool:
    return is_production_runtime()


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

    ready = all(check.get("status") == "ok" for check in checks.values())
    payload = {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "components": build_component_status_payload_safe(session),
        "security_gates": build_security_gates_payload(),
    }
    return payload, (200 if ready else 503)
