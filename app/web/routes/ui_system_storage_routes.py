"""Хранилище записей: stats, nearest day, purge (#265)."""

from __future__ import annotations

import os

from flask import request

from routes.http_guards import require_ui_settings_password
from services.cache import cache_get, cache_set
from services.api_json_validation import parse_request_json_dict
from services.system_metrics_constants import _CACHE_STORAGE_STATS_SEC
from services.system_storage_service import (
    build_storage_stats_list,
    nearest_recording_day_response,
    purge_storage_from_body,
)
from services.recordings_mirror_test_service import (
    test_recordings_mirror_connection,
)
from util import recordings_dir


def register_ui_system_storage_routes(app):
    """Маршруты ``/api/ui/storage/*``."""

    @app.route('/api/ui/storage/stats', methods=['GET'])
    def get_storage_stats():
        sck = 'storage_stats:v1'
        hit, sc = cache_get(sck)
        if hit:
            return sc, 200
        if not os.path.exists(recordings_dir()):
            cache_set(sck, [], 30)
            return [], 200

        stats = build_storage_stats_list()
        cache_set(sck, stats, _CACHE_STORAGE_STATS_SEC)
        return stats, 200

    @app.route('/api/ui/storage/nearest-recording-day', methods=['GET'])
    def get_nearest_recording_day():
        raw_date = (request.args.get('date') or '').strip()
        direction = (request.args.get('direction') or 'next').strip().lower()
        body, code = nearest_recording_day_response(raw_date, direction)
        return body, code

    @app.route('/api/ui/storage/purge', methods=['POST'])
    @require_ui_settings_password
    def purge_storage():
        data, err = parse_request_json_dict(request)
        if err is not None:
            return err, 400
        body, code = purge_storage_from_body(data)
        return body, code

    @app.route('/api/ui/storage/recordings-mirror/test', methods=['POST'])
    @require_ui_settings_password
    def test_recordings_mirror():
        """Admin: test configured SFTP mirror target from current settings."""
        return test_recordings_mirror_connection()
