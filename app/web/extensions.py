"""Flask extensions: SQLAlchemy, Migrate, CORS, SQLite PRAGMA (см. #292)."""

from __future__ import annotations

import os

from flask import Flask
from flask_migrate import Migrate

from flask_extensions import apply_cors, register_sqlite_connect_pragmas
from models import db
from services.session_idle_service import register_session_idle_middleware
from services.strict_ui_api_auth_service import (
    register_strict_ui_api_auth_middleware,
)
from services.upload_request_encoding_guard import (
    register_upload_request_encoding_guard,
)

migrate = Migrate()


def init_extensions(app: Flask) -> None:
    """Подключить CORS, db, Alembic/Flask-Migrate, PRAGMA на connect."""
    apply_cors(app)
    register_sqlite_connect_pragmas()
    db.init_app(app)
    web_dir = os.path.dirname(os.path.abspath(__file__))
    migrations_dir = os.path.join(web_dir, "migrations")
    migrate.init_app(app, db, directory=migrations_dir)
    register_strict_ui_api_auth_middleware(app)
    register_session_idle_middleware(app)
    register_upload_request_encoding_guard(app)
