"""Operational readiness payload for install/deploy verification."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from data_paths import data_dir
from services.component_status_service import build_component_status_payload_safe


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
    }
    return payload, (200 if ready else 503)
