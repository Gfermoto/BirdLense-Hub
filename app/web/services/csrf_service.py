"""CSRF protection for browser-driven UI API mutations."""

from __future__ import annotations

import os
import secrets

from flask import Flask, jsonify, request, session

from auth import _is_production_runtime

CSRF_COOKIE_NAME = "birdlense_csrf_token"
CSRF_HEADER_NAME = "X-Birdlense-CSRF-Token"
CSRF_SESSION_KEY = "_csrf_token"
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _env_flag_enabled(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def csrf_protection_enabled() -> bool:
    """Enabled by default in production; opt-in locally with BIRDLENSE_CSRF_PROTECTION=1."""
    raw = os.environ.get("BIRDLENSE_CSRF_PROTECTION")
    if raw is not None:
        return _env_flag_enabled(raw)
    return _is_production_runtime()


def _get_or_create_token() -> str:
    existing = str(session.get(CSRF_SESSION_KEY) or "")
    if existing:
        return existing
    fresh = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = fresh
    return fresh


def _set_csrf_cookie(response):
    response.set_cookie(
        CSRF_COOKIE_NAME,
        _get_or_create_token(),
        secure=_is_production_runtime(),
        httponly=False,
        samesite="Strict",
        path="/",
    )
    return response


def _csrf_tokens_match() -> bool:
    expected = str(session.get(CSRF_SESSION_KEY) or "")
    header_token = (request.headers.get(CSRF_HEADER_NAME) or "").strip()
    cookie_token = (request.cookies.get(CSRF_COOKIE_NAME) or "").strip()
    return bool(
        expected
        and header_token
        and cookie_token
        and secrets.compare_digest(header_token, expected)
        and secrets.compare_digest(cookie_token, expected)
    )


def register_csrf_protection(app: Flask) -> None:
    """Register token bootstrap endpoint and production CSRF middleware."""

    @app.route("/api/ui/csrf-token", methods=["GET"])
    def csrf_token():
        response = jsonify({"csrf_token": _get_or_create_token(), "header": CSRF_HEADER_NAME})
        return _set_csrf_cookie(response)

    @app.before_request
    def _birdlense_csrf_protection():  # type: ignore[no-redef]
        if not csrf_protection_enabled():
            return None
        if request.method.upper() not in _MUTATING_METHODS:
            return None
        if request.method.upper() == "OPTIONS":
            return None
        path = request.path or ""
        if not path.startswith("/api/ui/"):
            return None
        if path.rstrip("/") == "/api/ui/csrf-token":
            return None
        if _csrf_tokens_match():
            return None
        return jsonify({"error": "CSRF token required"}), 403
