"""Dataset export/clean, detection crop/confirm/PATCH, corrections log (#198)."""

import json
import threading
from datetime import datetime, timedelta, timezone

from flask import Response, current_app, request

from app_config.app_config import app_config
from auth import contributor_or_admin_access
from models import ActivityLog, Species, VideoSpecies, db
from services.dataset_export_service import (
    build_dataset_zip,
    clean_dataset,
    extract_and_save_crop_for_detection,
    move_crop_on_species_correction,
)
from services.detection_crop_service import crop_filename, extract_detection_frame
from services.http_response_cache import bust_response_caches
from services.visit_processor import VisitProcessor
from util import ensure_utc


def normalize_correction_source(value):
    src = (value or '').strip().lower()
    if src in ('unknowns', 'video'):
        return src
    return 'other'


def normalize_apply_scope(value, *, default='single_track'):
    scope = (value or '').strip().lower()
    if scope in ('single_track', 'whole_visit', 'legacy_fanout'):
        return scope
    return default


def write_correction_activity(
    action,
    source,
    detection_id,
    from_species_name=None,
    to_species_name=None,
    updated_count=None,
    *,
    apply_scope=None,
    reason=None,
    video_id=None,
    track_id=None,
    species_visit_id=None,
    from_species_id=None,
    to_species_id=None,
):
    payload = {
        'action': action,
        'source': source,
        'detection_id': detection_id,
        'from_species_name': from_species_name,
        'to_species_name': to_species_name,
        'updated_count': updated_count,
        'apply_scope': apply_scope,
        'reason': reason,
        'video_id': video_id,
        'track_id': track_id,
        'species_visit_id': species_visit_id,
        'from_species_id': from_species_id,
        'to_species_id': to_species_id,
    }
    try:
        log = ActivityLog(
            type='species_correction',
            data=json.dumps(payload, ensure_ascii=False),
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to write species_correction activity log')


def register_ui_corrections_dataset_routes(app):
    @app.route('/api/ui/detections/<int:detection_id>/crop', methods=['GET'])
    def get_detection_crop(detection_id):
        """Extract a frame from video for iNaturalist export. Returns JPEG."""
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        vs = db.session.get(VideoSpecies, detection_id)
        if not vs:
            return {'error': 'Detection not found'}, 404
        if vs.source != 'video':
            return {'error': 'Crop only for video detections'}, 400
        video = vs.video
        if not video:
            return {'error': 'Video not found'}, 404
        offset = vs.start_time + (vs.end_time - vs.start_time) / 2
        jpeg_bytes = extract_detection_frame(video.video_path, offset)
        if not jpeg_bytes:
            return {'error': 'Failed to extract frame'}, 500
        video_start = ensure_utc(video.start_time)
        det_time = video_start + timedelta(seconds=vs.start_time)
        filename = crop_filename(vs.species.name, det_time.isoformat())
        return Response(
            jpeg_bytes,
            mimetype='image/jpeg',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )

    @app.route('/api/ui/dataset/export', methods=['GET'])
    def export_dataset():
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        only_manually_corrected = request.args.get('only_manually_corrected', '').lower() in ('1', 'true', 'yes')
        ready_for_train = request.args.get('ready_for_train', '').lower() in ('1', 'true', 'yes')
        strict_quality = request.args.get('strict_quality', '').lower() in ('1', 'true', 'yes')
        try:
            val_ratio = float(request.args.get('val_ratio', '0.2'))
        except (TypeError, ValueError):
            val_ratio = 0.2
        try:
            test_ratio = float(request.args.get('test_ratio', '0'))
        except (TypeError, ValueError):
            test_ratio = 0.0
        try:
            split_seed = int(request.args.get('split_seed', '42'))
        except (TypeError, ValueError):
            split_seed = 42
        try:
            min_images_per_class = int(request.args.get('min_images_per_class', '1'))
        except (TypeError, ValueError):
            min_images_per_class = 1
        zip_bytes, err = build_dataset_zip(
            start_date=start_date,
            end_date=end_date,
            only_manually_corrected=only_manually_corrected,
            ready_for_train=ready_for_train,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            split_seed=split_seed,
            min_images_per_class=min_images_per_class,
            strict_quality=strict_quality,
        )
        if err:
            return {'error': err}, 404
        filename = f'birdlense_dataset_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")}Z.zip'
        return Response(
            zip_bytes,
            mimetype='application/zip',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )

    @app.route('/api/ui/dataset/retro-export', methods=['POST'])
    def retro_export_dataset():
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        from services.dataset_export_service import retro_export_all_video_detections

        data = request.json or {}
        min_conf = float(data.get('min_confidence', 0))
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        only_manually_corrected = bool(data.get('only_manually_corrected', False))
        rebuild = bool(data.get('rebuild', False))
        if rebuild and (not start_date or not end_date):
            return {'error': 'rebuild requires start_date and end_date'}, 400
        result = retro_export_all_video_detections(
            min_confidence=min_conf,
            start_date=start_date,
            end_date=end_date,
            only_manually_corrected=only_manually_corrected,
            rebuild=rebuild,
        )
        return result, 200

    @app.route('/api/ui/dataset/clean', methods=['POST'])
    def clean_dataset_route():
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        data = request.json or {}
        dry_run = bool(data.get('dry_run', False))
        remove_fullframe = data.get('remove_fullframe', True)
        remove_orphaned = data.get('remove_orphaned', False)
        result = clean_dataset(
            dry_run=dry_run,
            remove_fullframe=remove_fullframe,
            remove_orphaned=remove_orphaned,
        )
        return result, 200

    @app.route('/api/ui/detections/<int:detection_id>/confirm', methods=['POST'])
    def confirm_detection(detection_id):
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        payload = request.json or {}
        source = normalize_correction_source(payload.get('source'))
        apply_scope = normalize_apply_scope(
            payload.get('apply_scope'),
            default='legacy_fanout',
        )
        reason = (payload.get('reason') or '').strip() or None

        vs = db.session.get(VideoSpecies, detection_id)
        if not vs:
            return {'error': 'Detection not found'}, 404

        if apply_scope == 'single_track':
            to_confirm = [vs]
        else:
            to_confirm = list(vs.species_visit.video_species) if vs.species_visit else [vs]
        for v in to_confirm:
            v.manually_corrected = True
        db.session.commit()
        bust_response_caches()
        write_correction_activity(
            action='confirm_species',
            source=source,
            detection_id=detection_id,
            from_species_name=vs.species.name,
            to_species_name=vs.species.name,
            updated_count=len(to_confirm),
            apply_scope=apply_scope,
            reason=reason,
            video_id=vs.video_id,
            track_id=vs.track_id,
            species_visit_id=vs.species_visit_id,
            from_species_id=vs.species_id,
            to_species_id=vs.species_id,
        )

        return {
            'message': 'Confirmed',
            'updated_count': len(to_confirm),
            'apply_scope': apply_scope,
        }, 200

    @app.route('/api/ui/corrections/recent', methods=['GET'])
    def recent_corrections():
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        limit = request.args.get('limit', 10, type=int)
        limit = min(max(limit, 1), 100)
        rows = (
            ActivityLog.query
            .filter_by(type='species_correction')
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
            .all()
        )
        out = []
        for row in rows:
            parsed = {}
            if row.data:
                try:
                    parsed = json.loads(row.data)
                except (TypeError, ValueError):
                    parsed = {}
            out.append({
                'id': row.id,
                'created_at': ensure_utc(row.created_at).isoformat() if row.created_at else None,
                'action': parsed.get('action') or 'correct_species',
                'source': parsed.get('source') or 'other',
                'detection_id': parsed.get('detection_id'),
                'from_species_name': parsed.get('from_species_name'),
                'to_species_name': parsed.get('to_species_name'),
                'updated_count': parsed.get('updated_count'),
                'apply_scope': parsed.get('apply_scope') or 'legacy_fanout',
                'reason': parsed.get('reason'),
                'video_id': parsed.get('video_id'),
                'track_id': parsed.get('track_id'),
                'species_visit_id': parsed.get('species_visit_id'),
            })
        return out, 200

    @app.route('/api/ui/detections/<int:detection_id>', methods=['PATCH'])
    def update_detection_species(detection_id):
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403

        data = request.json or {}
        source = normalize_correction_source(data.get('source'))
        apply_scope = normalize_apply_scope(data.get('apply_scope'))
        reason = (data.get('reason') or '').strip() or None
        species_id = data.get('species_id')
        if species_id is None:
            return {'error': 'species_id is required'}, 400
        try:
            species_id = int(species_id)
        except (TypeError, ValueError):
            return {'error': 'species_id must be an integer'}, 400

        vs = db.session.get(VideoSpecies, detection_id)
        if not vs:
            return {'error': 'Detection not found'}, 404

        species = db.session.get(Species, species_id)
        if not species:
            return {'error': 'Species not found'}, 404

        old_visit = vs.species_visit
        old_species_id = vs.species_id
        old_species_name = vs.species.name

        if vs.species_id == species_id:
            return {'message': 'Species unchanged'}, 200

        if apply_scope == 'single_track':
            to_update = [vs]
        elif apply_scope == 'whole_visit' and old_visit:
            to_update = list(old_visit.video_species)
        else:
            to_update_set = set()
            for v in vs.video.video_species:
                if v.species_id == old_species_id:
                    to_update_set.add(v)
            if old_visit:
                for v in old_visit.video_species:
                    to_update_set.add(v)
            to_update = list(to_update_set)
        old_visits = {v.species_visit for v in to_update if v.species_visit}

        visit_timeout = int(app_config.get('detection.dedup_window_seconds') or 60)
        vp = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
        video_start = ensure_utc(vs.video.start_time)
        detection_time = video_start + timedelta(seconds=vs.start_time)
        new_visit, _ = vp._get_or_create_visit(species, detection_time)

        for v in to_update:
            v.species_id = species_id
            v.species_visit_id = new_visit.id
            v.species_visit = new_visit
            v.manually_corrected = True
            v_start = ensure_utc(v.video.start_time) + timedelta(seconds=v.start_time)
            v_end = ensure_utc(v.video.start_time) + timedelta(seconds=v.end_time)
            new_visit.end_time = max(new_visit.end_time, v_end)
            new_visit.start_time = min(new_visit.start_time, v_start)

        db.session.flush()

        for ov in old_visits:
            if ov:
                remaining = [x for x in ov.video_species if x not in to_update]
                if not remaining:
                    db.session.delete(ov)

        new_video_detections = [v for v in new_visit.video_species if v.source == 'video']
        if new_video_detections:
            vp._update_simultaneous_count(new_visit, new_video_detections)

        db.session.commit()
        bust_response_caches()

        # Датасет-кропы: FFmpeg на каждой строке — при legacy_fanout десятки вызовов
        # блокируют gunicorn и «вешают» UI. Мало строк — в том же запросе; иначе — фон.
        _INLINE_DATASET_CROP_LIMIT = 5

        def _run_dataset_crop_followup(
            jobs,
            *,
            app_obj,
        ):
            """Повторная загрузка VideoSpecies по id (после commit в другом потоке)."""
            from models import VideoSpecies as VSModel

            with app_obj.app_context():
                for det_id, vid, tid, old_name, new_name in jobs:
                    vrow = db.session.get(VSModel, det_id)
                    if not vrow or vrow.source != 'video':
                        continue
                    moved = move_crop_on_species_correction(
                        video_id=vid,
                        track_id=tid,
                        old_species_name=old_name,
                        new_species_name=new_name,
                    )
                    if not moved:
                        extract_and_save_crop_for_detection(vrow, new_name)

        video_crop_jobs = [
            (v.id, v.video_id, v.track_id, old_species_name, species.name)
            for v in to_update
            if v.source == 'video'
        ]
        if len(video_crop_jobs) <= _INLINE_DATASET_CROP_LIMIT:
            for v in to_update:
                if v.source == 'video':
                    moved = move_crop_on_species_correction(
                        video_id=v.video_id,
                        track_id=v.track_id,
                        old_species_name=old_species_name,
                        new_species_name=species.name,
                    )
                    if not moved:
                        extract_and_save_crop_for_detection(v, species.name)
        elif video_crop_jobs:
            app_obj = current_app._get_current_object()
            threading.Thread(
                target=_run_dataset_crop_followup,
                args=(video_crop_jobs,),
                kwargs={'app_obj': app_obj},
                daemon=True,
            ).start()

        updated_count = len(to_update)
        write_correction_activity(
            action='correct_species',
            source=source,
            detection_id=detection_id,
            from_species_name=old_species_name,
            to_species_name=species.name,
            updated_count=updated_count,
            apply_scope=apply_scope,
            reason=reason,
            video_id=vs.video_id,
            track_id=vs.track_id,
            species_visit_id=vs.species_visit_id,
            from_species_id=old_species_id,
            to_species_id=species.id,
        )
        return {
            'message': 'Species updated' + (f' ({updated_count} videos)' if updated_count > 1 else ''),
            'species_id': species_id,
            'updated_count': updated_count,
            'apply_scope': apply_scope,
        }, 200
