"""Маршруты bulk delete для review queue (#265)."""

from __future__ import annotations

from flask import request

from auth import admin_track_regen_access
from models import db
from services.review_queue_bulk_delete_api_service import (
    build_review_queue_delete_preview_payload,
    execute_review_queue_bulk_delete,
)


def register_ui_system_review_queue_routes(app):
    """Маршруты ``/api/ui/system/review-queue/*``."""

    @app.route('/api/ui/system/review-queue/delete-preview', methods=['POST'])
    def preview_review_queue_delete():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        body, code = build_review_queue_delete_preview_payload(
            db.session,
            request.get_json(silent=True) or {},
        )
        return body, code

    @app.route('/api/ui/system/review-queue/delete', methods=['POST'])
    def delete_review_queue_videos():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        body, code = execute_review_queue_bulk_delete(
            db.session,
            request.get_json(silent=True) or {},
        )
        return body, code
