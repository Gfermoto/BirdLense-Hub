"""Маршруты bulk delete для review queue (#265)."""

from __future__ import annotations

from flask import request

from models import db
from routes.http_guards import require_admin_track_regen
from services.review_queue_bulk_delete_api_service import (
    build_review_queue_delete_preview_payload,
    execute_review_queue_bulk_delete,
)


def register_ui_system_review_queue_routes(app):
    """Маршруты ``/api/ui/system/review-queue/*``."""

    @app.route("/api/ui/system/review-queue/delete-preview", methods=["POST"])
    @require_admin_track_regen
    def preview_review_queue_delete():
        body, code = build_review_queue_delete_preview_payload(
            db.session,
            request.get_json(silent=True) or {},
        )
        return body, code

    @app.route("/api/ui/system/review-queue/delete", methods=["POST"])
    @require_admin_track_regen
    def delete_review_queue_videos():
        body, code = execute_review_queue_bulk_delete(
            db.session,
            request.get_json(silent=True) or {},
        )
        return body, code
