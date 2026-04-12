"""Таймаут неактивности сессии входа (admin/contributor), #280."""

from __future__ import annotations

import time

from flask import Flask, session

from app_config.app_config import app_config
from auth import _is_production_runtime

SESSION_ACTIVITY_KEY = "_birdlense_last_activity_unix"


def stamp_session_activity_now() -> None:
    """Вызвать после успешного verify-password (новый отсчёт idle)."""
    session[SESSION_ACTIVITY_KEY] = time.time()
    session.modified = True


def clear_session_activity_timestamp() -> None:
    session.pop(SESSION_ACTIVITY_KEY, None)


def _session_has_unlock_state() -> bool:
    return bool(session.get("access_role")) or bool(session.get("settings_unlocked"))


def _idle_enforced() -> bool:
    if (app_config.get("general.settings_password") or "").strip():
        return True
    if (app_config.get("general.contributor_password") or "").strip():
        return True
    return _is_production_runtime()


def _idle_minutes() -> int:
    raw = app_config.get("general.session_idle_minutes")
    if raw is None:
        return 30
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 30
    return max(0, v)


def register_session_idle_middleware(app: Flask) -> None:
    @app.before_request
    def _birdlense_session_idle() -> None:
        from flask import request

        if not request.path.startswith("/api/"):
            return None
        if request.path.rstrip("/") == "/api/ui/health":
            return None
        if not _idle_enforced():
            return None
        lim = _idle_minutes()
        if lim <= 0:
            return None
        if not _session_has_unlock_state():
            return None

        now = time.time()
        raw_last = session.get(SESSION_ACTIVITY_KEY)
        try:
            last = float(raw_last) if raw_last is not None else now
        except (TypeError, ValueError):
            last = now

        if now - last > lim * 60:
            session.pop("access_role", None)
            session.pop("settings_unlocked", None)
            session.pop(SESSION_ACTIVITY_KEY, None)
            session.modified = True
            return None

        session[SESSION_ACTIVITY_KEY] = now
        session.modified = True
        return None
