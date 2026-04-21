"""Product-facing recognition improvement routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app, jsonify

from routes.http_guards import require_ui_contributor_or_admin, require_ui_settings_password
from services.fusion_product_service import (
    build_recognition_improvement_summary,
    recognition_training_status_snapshot,
    rollback_recognition_model,
    start_recognition_training_background,
)

if TYPE_CHECKING:
    from flask import Flask


def register_ui_system_recognition_routes(app: Flask) -> None:
    @app.route("/api/ui/system/recognition-improvement", methods=["GET"])
    @require_ui_contributor_or_admin
    def system_recognition_improvement_summary():
        return jsonify(build_recognition_improvement_summary()), 200

    @app.route("/api/ui/system/recognition-improvement/train", methods=["POST"])
    @require_ui_settings_password
    def system_recognition_improvement_train():
        body, code = start_recognition_training_background(current_app._get_current_object())
        return jsonify(body), code

    @app.route("/api/ui/system/recognition-improvement/train/status", methods=["GET"])
    @require_ui_contributor_or_admin
    def system_recognition_improvement_train_status():
        return jsonify(recognition_training_status_snapshot()), 200

    @app.route("/api/ui/system/recognition-improvement/rollback", methods=["POST"])
    @require_ui_settings_password
    def system_recognition_improvement_rollback():
        return jsonify(rollback_recognition_model()), 200
