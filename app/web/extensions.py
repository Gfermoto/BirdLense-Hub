"""Flask extensions: SQLAlchemy, Migrate, CORS, SQLite PRAGMA (см. #292)."""
from __future__ import annotations

import os

from flask import Flask
from flask_migrate import Migrate

from flask_extensions import apply_cors, register_sqlite_connect_pragmas
from models import db

migrate = Migrate()


def init_extensions(app: Flask) -> None:
    """Подключить CORS, db, Alembic/Flask-Migrate, PRAGMA на connect."""
    apply_cors(app)
    db.init_app(app)
    web_dir = os.path.dirname(os.path.abspath(__file__))
    migrations_dir = os.path.join(web_dir, 'migrations')
    migrate.init_app(app, db, directory=migrations_dir)
    register_sqlite_connect_pragmas()
