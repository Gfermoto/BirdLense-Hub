"""Flask extensions: SQLAlchemy, Migrate, CORS, SQLite PRAGMA (см. #292)."""

from __future__ import annotations

import os

from flask import Flask, request
from flask_migrate import Migrate
try:
    from flask_limiter import Limiter
except ModuleNotFoundError:  # pragma: no cover - local/dev env fallback
    class Limiter:  # type: ignore[override]
        """No-op fallback when flask_limiter is unavailable."""

        def __init__(self, *args, **kwargs):
            self.enabled = False

        def init_app(self, app: Flask) -> None:
            app.logger.warning(
                "flask_limiter not installed; rate limiter disabled"
            )

        def limit(self, *args, **kwargs):
            def _decorator(fn):
                return fn

            return _decorator

from auth import client_ip_for_rate_limit
from flask_extensions import apply_cors, register_sqlite_connect_pragmas
from models import db
from services.csrf_service import register_csrf_protection
from services.session_idle_service import register_session_idle_middleware
from services.strict_ui_api_auth_service import (
    register_strict_ui_api_auth_middleware,
)
from services.upload_request_encoding_guard import (
    register_upload_request_encoding_guard,
)

migrate = Migrate()


def _rate_limit_remote_ip() -> str:
    """Тот же IP, что и для verify-password (TRUSTED_PROXY)."""
    return client_ip_for_rate_limit(request)


limiter = Limiter(
    key_func=_rate_limit_remote_ip,
    storage_uri=os.environ.get("BIRDLENSE_RATELIMIT_STORAGE_URI", "memory://"),
)


def init_extensions(app: Flask) -> None:
    """Подключить CORS, db, Alembic/Flask-Migrate, PRAGMA на connect."""
    apply_cors(app)
    register_sqlite_connect_pragmas()
    db.init_app(app)
    web_dir = os.path.dirname(os.path.abspath(__file__))
    migrations_dir = os.path.join(web_dir, "migrations")
    migrate.init_app(app, db, directory=migrations_dir)
    # Idle до strict/CSRF: сброс просроченной сессии до проверок.
    register_session_idle_middleware(app)
    register_csrf_protection(app)
    register_strict_ui_api_auth_middleware(app)
    register_upload_request_encoding_guard(app)
    limiter.init_app(app)
    if os.environ.get("BIRDLENSE_RATELIMIT_DISABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        limiter.enabled = False
