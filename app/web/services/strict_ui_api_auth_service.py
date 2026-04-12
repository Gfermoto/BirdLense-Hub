"""Strict /api/ui/* auth in production when BIRDLENSE_STRICT_API_AUTH (#279)."""

from __future__ import annotations

import os
import secrets

from flask import Flask, jsonify

from auth import (
    _is_production_runtime,
    contributor_or_admin_access,
    mcp_bearer_authorized,
)


def _env_flag_enabled(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def strict_ui_api_auth_enabled() -> bool:
    """Strict gate: production runtime and explicit env flag."""
    return _is_production_runtime() and _env_flag_enabled(os.environ.get("BIRDLENSE_STRICT_API_AUTH"))


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
        ("GET", "/api/ui/settings/requires-password"),
        ("GET", "/api/ui/settings/check-access"),
        ("POST", "/api/ui/settings/verify-password"),
        ("GET", "/api/ui/push/vapid-public"),
        ("POST", "/api/ui/settings/logout"),
    }
)


def _canonical_path(path: str) -> str:
    p = (path or "").split("?", 1)[0].rstrip("/")
    return p if p else "/"


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
        if strict_ui_request_authorized():
            return None
        return jsonify({"error": "Authentication required"}), 403
