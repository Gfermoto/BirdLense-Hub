"""Админские и служебные маршруты ``/api/ui/system/*``: БД, ретеншн, виды, конфиг, отчёты."""
from datetime import datetime, timezone

from flask import current_app, request
from models import db

from auth import admin_track_regen_access
from util import settings_check_access
from services.cache import cache_get, cache_set
from services.processor_logs_service import LOG_LINES_DEFAULT
from services.system_admin_api_service import (
    build_config_audit_payload,
    compute_system_activity_uptime,
    processor_logs_tail_http_response,
    start_bulk_spectrogram_regeneration,
    start_single_video_spectrogram_regeneration,
    start_single_video_track_regeneration,
)
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
    from routes.ui_system_maintenance_routes import register_ui_system_maintenance_routes
    register_ui_system_maintenance_routes(app)

    @app.route('/api/ui/system/config-audit', methods=['GET'])
    def system_config_audit():
        if not settings_check_access():
            return {'error': 'Unauthorized'}, 401
        return build_config_audit_payload()

    @app.route('/api/ui/system/logs', methods=['GET'])
    def get_processor_logs():
        """Return last N lines of processor.log for remote diagnostics."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        return processor_logs_tail_http_response(
            request.args.get('lines', LOG_LINES_DEFAULT),
        )

    @app.route('/api/ui/system/activity', methods=['GET'])
    def get_activity():
        month = request.args.get(
            'month',
            datetime.now(timezone.utc).strftime('%Y-%m'),
        )
        ack = f'system_activity:{month}'
        hit, ac = cache_get(ack)
        if hit:
            return ac
        out, code = compute_system_activity_uptime(db.session, month)
        if code == 200:
            cache_set(ack, out, _CACHE_SYSTEM_ACTIVITY_SEC)
        return out, code

    @app.route('/api/ui/system/regenerate-spectrograms', methods=['POST'])
    def regenerate_spectrograms():
        """
        Start spectrogram regeneration in background. Returns immediately.
        Processes videos without spectrograms (or all if force=true).
        Only available when BirdNET is configured (MQTT broker + birdnet_topic).
        Poll GET .../status to get result.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        body = request.get_json(silent=True) or {}
        return start_bulk_spectrogram_regeneration(
            current_app._get_current_object(),
            body,
        )

    @app.route('/api/ui/videos/<int:video_id>/regenerate-spectrogram', methods=['POST'])
    def regenerate_spectrogram_single_video(video_id):
        """Перегенерация спектрограммы для одной записи (админ при двухуровневом доступе)."""
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        return start_single_video_spectrogram_regeneration(
            current_app._get_current_object(),
            video_id,
        )

    @app.route('/api/ui/system/regenerate-spectrograms/status', methods=['GET'])
    def regenerate_spectrograms_status():
        """Return last regeneration result: {status, result: {generated, failed, skipped}, error}."""
        return job_state._regenerate_status, 200

    @app.route('/api/ui/system/regenerate-tracks/status', methods=['GET'])
    def regenerate_tracks_status():
        """Return last track regeneration result."""
        return job_state._regenerate_tracks_status, 200

    @app.route('/api/ui/videos/<int:video_id>/regenerate-tracks', methods=['POST'])
    def regenerate_tracks_single_video(video_id):
        """Перегенерация треков только для одной записи (админ при двухуровневом доступе)."""
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        body = request.get_json(silent=True) or {}
        return start_single_video_track_regeneration(
            current_app._get_current_object(),
            video_id,
            body,
        )

    from routes.ui_system_species_registry_routes import register_ui_system_species_registry_routes
    register_ui_system_species_registry_routes(app)

    start_system_metrics_sampler(app)
