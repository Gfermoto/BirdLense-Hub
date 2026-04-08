"""Admin diagnostics: broken Video rows, purge без species, review-only noise (#265)."""

from __future__ import annotations

import json
import os
import shutil

from flask import request

from auth import admin_track_regen_access
from models import ActivityLog, Species, Video, VideoSpecies, db
from services.broken_videos_inventory_service import (
    broken_video_row_payload,
    broken_video_row_reason,
    scan_broken_videos_inventory,
    video_row_has_no_species,
    videos_with_species_exist_clause,
)
from services.http_response_cache import bust_response_caches, bust_system_response_caches
from services.retention_service import _delete_video_row_cascade
from services.storage_tree_utils import get_tree_storage_info
from services.system_route_payload_parsers import parse_video_ids
import util as util_mod

BROKEN_VIDEOS_DELETE_CONFIRMATION = 'delete_broken_video_rows'
BROKEN_VIDEOS_PURGE_CONFIRMATION = 'purge_all_broken_video_rows'
NO_SPECIES_VIDEOS_PURGE_CONFIRMATION = 'purge_videos_without_species'
REVIEW_ONLY_NOISE_SPECIES = ('Bird', 'Squirrel', 'Rodent')


def register_ui_system_diagnostics_routes(app):
    """Маршруты ``/api/ui/system/diagnostics/*``."""

    @app.route('/api/ui/system/diagnostics/broken-videos', methods=['GET'])
    def list_broken_video_rows():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            limit = int(request.args.get('limit') or 50)
            limit = max(1, min(limit, 200))
            after_id = int(request.args.get('after_id') or 0)
            max_scan = int(request.args.get('max_scan') or 5000)
            max_scan = max(1, min(max_scan, 20000))
        except ValueError:
            return {'error': 'Invalid numeric query parameter'}, 400

        items: list[dict] = []
        scanned = 0
        cursor = after_id
        while len(items) < limit and scanned < max_scan:
            batch = (
                Video.query.filter(Video.id > cursor)
                .order_by(Video.id.asc())
                .limit(200)
                .all()
            )
            if not batch:
                break
            for video in batch:
                scanned += 1
                if scanned > max_scan:
                    break
                row = broken_video_row_payload(video)
                if row:
                    items.append(row)
                if len(items) >= limit:
                    break
            cursor = batch[-1].id

        next_after = None
        if items and len(items) == limit:
            next_after = items[-1]['video_id']
        return {
            'bucket': 'broken_video_row',
            'items': items,
            'scanned': scanned,
            'after_id': after_id,
            'next_after_id': next_after,
            'confirmation_phrase_delete': BROKEN_VIDEOS_DELETE_CONFIRMATION,
            'confirmation_phrase_purge': BROKEN_VIDEOS_PURGE_CONFIRMATION,
        }, 200

    @app.route('/api/ui/system/diagnostics/broken-videos/delete-preview', methods=['POST'])
    def preview_broken_video_rows_delete():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            video_ids = parse_video_ids(payload)
            if not video_ids:
                return {'error': 'video_ids is required'}, 400
            videos = Video.query.filter(Video.id.in_(video_ids)).all()
            by_id = {v.id: v for v in videos}
            missing = [vid for vid in video_ids if vid not in by_id]
            if missing:
                return {'error': 'Some video_ids not found', 'missing_video_ids': missing}, 400
            previews = []
            not_broken = []
            for vid in video_ids:
                v = by_id[vid]
                row = broken_video_row_payload(v)
                if row:
                    previews.append(row)
                else:
                    not_broken.append(vid)
            if not_broken:
                return {
                    'error': 'Some videos are not broken (file exists); refusing preview',
                    'not_broken_video_ids': sorted(not_broken),
                }, 400
            return {
                'confirmation_phrase': BROKEN_VIDEOS_DELETE_CONFIRMATION,
                'video_ids': video_ids,
                'video_count': len(video_ids),
                'videos': previews,
            }, 200
        except ValueError as exc:
            return {'error': str(exc)}, 400
        except Exception as e:
            app.logger.exception('Broken video delete preview failed: %s', e)
            return {'error': 'Failed to build broken video delete preview'}, 500

    @app.route('/api/ui/system/diagnostics/broken-videos/delete', methods=['POST'])
    def delete_broken_video_rows():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            video_ids = parse_video_ids(payload)
            if not video_ids:
                return {'error': 'video_ids is required'}, 400
            confirm_text = str((payload or {}).get('confirm_text') or '').strip()
            if confirm_text != BROKEN_VIDEOS_DELETE_CONFIRMATION:
                return {
                    'error': f'Confirmation text must be "{BROKEN_VIDEOS_DELETE_CONFIRMATION}"',
                }, 400

            videos = Video.query.filter(Video.id.in_(video_ids)).all()
            by_id = {v.id: v for v in videos}
            missing = [vid for vid in video_ids if vid not in by_id]
            if missing:
                return {'error': 'Some video_ids not found', 'missing_video_ids': missing}, 400

            not_broken = []
            for vid in video_ids:
                if broken_video_row_payload(by_id[vid]) is None:
                    not_broken.append(vid)
            if not_broken:
                return {
                    'error': 'Some videos are not broken (file exists); refusing delete',
                    'not_broken_video_ids': sorted(not_broken),
                }, 400

            deleted_video_ids: list[int] = []
            deleted_dirs: set[str] = set()
            deleted_files = 0
            deleted_size = 0
            for vid in video_ids:
                video = by_id[vid]
                full_path = util_mod.full_path_for_video(video.video_path) if video.video_path else None
                if full_path and os.path.isdir(os.path.dirname(full_path)):
                    deleted_dirs.add(os.path.dirname(full_path))
                _delete_video_row_cascade(video)
                deleted_video_ids.append(vid)

            cleanup_log = ActivityLog(
                type='admin_diagnostics_cleanup',
                data=json.dumps({
                    'action': 'broken_video_rows_delete',
                    'bucket': 'broken_video_row',
                    'video_ids': deleted_video_ids,
                }),
            )
            db.session.add(cleanup_log)
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
            return {
                'message': f'Deleted {len(deleted_video_ids)} broken video rows',
                'deletedCount': len(deleted_video_ids),
                'deletedVideoIds': deleted_video_ids,
                'deletedDirs': len(deleted_dirs),
                'deletedFiles': deleted_files,
                'deletedSize': deleted_size,
                'confirmation_phrase': BROKEN_VIDEOS_DELETE_CONFIRMATION,
            }, 200
        except ValueError as exc:
            db.session.rollback()
            return {'error': str(exc)}, 400
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Broken video rows delete failed: %s', e)
            return {'error': 'Failed to delete broken video rows'}, 500

    @app.route('/api/ui/system/diagnostics/broken-videos/purge', methods=['POST'])
    def purge_broken_video_rows():
        """Массовая уборка: строки Video без читаемого файла (в т.ч. 0 байт).

        dry_run (default true): только статистика по первым max_scan строкам Video.
        dry_run false: удалить до limit битых записей за один запрос (повторять до deletedCount=0).
        """
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            max_scan = int(payload.get('max_scan') or 100_000)
            max_scan = max(1000, min(max_scan, 500_000))
            limit = int(payload.get('limit') or 500)
            limit = max(1, min(limit, 5000))

            if dry_run:
                inv = scan_broken_videos_inventory(
                    max_scan=max_scan,
                    collect_ids_limit=None,
                )
                return {
                    'dry_run': True,
                    'scanned': inv['scanned'],
                    'broken_total': inv['broken_total'],
                    'by_reason': inv['by_reason'],
                    'sample_video_ids': inv['sample_video_ids'],
                    'confirmation_phrase': BROKEN_VIDEOS_PURGE_CONFIRMATION,
                    'note': (
                        'Повторяйте POST с dry_run:false и тем же confirm_text, '
                        'пока deletedCount не станет 0.'
                    ),
                }, 200

            confirm_text = str((payload or {}).get('confirm_text') or '').strip()
            if confirm_text != BROKEN_VIDEOS_PURGE_CONFIRMATION:
                return {
                    'error': (
                        f'Confirmation text must be "{BROKEN_VIDEOS_PURGE_CONFIRMATION}"'
                    ),
                }, 400

            inv = scan_broken_videos_inventory(
                max_scan=max_scan,
                collect_ids_limit=limit,
            )
            video_ids = inv['ids_to_delete']
            if not video_ids:
                return {
                    'message': 'No broken video rows found in scan range',
                    'deletedCount': 0,
                    'scanned': inv['scanned'],
                    'more_batches_suggested': False,
                    'confirmation_phrase': BROKEN_VIDEOS_PURGE_CONFIRMATION,
                }, 200

            videos = Video.query.filter(Video.id.in_(video_ids)).all()
            by_id = {v.id: v for v in videos}
            missing = [vid for vid in video_ids if vid not in by_id]
            if missing:
                return {'error': 'Some video_ids not found', 'missing_video_ids': missing}, 400

            not_broken = []
            for vid in video_ids:
                if broken_video_row_payload(by_id[vid]) is None:
                    not_broken.append(vid)
            if not_broken:
                return {
                    'error': 'Race or stale list: some rows are no longer broken',
                    'not_broken_video_ids': sorted(not_broken),
                }, 409

            deleted_video_ids: list[int] = []
            deleted_dirs: set[str] = set()
            deleted_files = 0
            deleted_size = 0
            for vid in video_ids:
                video = by_id[vid]
                full_path = util_mod.full_path_for_video(video.video_path) if video.video_path else None
                if full_path and os.path.isdir(os.path.dirname(full_path)):
                    deleted_dirs.add(os.path.dirname(full_path))
                _delete_video_row_cascade(video)
                deleted_video_ids.append(vid)

            cleanup_log = ActivityLog(
                type='admin_diagnostics_cleanup',
                data=json.dumps({
                    'action': 'broken_video_rows_purge_batch',
                    'bucket': 'broken_video_row',
                    'video_ids': deleted_video_ids,
                    'batch_limit': limit,
                }),
            )
            db.session.add(cleanup_log)
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
            more = len(deleted_video_ids) >= limit
            return {
                'message': f'Deleted {len(deleted_video_ids)} broken video rows (batch)',
                'deletedCount': len(deleted_video_ids),
                'deletedVideoIds': deleted_video_ids,
                'deletedDirs': len(deleted_dirs),
                'deletedFiles': deleted_files,
                'deletedSize': deleted_size,
                'scanned': inv['scanned'],
                'more_batches_suggested': more,
                'confirmation_phrase': BROKEN_VIDEOS_PURGE_CONFIRMATION,
            }, 200
        except ValueError as exc:
            db.session.rollback()
            return {'error': str(exc)}, 400
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Broken video purge failed: %s', e)
            return {'error': 'Failed to purge broken video rows'}, 500

    @app.route('/api/ui/system/diagnostics/no-species-videos/purge', methods=['POST'])
    def purge_no_species_video_rows():
        """Удаление записей Video без строк VideoSpecies (часто после scan import).

        Нормальный приём от процессора всегда создаёт детекции; пустые строки — мусор в ленте.
        dry_run (default true): счётчик и примеры id.
        dry_run false: удалить до limit таких записей за запрос (повторять до deletedCount=0).
        """
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            limit = int(payload.get('limit') or 500)
            limit = max(1, min(limit, 5000))
            sample_limit = int(payload.get('sample_limit') or 40)
            sample_limit = max(1, min(sample_limit, 200))

            has_species = videos_with_species_exist_clause()
            base_q = Video.query.filter(~has_species).order_by(Video.id.asc())

            if dry_run:
                total = base_q.count()
                sample_ids = [v.id for v in base_q.limit(sample_limit).all()]
                return {
                    'dry_run': True,
                    'without_species_total': total,
                    'sample_video_ids': sample_ids,
                    'confirmation_phrase': NO_SPECIES_VIDEOS_PURGE_CONFIRMATION,
                    'note': (
                        'Повторяйте POST с dry_run:false и confirm_text, пока deletedCount не 0. '
                        'Удаляются каталоги записей на диске.'
                    ),
                }, 200

            confirm_text = str((payload or {}).get('confirm_text') or '').strip()
            if confirm_text != NO_SPECIES_VIDEOS_PURGE_CONFIRMATION:
                return {
                    'error': (
                        f'Confirmation text must be "{NO_SPECIES_VIDEOS_PURGE_CONFIRMATION}"'
                    ),
                }, 400

            candidates = base_q.limit(limit).all()
            if not candidates:
                return {
                    'message': 'No videos without species detections',
                    'deletedCount': 0,
                    'more_batches_suggested': False,
                    'confirmation_phrase': NO_SPECIES_VIDEOS_PURGE_CONFIRMATION,
                }, 200

            stale: list[int] = []
            for v in candidates:
                if not video_row_has_no_species(v.id):
                    stale.append(v.id)
            if stale:
                return {
                    'error': 'Race: some videos now have species rows',
                    'stale_video_ids': sorted(stale),
                }, 409

            deleted_video_ids: list[int] = []
            deleted_dirs: set[str] = set()
            deleted_files = 0
            deleted_size = 0
            for video in candidates:
                full_path = util_mod.full_path_for_video(video.video_path) if video.video_path else None
                if full_path and os.path.isdir(os.path.dirname(full_path)):
                    deleted_dirs.add(os.path.dirname(full_path))
                _delete_video_row_cascade(video)
                deleted_video_ids.append(video.id)

            cleanup_log = ActivityLog(
                type='admin_diagnostics_cleanup',
                data=json.dumps({
                    'action': 'no_species_videos_purge_batch',
                    'bucket': 'no_species_video',
                    'video_ids': deleted_video_ids,
                    'batch_limit': limit,
                }),
            )
            db.session.add(cleanup_log)
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
            more = len(deleted_video_ids) >= limit
            return {
                'message': (
                    f'Deleted {len(deleted_video_ids)} videos without species (batch)'
                ),
                'deletedCount': len(deleted_video_ids),
                'deletedVideoIds': deleted_video_ids,
                'deletedDirs': len(deleted_dirs),
                'deletedFiles': deleted_files,
                'deletedSize': deleted_size,
                'more_batches_suggested': more,
                'confirmation_phrase': NO_SPECIES_VIDEOS_PURGE_CONFIRMATION,
            }, 200
        except ValueError as exc:
            db.session.rollback()
            return {'error': str(exc)}, 400
        except Exception as e:
            db.session.rollback()
            app.logger.exception('No-species video purge failed: %s', e)
            return {'error': 'Failed to purge videos without species'}, 500

    @app.route('/api/ui/system/diagnostics/review-only-noise-candidates', methods=['GET'])
    def list_review_only_noise_candidates():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            limit = int(request.args.get('limit') or 100)
            limit = max(1, min(limit, 500))
        except ValueError:
            return {'error': 'Invalid limit'}, 400

        rows = (
            db.session.query(VideoSpecies, Species, Video)
            .join(Species, Species.id == VideoSpecies.species_id)
            .join(Video, Video.id == VideoSpecies.video_id)
            .filter(
                VideoSpecies.source == 'video',
                VideoSpecies.species_visit_id.is_(None),
                Species.name.in_(REVIEW_ONLY_NOISE_SPECIES),
            )
            .order_by(VideoSpecies.id.desc())
            .limit(limit)
            .all()
        )
        items = []
        for vs, sp, v in rows:
            br, _ = broken_video_row_reason(v.video_path)
            vst = vs.created_at
            items.append({
                'detection_id': vs.id,
                'video_id': v.id,
                'species': sp.name,
                'confidence': vs.confidence,
                'detection_provider': vs.detection_provider,
                'created_at': vst.isoformat() if vst else None,
                'video_path': v.video_path,
                'video_file_issue': br,
            })
        return {
            'bucket': 'review_only_noise_candidate',
            'items': items,
            'note': (
                'Автоудаление истории не выполняется. Для массового снятия unknowns используйте '
                'review-queue delete при необходимости.'
            ),
        }, 200
