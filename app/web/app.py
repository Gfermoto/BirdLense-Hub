import os
from datetime import datetime, timezone
from util import notify_app_startup
from flask import Flask
from flask_cors import CORS
import logging
from sqlalchemy import text
import routes.ui_routes
import routes.ui_system_routes
import routes.processor_routes
from models import db
from seed.seed import seed

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
    # Базовые origins + CORS_ORIGINS из env (через запятую, для своих IP)
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://birdlense.local",
        "http://birdlense.local:80",
        "http://localhost:8085",
        "http://127.0.0.1:8085",
        "http://192.168.1.11:8085",
        "https://birdlense.eyera.info",
        "http://birdlense.eyera.info",
    ]
    extra = os.environ.get("CORS_ORIGINS", "")
    if extra:
        cors_origins.extend(s.strip() for s in extra.split(",") if s.strip())
    CORS(app, resources={r"/*": {"origins": cors_origins, "supports_credentials": True}})
    app.config.from_object('config.Config')

    db.init_app(app)
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
        seed()
    routes.ui_routes.register_routes(app)
    routes.ui_system_routes.register_routes(app)
    routes.processor_routes.register_routes(app)
    notify_app_startup(app)
    return app


app = create_app()
