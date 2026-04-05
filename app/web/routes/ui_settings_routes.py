"""Настройки, verify-password, eBird suggestions, notify/test, restart-processor (#198)."""

import os
import secrets

from flask import request, session

from app_config.app_config import app_config
from auth import (
    _check_verify_password_rate_limit,
    _clear_verify_password_attempts,
    _record_verify_password_failure,
    client_ip_for_rate_limit,
    contributor_or_admin_access,
    settings_check_access,
    verify_password_retry_after_seconds,
)
from services.cache import cache_delete_prefix
from services.http_response_cache import bust_response_caches
from util import data_dir, notify_telegram_test


def _settings_requires_password():
    admin_pw = (app_config.get('general.settings_password') or '').strip()
    contrib_pw = (app_config.get('general.contributor_password') or '').strip()
    if not admin_pw and not contrib_pw:
        return (
            os.environ.get('FLASK_ENV') == 'production'
            or os.environ.get('BIRDLENSE_ENV') == 'production'
        )
    return bool(admin_pw or contrib_pw)


def _has_contributor_tier():
    return bool((app_config.get('general.contributor_password') or '').strip())


def register_ui_settings_routes(app):
    @app.route('/api/ui/settings/requires-password', methods=['GET'])
    def settings_requires_password():
        return {
            'requires': _settings_requires_password(),
            'has_contributor_tier': _has_contributor_tier(),
        }, 200

    @app.route('/api/ui/settings/check-access', methods=['GET'])
    def settings_check_access_route():
        if settings_check_access():
            return {'unlocked': True, 'role': 'admin'}, 200
        if contributor_or_admin_access():
            return {'unlocked': True, 'role': 'contributor'}, 200
        return {'unlocked': False}, 200

    @app.route('/api/ui/settings/verify-password', methods=['POST'])
    def settings_verify_password():
        ip = client_ip_for_rate_limit(request)
        if not _check_verify_password_rate_limit(ip):
            retry = verify_password_retry_after_seconds()
            return (
                {'ok': False, 'error': 'Too many attempts'},
                429,
                {'Retry-After': str(retry)},
            )
        data = request.json or {}
        pw = (data.get('password') or '').strip()
        admin_pw = (app_config.get('general.settings_password') or '').strip()
        contrib_pw = (app_config.get('general.contributor_password') or '').strip()
        if not admin_pw and not contrib_pw:
            if (
                os.environ.get('FLASK_ENV') == 'production'
                or os.environ.get('BIRDLENSE_ENV') == 'production'
            ):
                _record_verify_password_failure(ip)
                return {'ok': False}, 401
            session['access_role'] = 'admin'
            session['settings_unlocked'] = True
            session.permanent = True
            _clear_verify_password_attempts(ip)
            return {'ok': True, 'role': 'admin'}, 200
        if secrets.compare_digest(pw, admin_pw):
            session['access_role'] = 'admin'
            session['settings_unlocked'] = True
            session.permanent = True
            _clear_verify_password_attempts(ip)
            return {'ok': True, 'role': 'admin'}, 200
        if contrib_pw and secrets.compare_digest(pw, contrib_pw):
            session['access_role'] = 'contributor'
            session['settings_unlocked'] = False
            session.permanent = True
            _clear_verify_password_attempts(ip)
            return {'ok': True, 'role': 'contributor'}, 200
        _record_verify_password_failure(ip)
        return {'ok': False}, 401

    @app.route('/api/ui/settings', methods=['GET'])
    def get_settings():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.cache import redis_url_effective_masked_for_api

        cfg = app_config.prepare_settings_for_api(app_config.config)
        perf = cfg.setdefault('performance', {})
        perf['redis_url_effective_masked'] = redis_url_effective_masked_for_api()
        return cfg, 200

    @app.route('/api/ui/settings/ebird-species-mapping-suggestions', methods=['GET'])
    def ebird_species_mapping_suggestions():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.ebird_mapping_suggestions import build_ebird_mapping_suggestions

        return build_ebird_mapping_suggestions(), 200

    @app.route('/api/ui/settings', methods=['PATCH'])
    def update_settings():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            updates = request.json
            if not updates:
                return {"error": "No data provided for update"}, 400

            if isinstance(updates.get('performance'), dict):
                updates['performance'].pop('redis_url_effective_masked', None)

            if 'video' in updates and 'cameras' in updates['video']:
                cameras = updates['video']['cameras'] or []
                updates['video']['cameras'] = [
                    c for c in cameras
                    if (c.get('stream_name') or '').strip()
                ]

            updates = app_config.filter_sensitive_placeholders(updates)

            if isinstance(updates.get('secrets'), dict):
                updates['secrets'].pop('zip', None)
            if isinstance(app_config.config.get('secrets'), dict):
                app_config.config['secrets'].pop('zip', None)

            app_config.config = app_config.merge_dicts(
                app_config.config, updates)

            app_config.save()

            bust_response_caches()
            cache_delete_prefix('ebird_region_comparison:')
            from services.cache import reset_redis_client

            reset_redis_client()

            return app_config.prepare_settings_for_api(app_config.config)

        except Exception:
            app.logger.exception('Update settings failed')
            return {"error": "Failed to save settings"}, 500

    @app.route('/api/ui/notify/test', methods=['POST'])
    def notify_test():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        if not app_config.get('general.enable_notifications'):
            return {'error': 'Notifications disabled'}, 400
        token = (app_config.get('notifications.telegram_bot_token') or '').strip()
        chat_id = (app_config.get('notifications.telegram_chat_id') or '').strip()
        if not token or not chat_id:
            return {'error': 'Telegram bot token or chat_id not configured'}, 400
        success, err = notify_telegram_test()
        if success:
            return {'message': 'Test notification sent'}, 200
        return {'error': err or 'Failed'}, 500

    @app.route('/api/ui/restart-processor', methods=['POST'])
    def restart_processor():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        base = data_dir()
        flag_path = os.path.join(base, 'restart_processor.flag')
        notify_skip_path = os.path.join(base, '.startup_notify_skip')
        try:
            os.makedirs(base, exist_ok=True)
            with open(flag_path, 'w') as f:
                f.write('1')
            with open(notify_skip_path, 'a'):
                os.utime(notify_skip_path, None)
            return {"message": "Processor restart requested"}, 200
        except Exception:
            app.logger.exception('Restart processor failed')
            return {"error": "Failed to restart processor"}, 500
