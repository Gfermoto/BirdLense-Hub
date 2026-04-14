"""Flask entry: фабрика приложения, оркестрация bootstrap и маршрутов (#292)."""

import logging
import os

from flask import Flask

from app_logging import configure_process_logging, init_request_logging
from app_startup import (
    apply_schema_migrations_and_seed,
    bootstrap_legacy_import_cleanup,
    bootstrap_species_metadata_enrich,
    bootstrap_species_metadata_repair,
    bootstrap_species_registry,
)
from errors import register_error_handlers
from extensions import init_extensions
from routes import register_all_routes
from util import notify_app_startup

configure_process_logging()

_log = logging.getLogger(__name__)


def create_app():
    """Собрать BirdLense Hub: CORS, БД, фоновые задачи, UI и processor API."""
    _log.info(
        "create_app() invoked (pid=%s)",
        os.getpid(),
    )
    app = Flask(__name__)
    app.config.from_object("config.Config")
    init_extensions(app)
    init_request_logging(app)
    register_error_handlers(app)

    _web_dir = os.path.dirname(os.path.abspath(__file__))
    _migrations_dir = os.path.join(_web_dir, "migrations")

    with app.app_context():
        apply_schema_migrations_and_seed(_migrations_dir)
        bootstrap_species_registry()
        bootstrap_legacy_import_cleanup()
        bootstrap_species_metadata_repair(app)
        bootstrap_species_metadata_enrich(app)
    register_all_routes(app)
    notify_app_startup(app)
    return app


# Tests call create_app(); prod gunicorn uses app:app when import creates app.
# FLASK_CREATE_APP_ON_IMPORT=0 skips auto-create (e.g. FLASK_TESTING).
_create_flag = os.environ.get("FLASK_CREATE_APP_ON_IMPORT", "1").strip().lower()
if _create_flag in ("1", "true", "yes") and not os.environ.get("FLASK_TESTING"):
    app = create_app()
else:
    app = None
