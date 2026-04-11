"""Декораторы проверки доступа для UI routes (DRY, #302)."""

from __future__ import annotations

import auth as auth_mod
from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar('F', bound=Callable[..., Any])


def require_ui_settings_password(view: F) -> F:
    """``settings_check_access``; при отказе — 403 и ``Password required``."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if not auth_mod.settings_check_access():
            return {'error': 'Password required'}, 403
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def require_ui_settings_unauthorized(view: F) -> F:
    """``settings_check_access``; при отказе — 401 и ``Unauthorized`` (config-audit)."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if not auth_mod.settings_check_access():
            return {'error': 'Unauthorized'}, 401
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def require_admin_track_regen(view: F) -> F:
    """``admin_track_regen_access``; при отказе — 403 ``Access denied``."""

    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if not auth_mod.admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]
