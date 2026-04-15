"""Маршруты bulk delete для review queue (#265)."""

from __future__ import annotations

from flask import request

from models import db
from routes.http_guards import require_ui_contributor_or_admin
from services.api_json_validation import parse_request_json_object_allow_empty
from services.review_queue_bulk_delete_api_service import (
    build_review_queue_delete_preview_payload,
    execute_review_queue_bulk_delete,
)


def register_ui_system_review_queue_routes(app):
    """Маршруты ``/api/ui/system/review-queue/*``."""

    @app.route("/api/ui/system/review-queue/delete-preview", methods=["POST"])
    @require_ui_contributor_or_admin
    def preview_review_queue_delete():
        payload, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        body, code = build_review_queue_delete_preview_payload(
            db.session,
            payload,
        )
        return body, code

    @app.route("/api/ui/system/review-queue/delete", methods=["POST"])
    @require_ui_contributor_or_admin
    def delete_review_queue_videos():
        payload, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        body, code = execute_review_queue_bulk_delete(
            db.session,
            payload,
        )
        return body, code
