"""Обвязка Flask/SQLAlchemy для create_app: CORS, PRAGMA SQLite при connect."""

from __future__ import annotations

import os

from flask import Flask
from flask_cors import CORS
from sqlalchemy import event
from sqlalchemy.engine import Engine


def apply_cors(app: Flask) -> None:
    """Включить CORS: dev origins из config, default и переменная CORS_ORIGINS."""
    cors_origins: list[str] = []
    local_dev = (app.config.get("CORS_LOCAL_DEV_ORIGINS") or "").strip()
    if local_dev:
        cors_origins.extend(s.strip() for s in local_dev.split(",") if s.strip())
    default_extra = app.config.get("CORS_DEFAULT_ORIGINS", "")
    if default_extra:
        cors_origins.extend(s.strip() for s in default_extra.split(",") if s.strip())
    runtime_extra = os.environ.get("CORS_ORIGINS", "")
    if runtime_extra:
        cors_origins.extend(s.strip() for s in runtime_extra.split(",") if s.strip())
    CORS(
        app,
        resources={
            r"/*": {"origins": cors_origins, "supports_credentials": True},
        },
    )


def register_sqlite_connect_pragmas() -> None:
    """PRAGMA на каждое подключение к SQLite (WAL, кэш, temp)."""

    @event.listens_for(Engine, "connect")
    def _sqlite_optimize(dbapi_connection, _connection_record):
        """WAL и кэш: меньше блокировок и I/O на большой SQLite."""
        try:
            import sqlite3
        except ImportError:
            return
        if not isinstance(dbapi_connection, sqlite3.Connection):
            return
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA cache_size=-64000")
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.close()
