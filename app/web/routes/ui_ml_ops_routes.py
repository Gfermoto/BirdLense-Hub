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
    build_classifier_calibration_report_payload,
    build_dataset_streams_summary,
    build_feedback_loop_export_payload,
    build_feedback_loop_status_payload,
    build_ml_runtime_status,
    build_similarity_summary_payload,
    build_video_reid_match_payload,
    build_reid_summary,
)
from services.api_json_validation import parse_request_json_object_allow_empty


def register_ui_ml_ops_routes(app):
    """Register lightweight ML/CV helper routes."""

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

    @app.route("/api/ui/system/reid/similarity-summary", methods=["GET"])
    @require_ui_contributor_or_admin
    def reid_similarity_summary():
        return build_similarity_summary_payload(
            db.session,
            top_k=request.args.get("top_k", 5, type=int),
            max_rows=request.args.get("max_rows", 500, type=int),
        )

    @app.route("/api/ui/system/feedback-loop/status", methods=["GET"])
    @require_ui_contributor_or_admin
    def feedback_loop_status():
        return build_feedback_loop_status_payload(db.session)

    @app.route("/api/ui/system/feedback-loop/export", methods=["POST"])
    @require_ui_contributor_or_admin
    def feedback_loop_export():
        data, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        return build_feedback_loop_export_payload(data)

    @app.route("/api/ui/system/ml-runtime", methods=["GET"])
    @require_ui_settings_unauthorized
    def ml_runtime_status():
        return build_ml_runtime_status()

    @app.route("/api/ui/system/dataset-streams", methods=["GET"])
    @require_ui_contributor_or_admin
    def dataset_streams_summary():
        return build_dataset_streams_summary()

    @app.route("/api/ui/system/classifier-calibration-report", methods=["GET"])
    @require_ui_contributor_or_admin
    def classifier_calibration_report():
        return build_classifier_calibration_report_payload(
            pair_limit=request.args.get("pair_limit", 15, type=int),
        )
