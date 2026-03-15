import logging
import os

# Secret key for Flask session (settings unlock)
_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
if not _SECRET_KEY:
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
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', f'sqlite:///{db_path}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = _SECRET_KEY
