"""Точка входа Flask: фабрика приложения, БД (create_all + Alembic), регистрация маршрутов."""
import os
import threading
from util import notify_app_startup
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate, upgrade
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine
import routes.ui_routes
import routes.ui_system_routes
import routes.processor_routes
from models import db, Species
from seed.seed import seed
from services.species_registry_service import (
    ensure_species_registry_seeded,
    backfill_species_taxa,
    repair_recently_reset_species_metadata,
    enrich_species_metadata_with_status,
)

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


def _env_truthy(name: str, default: str = '0') -> bool:
    return (os.environ.get(name, default) or default).strip().lower() in (
        '1', 'true', 'yes',
    )


def create_app():
    """Собрать приложение BirdLense Hub: CORS, БД, опциональные фоновые задачи, UI и processor API."""
    _log.info(
        "create_app() invoked (pid=%s)",
        os.getpid()
    )
    app = Flask(__name__)
    app.config.from_object('config.Config')
    # Базовые origins + CORS_DEFAULT_ORIGINS/CORS_ORIGINS из env (через запятую, для своих IP/доменов)
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://birdlense.local",
        "http://birdlense.local:80",
        "http://localhost:8085",
        "http://127.0.0.1:8085",
    ]
    default_extra = app.config.get("CORS_DEFAULT_ORIGINS", "")
    if default_extra:
        cors_origins.extend(s.strip() for s in default_extra.split(",") if s.strip())
    runtime_extra = os.environ.get("CORS_ORIGINS", "")
    if runtime_extra:
        cors_origins.extend(s.strip() for s in runtime_extra.split(",") if s.strip())
    CORS(app, resources={r"/*": {"origins": cors_origins, "supports_credentials": True}})

    db.init_app(app)
    _migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
    migrate.init_app(app, db, directory=_migrations_dir)

    @event.listens_for(Engine, "connect")
    def _sqlite_optimize(dbapi_connection, _connection_record):
        """Чтения параллельнее записи; кэш страниц — меньше I/O на большой БД."""
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

    with app.app_context():
        db.create_all()
        upgrade(directory=_migrations_dir)
        seed()
        try:
            seed_stats = ensure_species_registry_seeded()
            _log.info(
                "species_registry seed: taxa_created=%s aliases_created=%s",
                seed_stats.get("taxa_created", 0),
                seed_stats.get("aliases_created", 0),
            )
            # Тяжёлый backfill на старте только по явному флагу (auditing: избегать скрытых мутаций).
            if _env_truthy('BIRDLENSE_STARTUP_BACKFILL_SPECIES_TAXA'):
                bf_stats = backfill_species_taxa(dry_run=False)
                _log.info(
                    "species_registry backfill: processed=%s matched=%s unresolved=%s",
                    bf_stats.get("processed", 0),
                    bf_stats.get("matched", 0),
                    bf_stats.get("unresolved", 0),
                )
            else:
                _log.info(
                    "species_registry backfill skipped "
                    "(set BIRDLENSE_STARTUP_BACKFILL_SPECIES_TAXA=1 or use POST "
                    "/api/ui/system/species-registry/backfill)",
                )
        except Exception as e:
            db.session.rollback()
            _log.warning("species_registry init skipped: %s", e)
        try:
            if _env_truthy('BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT'):
                cleaned_rows, cleaned_visits = (
                    routes.ui_system_routes._cleanup_legacy_import_placeholders()
                )
                if cleaned_rows or cleaned_visits:
                    db.session.commit()
                    _log.info(
                        "legacy import cleanup: detections_removed=%s visits_removed=%s",
                        cleaned_rows,
                        cleaned_visits,
                    )
            else:
                _log.info(
                    "legacy import cleanup on startup skipped "
                    "(set BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=1; scan import still cleans)",
                )
        except Exception as e:
            db.session.rollback()
            _log.warning(
                "legacy import cleanup skipped: %s", e,
            )
        try:
            reset_victims = Species.query.filter(
                Species.image_url.is_(None),
                Species.description.isnot(None),
            ).count()
            repair_on_start = _env_truthy('BIRDLENSE_STARTUP_REPAIR_SPECIES_METADATA')
            if (
                reset_victims
                and not app.config.get('TESTING')
                and repair_on_start
            ):
                def _repair_reset_victims():
                    with app.app_context():
                        try:
                            stats = repair_recently_reset_species_metadata(
                                limit=reset_victims,
                                dry_run=False,
                            )
                            _log.info(
                                'species_metadata_repair: processed=%s repaired=%s failed=%s',
                                stats.get('processed', 0),
                                stats.get('repaired', 0),
                                stats.get('failed', 0),
                            )
                        except Exception as repair_err:
                            db.session.rollback()
                            _log.warning(
                                'species_metadata_repair skipped: %s',
                                repair_err,
                            )

                threading.Thread(target=_repair_reset_victims, daemon=True).start()
            elif reset_victims and not app.config.get('TESTING') and not repair_on_start:
                _log.info(
                    'species metadata repair on startup skipped '
                    '(%s rows eligible; set BIRDLENSE_STARTUP_REPAIR_SPECIES_METADATA=1)',
                    reset_victims,
                )
        except Exception as e:
            db.session.rollback()
            _log.warning('species metadata repair setup skipped: %s', e)

        # Optional metadata enrichment kickoff (disabled by default).
        # Enable with SPECIES_METADATA_ENRICH_ON_START=1 for controlled maintenance runs.
        try:
            enrich_on_start = os.environ.get('SPECIES_METADATA_ENRICH_ON_START', '0').strip() in ('1', 'true', 'yes')
            if not app.config.get('TESTING') and enrich_on_start:
                marker = '/tmp/.birdlense_species_metadata_enrich_started'
                if not os.path.exists(marker):
                    try:
                        open(marker, 'a').close()
                    except OSError:
                        pass

                    def _background_enrich():
                        with app.app_context():
                            log = logging.getLogger(__name__)
                            try:
                                stats = enrich_species_metadata_with_status(
                                    limit=300,
                                    dry_run=False,
                                    retry_failed_only=False,
                                )
                                log.info(
                                    'species_metadata_enrich pass1: processed=%s updated=%s failed=%s',
                                    stats.get('processed', 0),
                                    stats.get('updated', 0),
                                    stats.get('failed', 0),
                                )
                                retry_stats = enrich_species_metadata_with_status(
                                    limit=300,
                                    dry_run=False,
                                    retry_failed_only=True,
                                )
                                log.info(
                                    'species_metadata_enrich retry: processed=%s updated=%s failed=%s',
                                    retry_stats.get('processed', 0),
                                    retry_stats.get('updated', 0),
                                    retry_stats.get('failed', 0),
                                )
                            except Exception as enrich_err:
                                log.warning('species_metadata_enrich skipped: %s', enrich_err)

                    threading.Thread(target=_background_enrich, daemon=True).start()
        except Exception as e:
            logging.getLogger(__name__).warning('species_metadata_enrich setup failed: %s', e)
    routes.ui_routes.register_routes(app)
    routes.ui_system_routes.register_routes(app)
    routes.processor_routes.register_routes(app)
    notify_app_startup(app)
    return app


# Do not create the app automatically on import in test environments.
# Tests use the `create_app` factory directly. For production (gunicorn),
# set FLASK_CREATE_APP_ON_IMPORT=1 (default) or ensure WSGI loads the factory.
_create_on_import = os.environ.get('FLASK_CREATE_APP_ON_IMPORT', '1').strip().lower()
if _create_on_import in ('1', 'true', 'yes') and not os.environ.get('FLASK_TESTING'):
    app = create_app()
else:
    app = None
