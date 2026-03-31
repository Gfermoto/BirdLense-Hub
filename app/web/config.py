import logging
import os

# Secret key for Flask session (settings unlock)
_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
_is_production = (
    os.environ.get('FLASK_ENV') == 'production'
    or os.environ.get('BIRDLENSE_ENV') == 'production'
)
if not _SECRET_KEY:
    if _is_production:
        raise RuntimeError(
            'FLASK_SECRET_KEY is required in production. '
            'Set it in app/.env or environment.'
        )
    logging.warning(
        'FLASK_SECRET_KEY not set — using default. Set it in production to prevent session forgery.'
    )
    _SECRET_KEY = 'birdlense-settings-session'


class Config:
    _data_base = os.getenv('DATA_DIR') or os.path.join(
        os.path.abspath(os.path.dirname(__file__)), '..', 'data')
    db_directory = os.path.join(_data_base, 'db')
    os.makedirs(db_directory, exist_ok=True)
    db_path = os.path.join(db_directory, 'birdlense.db')
    _database_url = os.getenv('DATABASE_URL', f'sqlite:///{db_path}')
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite: gthread + WAL (app.py). PostgreSQL: пул соединений под нагрузку.
    if _database_url.startswith('sqlite:'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'connect_args': {'check_same_thread': False, 'timeout': 30},
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_size': int(os.getenv('SQLALCHEMY_POOL_SIZE', '5')),
            'max_overflow': int(os.getenv('SQLALCHEMY_MAX_OVERFLOW', '15')),
        }
    SECRET_KEY = _SECRET_KEY
    # Optional built-in CORS origins (comma-separated). Keep empty by default for self-hosters.
    CORS_DEFAULT_ORIGINS = os.getenv('CORS_DEFAULT_ORIGINS', '')
