"""Админские и служебные маршруты ``/api/ui/system/*``: БД, ретеншн, виды, конфиг, отчёты."""

from datetime import datetime, timezone

from flask import current_app, request
from models import db

from routes.http_guards import (
    require_admin_track_regen,
    require_ui_settings_password,
    require_ui_settings_unauthorized,
)
from services.api_json_validation import parse_request_json_object_allow_empty
from services.cache import cache_get, cache_set
from services.processor_logs_service import LOG_LINES_DEFAULT
from services.system_admin_api_service import (
    build_config_audit_payload,
    compute_system_activity_uptime,
    processor_logs_tail_http_response,
    start_single_video_track_regeneration,
)
from services.system_domain_health_service import build_domain_health_payload
from services.system_tuning_workbench_service import (
    apply_tuning_preset,
    build_tuning_workbench_payload,
    rollback_tuning_workbench_profile,
    upsert_camera_tuning_profile,
)
from services.yolo_detector_health_service import build_yolo_detector_health_payload
from services.system_metrics_constants import _CACHE_SYSTEM_ACTIVITY_SEC
from services.system_metrics_sampler_service import start_system_metrics_sampler

import routes.ui_system_jobs_state as job_state


def register_routes(app):
    """Зарегистрировать расширенный набор system API (кроме metrics — отдельный модуль)."""
    from routes.ui_system_metrics_routes import register_ui_system_metrics_routes

    register_ui_system_metrics_routes(app)
    from routes.ui_system_diagnostics_routes import register_ui_system_diagnostics_routes

    register_ui_system_diagnostics_routes(app)
    from routes.ui_system_review_queue_routes import register_ui_system_review_queue_routes

    register_ui_system_review_queue_routes(app)
    from routes.ui_system_storage_routes import register_ui_system_storage_routes

    register_ui_system_storage_routes(app)
    from routes.ui_system_db_routes import register_ui_system_db_routes

    register_ui_system_db_routes(app)
    from routes.ui_system_fusion_routes import register_ui_system_fusion_routes

    register_ui_system_fusion_routes(app)
    from routes.ui_system_behavior_routes import register_ui_system_behavior_routes

    register_ui_system_behavior_routes(app)
    from routes.ui_system_recognition_routes import register_ui_system_recognition_routes

    register_ui_system_recognition_routes(app)
    from routes.ui_system_maintenance_routes import register_ui_system_maintenance_routes

    register_ui_system_maintenance_routes(app)
    from routes.ui_system_file_test_routes import register_ui_system_file_test_routes

    register_ui_system_file_test_routes(app)
    from routes.ui_system_jobs_routes import register_ui_system_jobs_routes

    register_ui_system_jobs_routes(app)
    @app.route("/api/ui/system/config-audit", methods=["GET"])
    @require_ui_settings_unauthorized
    def system_config_audit():
        return build_config_audit_payload()

    @app.route("/api/ui/system/logs", methods=["GET"])
    @require_ui_settings_password
    def get_processor_logs():
        """Return last N lines of processor.log for remote diagnostics."""
        return processor_logs_tail_http_response(
            request.args.get("lines", LOG_LINES_DEFAULT),
        )

    @app.route("/api/ui/system/domain-health", methods=["GET"])
    @require_ui_settings_password
    def system_domain_health():
        """Domain-level integrity snapshot for recordings, visits and species registry."""
        return build_domain_health_payload()

    @app.route("/api/ui/system/yolo-detector-health", methods=["GET"])
    @require_ui_settings_password
    def system_yolo_detector_health():
        """Live YOLO blind/healthy status from processor gauges and recent sessions."""
        try:
            hours = int(request.args.get("hours", 24))
        except (TypeError, ValueError):
            hours = 24
        return build_yolo_detector_health_payload(hours=hours)

    @app.route("/api/ui/system/tuning-workbench", methods=["GET"])
    @require_ui_settings_password
    def system_tuning_workbench():
        return build_tuning_workbench_payload()

    @app.route("/api/ui/system/tuning-workbench/apply-preset", methods=["POST"])
    @require_ui_settings_password
    def system_tuning_workbench_apply_preset():
        body, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        return apply_tuning_preset(preset_id=str((body or {}).get("preset_id") or ""))

    @app.route("/api/ui/system/tuning-workbench/camera-profile", methods=["POST"])
    @require_ui_settings_password
    def system_tuning_workbench_camera_profile():
        body, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        return upsert_camera_tuning_profile(
            camera_id=str((body or {}).get("camera_id") or ""),
            overrides=(body or {}).get("overrides"),
            experiment_tag=str((body or {}).get("experiment_tag") or ""),
            max_runtime_cost_delta=(
                (body or {}).get("max_runtime_cost_delta")
                if isinstance(body, dict)
                else None
            ),
        )

    @app.route("/api/ui/system/tuning-workbench/rollback", methods=["POST"])
    @require_ui_settings_password
    def system_tuning_workbench_rollback():
        return rollback_tuning_workbench_profile()

    @app.route("/api/ui/system/activity", methods=["GET"])
    def get_activity():
        month = request.args.get(
            "month",
            datetime.now(timezone.utc).strftime("%Y-%m"),
        )
        ack = f"system_activity:{month}"
        hit, ac = cache_get(ack)
        if hit:
            return ac
        out, code = compute_system_activity_uptime(db.session, month)
        if code == 200:
            cache_set(ack, out, _CACHE_SYSTEM_ACTIVITY_SEC)
        return out, code

    @app.route("/api/ui/system/regenerate-tracks/status", methods=["GET"])
    def regenerate_tracks_status():
        """Return last track regeneration result."""
        return job_state._regenerate_tracks_status, 200

    @app.route("/api/ui/videos/<int:video_id>/regenerate-tracks", methods=["POST"])
    @require_admin_track_regen
    def regenerate_tracks_single_video(video_id):
        """Перегенерация треков только для одной записи (админ при двухуровневом доступе)."""
        body, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        return start_single_video_track_regeneration(
            current_app._get_current_object(),
            video_id,
            body,
        )

    from routes.ui_system_species_registry_routes import register_ui_system_species_registry_routes

    register_ui_system_species_registry_routes(app)

    start_system_metrics_sampler(app)
