"""Маршруты bulk delete для review queue (#265)."""

from __future__ import annotations

import os
import shutil

from flask import request

from auth import admin_track_regen_access
from models import db
from services.http_response_cache import (
    bust_response_caches,
    bust_system_response_caches,
)
from services.retention_service import _delete_video_row_cascade
from services.review_queue_bulk_plan import resolve_review_queue_bulk_plan
from services.storage_tree_utils import get_tree_storage_info
import util as util_mod


def register_ui_system_review_queue_routes(app):
    """Маршруты ``/api/ui/system/review-queue/*``."""

    @app.route('/api/ui/system/review-queue/delete-preview', methods=['POST'])
    def preview_review_queue_delete():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            plan = resolve_review_queue_bulk_plan(db.session, payload)
            return {
                'confirmation_phrase': plan['confirmation_phrase'],
                'date': plan['date'],
                'time_of_day': plan['time_of_day'],
                'hour': plan['hour'],
                'unknown_count': plan['unknown_count'],
                'video_count': plan['video_count'],
                'unknown_ids': plan['unknown_ids'],
                'video_ids': plan['video_ids'],
                'missing_video_ids': plan['missing_video_ids'],
                'videos': plan['preview_videos'],
            }, 200
        except ValueError as exc:
            return {'error': str(exc)}, 400
        except Exception as e:
            app.logger.exception(
                'Review queue delete preview failed: %s', e,
            )
            return {
                'error': 'Failed to build review queue delete preview',
            }, 500

    @app.route('/api/ui/system/review-queue/delete', methods=['POST'])
    def delete_review_queue_videos():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            plan = resolve_review_queue_bulk_plan(db.session, payload)
            confirm_text = str(
                (payload or {}).get('confirm_text') or '',
            ).strip()
            phrase = plan['confirmation_phrase']
            if confirm_text != phrase:
                return {
                    'error': f'Confirmation text must be "{phrase}"',
                }, 400

            deleted_video_ids = []
            deleted_dirs = set()
            deleted_files = 0
            deleted_size = 0
            for video_id in plan['video_ids']:
                video = plan['videos_by_id'].get(video_id)
                if not video:
                    continue
                vp = video.video_path
                full_path = util_mod.full_path_for_video(vp) if vp else None
                if full_path and os.path.isdir(os.path.dirname(full_path)):
                    deleted_dirs.add(os.path.dirname(full_path))
                _delete_video_row_cascade(video)
                deleted_video_ids.append(video_id)

            db.session.commit()

            for dir_path in sorted(deleted_dirs):
                if not os.path.isdir(dir_path):
                    continue
                count, size = get_tree_storage_info(dir_path)
                deleted_files += count
                deleted_size += size
                shutil.rmtree(dir_path)

            bust_response_caches()
            bust_system_response_caches()
            n = len(deleted_video_ids)
            return {
                'message': f'Deleted {n} review-queue videos',
                'deletedCount': n,
                'deletedVideoIds': deleted_video_ids,
                'deletedDirs': len(deleted_dirs),
                'deletedFiles': deleted_files,
                'deletedSize': deleted_size,
                'confirmation_phrase': phrase,
            }, 200
        except ValueError as exc:
            db.session.rollback()
            return {'error': str(exc)}, 400
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Review queue delete failed: %s', e)
            return {'error': 'Failed to delete review queue videos'}, 500
