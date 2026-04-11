"""Flask entry: app factory, DB bootstrap, route registration."""
import logging
import os

from flask import Flask
from flask_migrate import Migrate

from app_startup import (
    apply_schema_migrations_and_seed,
    bootstrap_legacy_import_cleanup,
    bootstrap_species_metadata_enrich,
    bootstrap_species_metadata_repair,
    bootstrap_species_registry,
)
from flask_extensions import apply_cors, register_sqlite_connect_pragmas
from models import db
import routes.processor_routes
import routes.ui_routes
import routes.ui_system_routes
from util import notify_app_startup

migrate = Migrate()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to the console
    ]
)

_log = logging.getLogger(__name__)


def create_app():
    """Собрать BirdLense Hub: CORS, БД, фоновые задачи, UI и processor API."""
    _log.info(
        'create_app() invoked (pid=%s)',
        os.getpid(),
    )
    app = Flask(__name__)
    app.config.from_object('config.Config')
    apply_cors(app)

    db.init_app(app)
    _web_dir = os.path.dirname(os.path.abspath(__file__))
    _migrations_dir = os.path.join(_web_dir, 'migrations')
    migrate.init_app(app, db, directory=_migrations_dir)
    register_sqlite_connect_pragmas()

    with app.app_context():
        apply_schema_migrations_and_seed(_migrations_dir)
        bootstrap_species_registry()
        bootstrap_legacy_import_cleanup()
        bootstrap_species_metadata_repair(app)
        bootstrap_species_metadata_enrich(app)
    routes.ui_routes.register_routes(app)
    routes.ui_system_routes.register_routes(app)
    routes.processor_routes.register_routes(app)
    notify_app_startup(app)
    return app


# Tests call create_app(); prod gunicorn uses app:app when import creates app.
# FLASK_CREATE_APP_ON_IMPORT=0 skips auto-create (e.g. FLASK_TESTING).
_create_flag = os.environ.get('FLASK_CREATE_APP_ON_IMPORT', '1').strip().lower()
if _create_flag in ('1', 'true', 'yes') and not os.environ.get('FLASK_TESTING'):
    app = create_app()
else:
    app = None
