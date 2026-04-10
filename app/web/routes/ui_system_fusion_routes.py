"""Fusion export/eval и refresh Telegram proxy (#265)."""
from __future__ import annotations

import threading

from flask import request, send_file

import routes.ui_system_jobs_state as job_state
from services.fusion_training_service import (
    latest_fusion_export_path as _latest_fusion_export_path,
    run_fusion_eval_job as _run_fusion_eval_job,
    run_fusion_export_job as _run_fusion_export_job,
)
from services.telegram_proxy_service import (
    refresh_telegram_proxy as refresh_telegram_proxy_service,
)
from util import settings_check_access


def register_ui_system_fusion_routes(app):
    """Fusion CSV и Telegram proxy refresh."""

    @app.route('/api/ui/system/fusion/export', methods=['POST'])
    def fusion_export():
        """Export decision traces to CSV for fusion calibration/training."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with job_state._fusion_export_lock:
            if job_state._fusion_export_status['status'] == 'running':
                return {'error': 'Fusion export already in progress', 'status': job_state._fusion_export_status}, 409
            job_state._fusion_export_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': None,
            })

        def _run():
            try:
                with app.app_context():
                    result = _run_fusion_export_job()
                with job_state._fusion_export_lock:
                    job_state._fusion_export_status.update({
                        'status': 'done',
                        'result': result,
                        'error': None,
                        'progress': None,
                    })
            except Exception as e:
                with job_state._fusion_export_lock:
                    job_state._fusion_export_status.update({
                        'status': 'error',
                        'result': None,
                        'error': str(e),
                        'progress': None,
                    })

        threading.Thread(target=_run, daemon=True).start()
        return {'message': 'Fusion export started', 'status': job_state._fusion_export_status}, 202

    @app.route('/api/ui/system/fusion/export/status', methods=['GET'])
    def fusion_export_status():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with job_state._fusion_export_lock:
            return dict(job_state._fusion_export_status), 200

    @app.route('/api/ui/system/fusion/export/download', methods=['GET'])
    def fusion_export_download():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        latest = _latest_fusion_export_path()
        if not latest or not latest.exists():
            return {'error': 'Fusion export not found'}, 404
        return send_file(
            latest,
            as_attachment=True,
            download_name=latest.name,
            mimetype='text/csv',
        )

    @app.route('/api/ui/system/fusion/eval', methods=['POST'])
    def fusion_eval():
        """Evaluate fusion calibration on a CSV export."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with job_state._fusion_eval_lock:
            if job_state._fusion_eval_status['status'] == 'running':
                return {'error': 'Fusion eval already in progress', 'status': job_state._fusion_eval_status}, 409
            job_state._fusion_eval_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': None,
            })
        payload = request.get_json(silent=True) or {}

        def _run():
            try:
                with app.app_context():
                    result = _run_fusion_eval_job(
                        source_csv=payload.get('source_csv'),
                        model_path=payload.get('model_path'),
                        score_col=payload.get('score_col'),
                        label_col=payload.get('label_col', 'valid_track_label'),
                        slice_fields=list(payload.get('slice_fields') or []),
                    )
                with job_state._fusion_eval_lock:
                    job_state._fusion_eval_status.update({
                        'status': 'done',
                        'result': result,
                        'error': None,
                        'progress': None,
                    })
            except Exception as e:
                with job_state._fusion_eval_lock:
                    job_state._fusion_eval_status.update({
                        'status': 'error',
                        'result': None,
                        'error': str(e),
                        'progress': None,
                    })

        threading.Thread(target=_run, daemon=True).start()
        return {'message': 'Fusion eval started', 'status': job_state._fusion_eval_status}, 202

    @app.route('/api/ui/system/fusion/eval/status', methods=['GET'])
    def fusion_eval_status():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with job_state._fusion_eval_lock:
            return dict(job_state._fusion_eval_status), 200

    @app.route('/api/ui/system/telegram-proxy/refresh', methods=['POST'])
    def refresh_telegram_proxy():
        """Refresh Telegram SOCKS proxy using the backend service."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with job_state._telegram_proxy_refresh_lock:
            if job_state._telegram_proxy_refresh_status['status'] == 'running':
                return {
                    'error': 'Telegram proxy refresh already in progress',
                    'status': job_state._telegram_proxy_refresh_status,
                }, 409
            job_state._telegram_proxy_refresh_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': None,
            })

        def _run():
            try:
                with app.app_context():
                    result = refresh_telegram_proxy_service()
                with job_state._telegram_proxy_refresh_lock:
                    job_state._telegram_proxy_refresh_status.update({
                        'status': 'done',
                        'result': result,
                        'error': None,
                        'progress': None,
                    })
            except Exception as e:
                with job_state._telegram_proxy_refresh_lock:
                    job_state._telegram_proxy_refresh_status.update({
                        'status': 'error',
                        'result': None,
                        'error': str(e),
                        'progress': None,
                    })

        threading.Thread(target=_run, daemon=True).start()
        return {'message': 'Telegram proxy refresh started', 'status': job_state._telegram_proxy_refresh_status}, 202

    @app.route('/api/ui/system/telegram-proxy/refresh/status', methods=['GET'])
    def refresh_telegram_proxy_status():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with job_state._telegram_proxy_refresh_lock:
            return dict(job_state._telegram_proxy_refresh_status), 200

