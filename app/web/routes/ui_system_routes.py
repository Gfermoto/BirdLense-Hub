"""Админские и служебные маршруты ``/api/ui/system/*``: БД, ретеншн, виды, конфиг, отчёты."""
import os
import threading
from datetime import datetime, timezone

from flask import request
from models import db, Video

from app_config.app_config import app_config
from auth import admin_track_regen_access
from util import settings_check_access
from services.cache import cache_get, cache_set
from services.processor_logs_service import (
    LOG_LINES_DEFAULT,
    clamp_processor_log_line_count,
    read_processor_log_tail,
)
from services.system_activity_service import (
    SystemActivityMonthError,
    fetch_system_activity_daily_uptime,
    parse_system_activity_month,
)
from services.system_config_audit_service import build_system_config_audit_payload
from services.system_metrics_constants import _CACHE_SYSTEM_ACTIVITY_SEC
from services.system_metrics_sampler_service import start_system_metrics_sampler
from services.system_spectrogram_regen_service import run_regenerate_spectrograms_worker
from services.system_track_regen_worker import run_regenerate_tracks_worker

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
        return build_system_config_audit_payload(
            user_config_file=app_config.user_config_file,
            default_config_file=app_config.default_config_file,
            app_config_get=app_config.get,
        ), 200

    @app.route('/api/ui/system/logs', methods=['GET'])
    def get_processor_logs():
        """Return last N lines of processor.log for remote diagnostics."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        lines = clamp_processor_log_line_count(
            request.args.get('lines', LOG_LINES_DEFAULT),
        )
        try:
            return read_processor_log_tail(lines)
        except OSError:
            app.logger.exception('Get processor logs failed')
            return {'error': 'Failed to read logs', 'lines': []}, 500

    @app.route('/api/ui/system/activity', methods=['GET'])
    def get_activity():
        month = request.args.get('month', datetime.now(timezone.utc).strftime('%Y-%m'))
        try:
            start_date, end_date = parse_system_activity_month(month)
        except SystemActivityMonthError as exc:
            return {'error': str(exc)}, 400
        ack = f'system_activity:{month}'
        hit, ac = cache_get(ack)
        if hit:
            return ac
        out = fetch_system_activity_daily_uptime(db.session, start_date, end_date)
        cache_set(ack, out, _CACHE_SYSTEM_ACTIVITY_SEC)
        return out

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
        mqtt_broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
        birdnet_configured = bool(
            mqtt_broker and (app_config.get('mqtt.birdnet_topic') or '').strip()
        )
        if not birdnet_configured:
            return {
                'error': 'Spectrogram regeneration requires BirdNET (MQTT broker + birdnet_topic)',
            }, 400
        with job_state._regenerate_lock:
            if job_state._regenerate_status['status'] == 'running':
                return {
                    'error': 'Regeneration already in progress',
                    'status': job_state._regenerate_status,
                }, 409
        data = request.json or {}
        force = data.get('force', False)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        threading.Thread(
            target=run_regenerate_spectrograms_worker,
            args=(app, force, start_date, end_date, None),
            daemon=True,
        ).start()
        return {
            'message': 'Regeneration started in background.',
            'started': True,
        }, 202

    @app.route('/api/ui/videos/<int:video_id>/regenerate-spectrogram', methods=['POST'])
    def regenerate_spectrogram_single_video(video_id):
        """Перегенерация спектрограммы для одной записи (админ при двухуровневом доступе)."""
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        video = db.session.get(Video, video_id)
        if not video:
            return {'error': 'Video not found'}, 404
        with job_state._regenerate_lock:
            if job_state._regenerate_status['status'] == 'running':
                return {
                    'error': 'Regeneration already in progress',
                    'status': job_state._regenerate_status,
                }, 409
        threading.Thread(
            target=run_regenerate_spectrograms_worker,
            args=(app, True, None, None, [video_id]),
            daemon=True,
        ).start()
        return {
            'message': 'Spectrogram regeneration started for this video.',
            'started': True,
            'video_id': video_id,
        }, 202

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
        video = db.session.get(Video, video_id)
        if not video:
            return {'error': 'Video not found'}, 404
        data = request.json or {}
        force = bool(data.get('force', False))
        with job_state._regenerate_tracks_lock:
            if job_state._regenerate_tracks_status['status'] == 'running':
                return {
                    'error': 'Track regeneration already in progress',
                    'status': job_state._regenerate_tracks_status,
                }, 409
        threading.Thread(
            target=run_regenerate_tracks_worker,
            args=(app, force, None, None, None, [video_id], []),
            daemon=True,
        ).start()
        return {
            'message': 'Track regeneration started for this video.',
            'started': True,
            'video_id': video_id,
        }, 202

    from routes.ui_system_species_registry_routes import register_ui_system_species_registry_routes
    register_ui_system_species_registry_routes(app)

    start_system_metrics_sampler(app)
