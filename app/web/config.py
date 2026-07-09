"""Параметры Flask и SQLAlchemy: секрет сессии, путь к SQLite/Postgres, пул соединений."""

import logging
import os

from services.runtime_env import is_production_runtime


# Secret key for Flask session (settings unlock)
_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
_is_production = is_production_runtime()
if not _SECRET_KEY:
    if _is_production:
        raise RuntimeError("FLASK_SECRET_KEY is required in production. Set it in app/.env or environment.")
    logging.warning("FLASK_SECRET_KEY not set — using default. Set it in production to prevent session forgery.")
    _SECRET_KEY = "birdlense-settings-session"
if _is_production:
    if not (os.environ.get("PROCESSOR_SECRET") or "").strip():
        raise RuntimeError("PROCESSOR_SECRET is required in production. Set it in app/.env or environment.")
    # STRICT_API_AUTH не требуется принудительно — middleware включается
    # только при явном BIRDLENSE_STRICT_API_AUTH=1. Без пароля в user_config
    # UI работает свободно; после задания пароля — авторизация.

# Локальная разработка (Vite, LAN): не хранить в app.py — один источник для CORS.
_CORS_LOCAL_DEV_ORIGINS_DEV = (
    "http://localhost:5173,http://127.0.0.1:5173,http://birdlense.local,"
    "http://birdlense.local:80,http://localhost:8085,http://127.0.0.1:8085"
)
_CORS_LOCAL_DEV_ORIGINS_DEFAULT = "" if _is_production else _CORS_LOCAL_DEV_ORIGINS_DEV


class Config:
    """Загрузка `SQLALCHEMY_*`, `SECRET_KEY`, каталога БД из DATA_DIR и переменных окружения."""

    _data_base = os.getenv("DATA_DIR") or os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "data")
    db_directory = os.path.join(_data_base, "db")
    os.makedirs(db_directory, exist_ok=True)
    db_path = os.path.join(db_directory, "birdlense.db")
    _database_url = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite: gthread + WAL (app.py). PostgreSQL: пул соединений под нагрузку.
    if _database_url.startswith("sqlite:"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "connect_args": {"check_same_thread": False, "timeout": 30},
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_size": int(os.getenv("SQLALCHEMY_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "15")),
        }
    SECRET_KEY = _SECRET_KEY
    # Верхняя граница размера тела HTTP (multipart upload). Без этого Werkzeug/Flask могут отдать 413
    # раньше, чем сработает логика video.file_test_max_upload_mb. Переменная — байты; по умолчанию ~80 GiB.
    MAX_CONTENT_LENGTH = int(
        os.getenv("FLASK_MAX_CONTENT_LENGTH", str(80 * 1024 * 1024 * 1024)),
    )
    # Built-in local/dev CORS origins (comma-separated). Пустая env — без этого набора (строгий режим).
    CORS_LOCAL_DEV_ORIGINS = os.getenv(
        "CORS_LOCAL_DEV_ORIGINS",
        _CORS_LOCAL_DEV_ORIGINS_DEFAULT,
    )
    # Optional built-in CORS origins (comma-separated). Keep empty by default for self-hosters.
    CORS_DEFAULT_ORIGINS = os.getenv("CORS_DEFAULT_ORIGINS", "")
