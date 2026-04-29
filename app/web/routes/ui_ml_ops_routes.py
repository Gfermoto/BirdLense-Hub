"""ML/CV operator endpoints that do not require new weights."""

from __future__ import annotations

from flask import request

from models import db
from routes.http_guards import (
    require_ui_contributor_or_admin,
    require_ui_settings_unauthorized,
)
from services.ml_ops_service import (
    build_active_learning_pool_preview,
    build_ml_runtime_status,
    build_video_reid_match_payload,
    build_reid_summary,
    build_video_action_events_payload,
)


def register_ui_ml_ops_routes(app):
    """Register lightweight ML/CV helper routes."""

    @app.route("/api/ui/videos/<int:video_id>/action-events", methods=["GET"])
    def video_action_events(video_id: int):
        return build_video_action_events_payload(db.session, video_id)

    @app.route("/api/ui/videos/<int:video_id>/reid-match", methods=["GET"])
    @require_ui_contributor_or_admin
    def video_reid_match(video_id: int):
        return build_video_reid_match_payload(db.session, video_id)

    @app.route("/api/ui/system/active-learning/pool-preview", methods=["GET"])
    @require_ui_contributor_or_admin
    def active_learning_pool_preview():
        return build_active_learning_pool_preview(
            db.session,
            limit=request.args.get("limit", 100, type=int),
        )

    @app.route("/api/ui/system/reid/summary", methods=["GET"])
    @require_ui_contributor_or_admin
    def reid_summary():
        return build_reid_summary(db.session)

    @app.route("/api/ui/system/ml-runtime", methods=["GET"])
    @require_ui_settings_unauthorized
    def ml_runtime_status():
        return build_ml_runtime_status()
