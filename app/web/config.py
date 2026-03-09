import os


class Config:
    _data_base = os.getenv('DATA_DIR') or os.path.join(
        os.path.abspath(os.path.dirname(__file__)), '..', 'data')
    db_directory = os.path.join(_data_base, 'db')
    os.makedirs(db_directory, exist_ok=True)
    db_path = os.path.join(db_directory, 'birdlense.db')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', f'sqlite:///{db_path}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
