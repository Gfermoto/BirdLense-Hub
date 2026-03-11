import os
from util import notify
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
    app = Flask(__name__)
    # Базовые origins + CORS_ORIGINS из env (через запятую, для своих IP)
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://birdlense.local",
        "http://birdlense.local:80",
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
        seed()
    routes.ui_routes.register_routes(app)
    routes.ui_system_routes.register_routes(app)
    routes.processor_routes.register_routes(app)
    notify(f"App is UP!", tags="rocket")
    return app


app = create_app()
