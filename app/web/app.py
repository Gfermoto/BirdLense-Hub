import os
import threading
from datetime import datetime, timezone
from util import notify_app_startup
from flask import Flask
from flask_cors import CORS
import logging
from sqlalchemy import text, event
from sqlalchemy.engine import Engine
import routes.ui_routes
import routes.ui_system_routes
import routes.processor_routes
from models import db
from seed.seed import seed
from services.species_registry_service import (
    ensure_species_registry_seeded,
    backfill_species_taxa,
    enrich_species_metadata_with_status,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to the console
    ]
)


def create_app():
    logging.getLogger(__name__).info(
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
        # Add detection_provider column if missing (migration)
        try:
            db.session.execute(text(
                "ALTER TABLE video_species ADD COLUMN detection_provider VARCHAR"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Add manually_corrected column if missing (migration)
        try:
            db.session.execute(text(
                "ALTER TABLE video_species ADD COLUMN manually_corrected INTEGER DEFAULT 0"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Add species.taxon_id if missing (registry migration)
        try:
            db.session.execute(text(
                "ALTER TABLE species ADD COLUMN taxon_id INTEGER"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Species metadata enrichment columns (migration)
        try:
            db.session.execute(text(
                "ALTER TABLE species ADD COLUMN metadata_status VARCHAR DEFAULT 'pending'"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        try:
            db.session.execute(text(
                "ALTER TABLE species ADD COLUMN metadata_attempts INTEGER DEFAULT 0"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        try:
            db.session.execute(text(
                "ALTER TABLE species ADD COLUMN metadata_error VARCHAR"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        try:
            db.session.execute(text(
                "ALTER TABLE species ADD COLUMN metadata_source VARCHAR"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        try:
            db.session.execute(text(
                "ALTER TABLE species ADD COLUMN metadata_source_url VARCHAR"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        try:
            db.session.execute(text(
                "ALTER TABLE species ADD COLUMN metadata_updated_at DATETIME"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        seed()
        try:
            seed_stats = ensure_species_registry_seeded()
            logging.getLogger(__name__).info(
                "species_registry seed: taxa_created=%s aliases_created=%s",
                seed_stats.get("taxa_created", 0),
                seed_stats.get("aliases_created", 0),
            )
            # Safe incremental backfill of existing species rows.
            bf_stats = backfill_species_taxa(dry_run=False)
            logging.getLogger(__name__).info(
                "species_registry backfill: processed=%s matched=%s unresolved=%s",
                bf_stats.get("processed", 0),
                bf_stats.get("matched", 0),
                bf_stats.get("unresolved", 0),
            )
        except Exception as e:
            db.session.rollback()
            logging.getLogger(__name__).warning("species_registry init skipped: %s", e)

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


app = create_app()
