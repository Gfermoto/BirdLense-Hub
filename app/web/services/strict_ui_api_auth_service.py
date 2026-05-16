"""Strict /api/ui/* auth in production when BIRDLENSE_STRICT_API_AUTH (#279).

Публичные GET (_PUBLIC_GET_EXACT / префиксы): только read-only дашборд; доступ к данным
персона/настроек — в обработчике (contributor/admin/MCP/UI key). При добавлении новых
GET для главной страницы — расширять списки и тест ``test_strict_ui_api_auth``.
"""

from __future__ import annotations

import os
import secrets
import logging

from flask import Flask, jsonify

from auth import (
    contributor_or_admin_access,
    mcp_bearer_authorized,
)
from services.runtime_env import env_flag_enabled, is_production_runtime


def _env_flag_enabled(raw: str | None) -> bool:
    return env_flag_enabled(raw)


def strict_ui_api_auth_enabled() -> bool:
    """Strict gate: production runtime and explicit env flag."""
    return is_production_runtime() and _env_flag_enabled(os.environ.get("BIRDLENSE_STRICT_API_AUTH"))


def security_monitor_only_enabled() -> bool:
    """Production emergency mode: log security denials, but do not block."""
    return _env_flag_enabled(os.environ.get("BIRDLENSE_SECURITY_MONITOR_ONLY"))


def ui_api_key_authorized() -> bool:
    """BIRDLENSE_UI_API_KEY via X-Birdlense-Api-Key or Authorization: Bearer."""
    expected = (os.environ.get("BIRDLENSE_UI_API_KEY") or "").strip()
    if not expected:
        return False
    from flask import request

    hdr = (request.headers.get("X-Birdlense-Api-Key") or "").strip()
    if hdr and secrets.compare_digest(hdr, expected):
        return True
    auth = request.headers.get("Authorization") or ""
    if len(auth) > 7 and auth[:7].lower() == "bearer ":
        token = auth[7:].strip()
        if token and secrets.compare_digest(token, expected):
            return True
    return False


def strict_ui_request_authorized() -> bool:
    """Session (contributor/admin), MCP Bearer, or UI API key."""
    if mcp_bearer_authorized():
        return True
    if ui_api_key_authorized():
        return True
    if contributor_or_admin_access():
        return True
    return False


_STRICT_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/api/ui/health"),
        ("GET", "/api/ui/readiness"),
        ("GET", "/api/ui/csrf-token"),
        ("GET", "/api/ui/settings/requires-password"),
        ("GET", "/api/ui/settings/check-access"),
        ("POST", "/api/ui/settings/verify-password"),
        ("GET", "/api/ui/push/vapid-public"),
        ("POST", "/api/ui/settings/logout"),
    }
)

_PUBLIC_GET_EXACT: frozenset[str] = frozenset(
    {
        "/api/ui/status",
        "/api/ui/cameras",
        "/api/ui/feed/info",
        "/api/ui/weather",
        "/api/ui/sun-times",
        "/api/ui/overview",
        "/api/ui/region-comparison",
        "/api/ui/migration-calendar",
        "/api/ui/timeline",
        "/api/ui/timeline/export",
        "/api/ui/report/pdf",
        "/api/ui/unknowns",
        "/api/ui/species",
        "/api/ui/species/observed",
        "/api/ui/species/track-regen-options",
        "/api/ui/species/tuning-targets",
        "/api/ui/bird_families",
        "/api/ui/species-image",
        "/api/ui/birdfood",
        "/api/ui/favorites/by-species",
        "/api/ui/corrections/recent",
        "/api/ui/storage/stats",
        "/api/ui/storage/nearest-recording-day",
    }
)

_PUBLIC_GET_PREFIXES: tuple[str, ...] = (
    "/api/ui/videos/",
    "/api/ui/species/",
    "/api/ui/detections/",
)

_PRIVATE_GET_PREFIXES: tuple[str, ...] = (
    "/api/ui/settings",
    "/api/ui/system",
    "/api/ui/storage",
    "/api/ui/status/debug",
    "/api/ui/dataset",
)


def _canonical_path(path: str) -> str:
    p = (path or "").split("?", 1)[0].rstrip("/")
    return p if p else "/"


def _public_get_allowed(path: str) -> bool:
    if path in _PUBLIC_GET_EXACT:
        return True
    if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in _PRIVATE_GET_PREFIXES):
        return False
    return any(path.startswith(prefix) for prefix in _PUBLIC_GET_PREFIXES)


def register_strict_ui_api_auth_middleware(app: Flask) -> None:
    """403 on /api/ui/* without creds when strict + production (see module doc)."""

    @app.before_request
    def _birdlense_strict_ui_api_auth():  # type: ignore[no-redef]
        from flask import request

        if not strict_ui_api_auth_enabled():
            return None
        path = request.path or ""
        if not path.startswith("/api/ui/"):
            return None
        if request.method == "OPTIONS":
            return None
        key = (request.method.upper(), _canonical_path(path))
        if key in _STRICT_ALLOWLIST:
            return None
        if key[0] == "GET" and _public_get_allowed(key[1]):
            return None
        if strict_ui_request_authorized():
            return None
        msg = (
            "strict_ui_api_auth_denied_monitor_only" if security_monitor_only_enabled() else "strict_ui_api_auth_denied"
        )
        logging.warning(
            msg,
            extra={
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
            },
        )
        if security_monitor_only_enabled():
            return None
        return jsonify({"error": "Authentication required"}), 403
