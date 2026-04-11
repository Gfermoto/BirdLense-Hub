"""Admin diagnostics: broken Video rows, purge без species, review-only noise (#265)."""

from __future__ import annotations

from flask import request

from auth import admin_track_regen_access
from services.system_diagnostics_service import (
    build_birdnet_fifo_snapshot_response,
    build_broken_videos_list_response,
    build_review_only_noise_candidates_response,
    delete_broken_video_rows,
    parse_broken_videos_list_params,
    parse_review_only_noise_limit,
    preview_broken_video_rows_delete,
    purge_broken_video_rows,
    purge_no_species_video_rows,
)
from util import settings_check_access


def register_ui_system_diagnostics_routes(app):
    """Маршруты ``/api/ui/system/diagnostics/*``."""

    @app.route('/api/ui/system/diagnostics/broken-videos', methods=['GET'])
    def list_broken_video_rows():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            limit, after_id, max_scan = parse_broken_videos_list_params(request.args)
        except ValueError:
            return {'error': 'Invalid numeric query parameter'}, 400
        return build_broken_videos_list_response(limit, after_id, max_scan), 200

    @app.route('/api/ui/system/diagnostics/broken-videos/delete-preview', methods=['POST'])
    def preview_broken_video_rows_delete_route():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        payload = request.get_json(silent=True) or {}
        body, code = preview_broken_video_rows_delete(payload)
        return body, code

    @app.route('/api/ui/system/diagnostics/broken-videos/delete', methods=['POST'])
    def delete_broken_video_rows_route():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        payload = request.get_json(silent=True) or {}
        body, code = delete_broken_video_rows(payload)
        return body, code

    @app.route('/api/ui/system/diagnostics/broken-videos/purge', methods=['POST'])
    def purge_broken_video_rows_route():
        """Массовая уборка: строки Video без читаемого файла (в т.ч. 0 байт).

        dry_run (default true): только статистика по первым max_scan строкам Video.
        dry_run false: удалить до limit битых записей за один запрос (повторять до deletedCount=0).
        """
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        payload = request.get_json(silent=True) or {}
        body, code = purge_broken_video_rows(payload)
        return body, code

    @app.route('/api/ui/system/diagnostics/no-species-videos/purge', methods=['POST'])
    def purge_no_species_video_rows_route():
        """Удаление записей Video без строк VideoSpecies (часто после scan import).

        Нормальный приём от процессора всегда создаёт детекции; пустые строки — мусор в ленте.
        dry_run (default true): счётчик и примеры id.
        dry_run false: удалить до limit таких записей за запрос (повторять до deletedCount=0).
        """
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        payload = request.get_json(silent=True) or {}
        body, code = purge_no_species_video_rows(payload)
        return body, code

    @app.route('/api/ui/system/diagnostics/birdnet-fifo', methods=['GET'])
    def diagnostics_birdnet_fifo_snapshot():
        """Снимок FIFO BirdNET с диска (пишет процессор; см. processor.birdnet_fifo_snapshot_*)."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        body, code = build_birdnet_fifo_snapshot_response()
        return body, code

    @app.route('/api/ui/system/diagnostics/review-only-noise-candidates', methods=['GET'])
    def list_review_only_noise_candidates():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            limit = parse_review_only_noise_limit(request.args)
        except ValueError:
            return {'error': 'Invalid limit'}, 400
        return build_review_only_noise_candidates_response(limit), 200
