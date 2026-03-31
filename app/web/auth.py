"""Authentication and access-control helpers.

Extracted from util.py. util.py re-exports everything here for backward compatibility.
"""
import os
import secrets

from app_config.app_config import app_config


def _get_session_role():
    """Return 'admin' | 'contributor' | None from session."""
    from flask import session
    return session.get('access_role')


def _has_contributor_password():
    """True if contributor tier is configured (two-password mode)."""
    return bool((app_config.get('general.contributor_password') or '').strip())


def settings_check_access():
    """Check if admin access (settings, feed, system). Backward compat: no password = full access.
    Also accepts MCP token (Authorization: Bearer) for server-to-server calls."""
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
        return True
    role = session.get('access_role')
    if role == 'admin':
        return True
    if not contrib_pw and role and session.get('settings_unlocked'):
        return True  # legacy: single password
    return False


def contributor_or_admin_access():
    """Check if contributor or admin (correction, reports, iNaturalist, exports)."""
    from flask import session
    admin_pw = (app_config.get('general.settings_password') or '').strip()
    contrib_pw = (app_config.get('general.contributor_password') or '').strip()
    if not admin_pw and not contrib_pw:
        return True
    role = session.get('access_role')
    if role in ('admin', 'contributor'):
        return True
    if not contrib_pw and session.get('settings_unlocked'):
        return True  # legacy
    return False
