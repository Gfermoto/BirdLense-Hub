"""Authentication and access-control helpers.

Extracted from util.py. util.py re-exports everything here for backward compatibility.
"""
import ipaddress
import os
import secrets
import threading
import time

from app_config.app_config import app_config

# Rate limit for verify-password: 5 failed attempts per 60 sec per IP
_verify_password_attempts: dict = {}
_verify_password_lock = threading.Lock()
VERIFY_PASSWORD_LIMIT = 5
VERIFY_PASSWORD_WINDOW = 60


def _is_production_runtime() -> bool:
    values = {
        (os.environ.get('FLASK_ENV') or '').strip().lower(),
        (os.environ.get('BIRDLENSE_ENV') or '').strip().lower(),
    }
    return any(value in {'production', 'prod'} for value in values)


def _get_session_role():
    """Return 'admin' | 'contributor' | None from session."""
    from flask import session
    return session.get('access_role')


def _has_contributor_password():
    """True if contributor tier is configured (two-password mode)."""
    return bool((app_config.get('general.contributor_password') or '').strip())


def settings_check_access():
    """Check admin access for settings, feed, and system endpoints.

    Backward compat: no password = full access outside production.
    Also accepts MCP token (Authorization: Bearer) for server-to-server calls.
    """
    from flask import session, request
    admin_pw = (app_config.get('general.settings_password') or '').strip()
    contrib_pw = (app_config.get('general.contributor_password') or '').strip()

    # MCP token из настроек — для вызовов MCP-сервера к API (Get_app_settings и т.д.)
    mcp_token = (os.environ.get('MCP_TOKEN') or app_config.get('mcp.token') or '').strip()
    if mcp_token:
        auth = request.headers.get('Authorization') or ''
        if auth.startswith('Bearer '):
            token = auth[7:].strip()
            if secrets.compare_digest(token, mcp_token):
                return True

    if not admin_pw and not contrib_pw:
        if _is_production_runtime():
            return False
        return True
    role = session.get('access_role')
    if role == 'admin':
        return True
    if not contrib_pw and role and session.get('settings_unlocked'):
        return True  # legacy: single password
    return False


def contributor_or_admin_access():
    """Check if contributor or admin can access a route."""
    from flask import session
    admin_pw = (app_config.get('general.settings_password') or '').strip()
    contrib_pw = (app_config.get('general.contributor_password') or '').strip()
    if not admin_pw and not contrib_pw:
        if _is_production_runtime():
            return False
        return True
    role = session.get('access_role')
    if role in ('admin', 'contributor'):
        return True
    if not contrib_pw and session.get('settings_unlocked'):
        return True  # legacy
    return False


def client_ip_for_rate_limit(request) -> str:
    """Client IP for throttling behind nginx. Prefer X-Real-IP / X-Forwarded-For, then remote_addr.

    Nginx sets ``X-Real-IP`` for ``/api`` (see ``nginx/standalone.conf.template``). If the app is
    reached **without** a trusted reverse proxy, clients could spoof these headers — use TLS and
    firewall so only nginx talks to Gunicorn.
    """

    def _parse_ip_fragment(raw: str):
        s = (raw or '').strip()
        if not s:
            return None
        if ',' in s:
            s = s.split(',')[0].strip()
        try:
            ipaddress.ip_address(s)
            return s
        except ValueError:
            return None

    trusted_proxy = (os.environ.get('TRUSTED_PROXY') or '').strip().lower() in (
        '1', 'true', 'yes',
    )
    if trusted_proxy:
        for hdr in ('X-Real-IP', 'X-Forwarded-For'):
            parsed = _parse_ip_fragment(request.headers.get(hdr, ''))
            if parsed:
                return parsed
    ra = (getattr(request, 'remote_addr', None) or '').strip()
    return ra or 'unknown'


def _clear_verify_password_attempts(ip: str) -> None:
    """Reset failed-attempt counter after successful unlock."""
    with _verify_password_lock:
        _verify_password_attempts.pop(ip, None)


def _prune_verify_password_attempts_locked(now: float) -> None:
    """Drop stale IPs under lock so the map does not grow without bound."""
    stale = []
    for key, attempts in list(_verify_password_attempts.items()):
        fresh = [t for t in attempts if now - t < VERIFY_PASSWORD_WINDOW]
        if fresh:
            _verify_password_attempts[key] = fresh
        else:
            stale.append(key)
    for key in stale:
        _verify_password_attempts.pop(key, None)


def _check_verify_password_rate_limit(ip: str) -> bool:
    """Return True if under limit, False if rate limited (too many failed attempts)."""
    with _verify_password_lock:
        now = time.monotonic()
        _prune_verify_password_attempts_locked(now)
        attempts = _verify_password_attempts.get(ip, [])
        return len(attempts) < VERIFY_PASSWORD_LIMIT


def _record_verify_password_failure(ip: str) -> None:
    """Record a failed verify-password attempt for rate limiting."""
    with _verify_password_lock:
        now = time.monotonic()
        _prune_verify_password_attempts_locked(now)
        _verify_password_attempts.setdefault(ip, []).append(now)


def verify_password_retry_after_seconds() -> int:
    """HTTP Retry-After (seconds) for 429 on verify-password."""
    return int(VERIFY_PASSWORD_WINDOW)


# --- Public POST /api/ui/system/visitors/track (анонимная аналитика)
_visitor_track_hits: dict[str, list] = {}
_visitor_track_lock = threading.Lock()
VISITOR_TRACK_LIMIT = 120
VISITOR_TRACK_WINDOW = 60.0


def check_visitor_track_rate_limit(ip: str) -> bool:
    """Return True if under per-IP POST limit for visitor analytics."""
    now = time.monotonic()
    with _visitor_track_lock:
        hits = _visitor_track_hits.setdefault(ip, [])
        hits[:] = [t for t in hits if now - t < VISITOR_TRACK_WINDOW]
        if len(hits) >= VISITOR_TRACK_LIMIT:
            return False
        hits.append(now)
        return True
