"""Маршруты видео: детали, соседи, кадры треков, удаление, скачивание, стрим, merge (#198)."""

import json
import os
import shutil
from datetime import datetime, timedelta, timezone

from flask import request, send_file
from sqlalchemy.orm import joinedload

from app_config.app_config import app_config
from auth import contributor_or_admin_access
from models import Species, SpeciesVisit, Video, VideoSpecies, db
from services.cache import cache_get, cache_set
from services.dataset_export_service import (
    extract_and_save_crop_for_detection,
    move_crop_on_species_correction,
)
from services.detection_crop_service import VIDEO_PATH_SAFE_RE
from services.feeder_scale import video_scales_estimate_payload
from services.http_response_cache import bust_response_caches
from services.visit_processor import VisitProcessor
import util as util_mod
from util import ensure_utc, get_primary_video_for_visit_in_window

from routes.ui_route_constants import CACHE_DETECTION_FRAMES_SEC


def register_ui_video_routes(app):
    @app.route('/api/ui/videos/<int:video_id>', methods=['GET'])
    def get_video_details(video_id):
        video = (
            db.session.query(Video)
            .options(
                joinedload(Video.video_species).joinedload(VideoSpecies.species),
                joinedload(Video.food),
            )
            .filter(Video.id == video_id)
            .first()
        )

        if not video:
            return {'error': 'Video not found'}, 404

        def build_species_data(vs):
            data = {
                'id': vs.id,
                'species_id': vs.species.id,
                'species_name': vs.species.name,
                'start_time': vs.start_time,
                'end_time': vs.end_time,
                'confidence': vs.confidence,
                'source': vs.source,
                'track_id': vs.track_id,
                'image_url': vs.species.image_url,
            }
            if vs.detection_provider:
                data['detection_provider'] = vs.detection_provider
            return data

        video_json = {
            'id': video.id,
            'created_at': video.created_at.astimezone(timezone.utc).isoformat(),
            'processor_version': video.processor_version,
            'start_time': video.start_time.astimezone(timezone.utc).isoformat(),
            'end_time': video.end_time.astimezone(timezone.utc).isoformat(),
            'video_path': video.video_path,
            'spectrogram_path': video.spectrogram_path,
            'favorite': video.favorite,
            'weather': {
                'main': video.weather_main,
                'description': video.weather_description,
                'temp': video.weather_temp,
                'humidity': video.weather_humidity,
                'pressure': video.weather_pressure,
                'clouds': video.weather_clouds,
                'wind_speed': video.weather_wind_speed,
            },
            'species': [build_species_data(vs) for vs in video.video_species],
            'food': [
                {
                    'id': bf.id,
                    'name': bf.name,
                    'image_url': bf.image_url,
                }
                for bf in video.food
            ],
            'scales': video_scales_estimate_payload(video),
        }
        return video_json, 200

    @app.route('/api/ui/videos/<int:video_id>/neighbors', methods=['GET'])
    def get_video_neighbors(video_id):
        """Соседние ролики для страницы видео.

        По умолчанию границы дня считаются в UTC (совместимо с прежним контрактом).
        Опции:
        - day_scope=local: использовать локальный день оператора (tz_offset_minutes)
        - cross_day=true: если в пределах дня соседей нет, вернуть ближайший из соседних суток
        """
        video = db.session.get(Video, video_id)
        if not video:
            return {'error': 'Video not found'}, 404

        scope = (request.args.get('day_scope') or 'utc').strip().lower()
        if scope not in ('utc', 'local'):
            return {'error': 'day_scope must be "utc" or "local"'}, 400
        cross_day = (request.args.get('cross_day') or '').strip().lower() in ('1', 'true', 'yes')
        neighbor_mode = (request.args.get('neighbor_mode') or 'video').strip().lower()
        if neighbor_mode not in ('video', 'visit_primary'):
            return {'error': 'neighbor_mode must be "video" or "visit_primary"'}, 400
        visit_id = request.args.get('visit_id', type=int)
        if neighbor_mode == 'visit_primary' and visit_id is None:
            return {'error': 'visit_id is required when neighbor_mode=visit_primary'}, 400

        try:
            tz_offset_minutes = int(request.args.get('tz_offset_minutes', 0))
        except (TypeError, ValueError):
            return {'error': 'tz_offset_minutes must be an integer'}, 400
        if tz_offset_minutes < -840 or tz_offset_minutes > 840:
            return {'error': 'tz_offset_minutes out of range [-840, 840]'}, 400

        st_utc = ensure_utc(video.start_time).astimezone(timezone.utc).replace(tzinfo=None)
        if scope == 'local':
            local_dt = st_utc - timedelta(minutes=tz_offset_minutes)
            local_day_start = datetime(local_dt.year, local_dt.month, local_dt.day)
            local_day_end = local_day_start + timedelta(days=1)
            day_start = local_day_start + timedelta(minutes=tz_offset_minutes)
            day_end = local_day_end + timedelta(minutes=tz_offset_minutes)
            day_label = local_day_start.date().isoformat()
        else:
            day_start = datetime(st_utc.year, st_utc.month, st_utc.day)
            day_end = day_start + timedelta(days=1)
            day_label = day_start.date().isoformat()

        ids = []
        idx = None
        if neighbor_mode == 'visit_primary' and visit_id:
            visit_rows = (
                db.session.query(SpeciesVisit)
                .options(
                    joinedload(SpeciesVisit.video_species).joinedload(VideoSpecies.video),
                )
                .filter(
                    SpeciesVisit.end_time >= day_start,
                    SpeciesVisit.start_time < day_end,
                )
                .order_by(SpeciesVisit.start_time.asc(), SpeciesVisit.id.asc())
                .all()
            )
            ids = [
                primary.id
                for visit in visit_rows
                for primary in [
                    get_primary_video_for_visit_in_window(visit, day_start, day_end)
                ]
                if primary is not None
            ]
            visit_ids = [
                visit.id
                for visit in visit_rows
                if get_primary_video_for_visit_in_window(visit, day_start, day_end) is not None
            ]
            try:
                idx = visit_ids.index(visit_id)
            except ValueError:
                idx = None
        if idx is None:
            day_rows = (
                Video.query.filter(
                    Video.end_time > day_start,
                    Video.start_time < day_end,
                )
                .order_by(Video.start_time.asc(), Video.id.asc())
                .with_entities(Video.id)
                .all()
            )
            ids = [row[0] for row in day_rows]

        try:
            idx = ids.index(video_id) if idx is None else idx
        except ValueError:
            app.logger.warning(
                'Video %s start_time not in day list (scope=%s day %s–%s); ids=%s',
                video_id,
                scope,
                day_start,
                day_end,
                ids,
            )
            return {
                'day_scope': scope,
                'day_label': day_label,
                'timezone_offset_minutes': tz_offset_minutes if scope == 'local' else 0,
                'cross_day': cross_day,
                'previous_id': None,
                'next_id': None,
                'index': 0,
                'total': len(ids),
            }, 200
        prev_id = ids[idx - 1] if idx > 0 else None
        next_id = ids[idx + 1] if idx + 1 < len(ids) else None

        if cross_day and prev_id is None:
            prev = (
                Video.query.filter(
                    (Video.start_time < video.start_time)
                    | ((Video.start_time == video.start_time) & (Video.id < video.id))
                )
                .order_by(Video.start_time.desc(), Video.id.desc())
                .with_entities(Video.id)
                .first()
            )
            prev_id = prev[0] if prev else None
        if cross_day and next_id is None:
            nxt = (
                Video.query.filter(
                    (Video.start_time > video.start_time)
                    | ((Video.start_time == video.start_time) & (Video.id > video.id))
                )
                .order_by(Video.start_time.asc(), Video.id.asc())
                .with_entities(Video.id)
                .first()
            )
            next_id = nxt[0] if nxt else None

        return {
            'day_scope': scope,
            'day_label': day_label,
            'timezone_offset_minutes': tz_offset_minutes if scope == 'local' else 0,
            'cross_day': cross_day,
            'previous_id': prev_id,
            'next_id': next_id,
            'index': idx,
            'total': len(ids),
        }, 200

    @app.route('/api/ui/videos/<int:video_id>/detection-frames', methods=['GET'])
    def get_video_detection_frames(video_id):
        """Покадровые bbox для оверлея треков. Тяжёлый JSON — не смешиваем с GET /videos/:id."""
        ck = f"detection_frames:{video_id}"
        hit, cached = cache_get(ck)
        if hit:
            return cached, 200
        video = (
            db.session.query(Video)
            .options(joinedload(Video.video_species))
            .filter(Video.id == video_id)
            .first()
        )
        if not video:
            return {'error': 'Video not found'}, 404
        tracks = []
        for vs in video.video_species:
            if not vs.frames:
                continue
            try:
                frames = json.loads(vs.frames)
            except (TypeError, ValueError):
                continue
            tracks.append({
                'id': vs.id,
                'species_id': vs.species_id,
                'start_time': vs.start_time,
                'end_time': vs.end_time,
                'frames': frames,
            })
        body = {'tracks': tracks}
        cache_set(ck, body, CACHE_DETECTION_FRAMES_SEC)
        return body, 200

    @app.route('/api/ui/videos/<int:video_id>', methods=['DELETE'])
    def delete_video(video_id):
        """Удалить запись (видео, файл, связанные данные). Только для админа и помощника."""
        if not contributor_or_admin_access():
            return {'error': 'Access denied'}, 403
        video = db.session.get(Video, video_id)
        if not video:
            return {'error': 'Video not found'}, 404
        try:
            recording_dir = None
            if video.video_path and VIDEO_PATH_SAFE_RE.match(video.video_path):
                d = util_mod.full_path_for_video(os.path.dirname(video.video_path))
                if d and os.path.isdir(d):
                    recording_dir = d

            visit_ids = {vs.species_visit_id for vs in video.video_species if vs.species_visit_id}
            visits_to_delete = []
            for vid in visit_ids:
                other = VideoSpecies.query.filter(
                    VideoSpecies.species_visit_id == vid,
                    VideoSpecies.video_id != video_id,
                ).first()
                if not other:
                    visits_to_delete.append(vid)
            for vs in list(video.video_species):
                db.session.delete(vs)
            for vid in visits_to_delete:
                visit = db.session.get(SpeciesVisit, vid)
                if visit:
                    db.session.delete(visit)

            db.session.delete(video)
            db.session.commit()
            bust_response_caches()

            if recording_dir:
                try:
                    shutil.rmtree(recording_dir)
                    app.logger.info(f"Deleted recording dir: {recording_dir}")
                except OSError as e:
                    app.logger.warning(f"Could not delete dir {recording_dir}: {e}")

            return {'message': 'Video deleted'}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception(f'Delete video {video_id} failed: {e}')
            return {'error': str(e)}, 500

    @app.route('/api/ui/videos/<int:video_id>/download', methods=['GET'])
    def download_video(video_id):
        """Скачать видео. Только для админа и помощника (contributor_or_admin_access)."""
        if not contributor_or_admin_access():
            return {'error': 'Access denied'}, 403
        video = db.session.get(Video, video_id)
        if not video or not video.video_path:
            return {'error': 'Video not found'}, 404
        if not VIDEO_PATH_SAFE_RE.match(video.video_path):
            return {'error': 'Invalid video path'}, 400
        full_path = util_mod.full_path_for_video(video.video_path)
        if not full_path or not os.path.isfile(full_path):
            return {'error': 'Video file not found'}, 404
        ts = video.start_time.strftime('%Y-%m-%d_%H%M%S') if video.start_time else 'video'
        filename = f'birdlense_{ts}.mp4'
        return send_file(
            full_path,
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4',
        )

    @app.route('/api/ui/videos/<int:video_id>/stream', methods=['GET'])
    def stream_video(video_id):
        """Стриминг видео для плеера (Range, video/mp4).

        По умолчанию доступен гостям (Viewer), как GET /videos/:id — см. ACCESS_CONTROL.
        Опционально: general.require_auth_for_video_stream=true — только Contributor/Admin.
        """
        if bool(app_config.get('general.require_auth_for_video_stream')):
            if not contributor_or_admin_access():
                return {'error': 'Password required'}, 403
        video = db.session.get(Video, video_id)
        if not video or not video.video_path:
            return {'error': 'Video not found'}, 404
        if not VIDEO_PATH_SAFE_RE.match(video.video_path):
            return {'error': 'Invalid video path'}, 400
        full_path = util_mod.full_path_for_video(video.video_path)
        if not full_path or not os.path.isfile(full_path):
            return {'error': 'Video file not found'}, 404
        return send_file(
            full_path,
            mimetype='video/mp4',
            conditional=True,
        )

    @app.route('/api/ui/videos/<int:video_id>/merge-species', methods=['POST'])
    def merge_video_species(video_id):
        """Объединить все детекции в видео в один вид."""
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403

        video = db.session.get(Video, video_id)
        if not video:
            return {'error': 'Video not found'}, 404

        data = request.json or {}
        species_id = data.get('species_id')
        if species_id is None:
            return {'error': 'species_id is required'}, 400
        try:
            species_id = int(species_id)
        except (TypeError, ValueError):
            return {'error': 'species_id must be an integer'}, 400

        species = db.session.get(Species, species_id)
        if not species:
            return {'error': 'Species not found'}, 404

        to_update = [vs for vs in video.video_species]
        if not to_update:
            return {'message': 'No detections to merge', 'updated_count': 0}, 200

        if all(vs.species_id == species_id for vs in to_update):
            return {'message': 'All detections already this species', 'updated_count': 0}, 200

        old_visits = {vs.species_visit for vs in to_update if vs.species_visit}
        visit_timeout = int(app_config.get('detection.dedup_window_seconds') or 60)
        vp = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
        video_start = ensure_utc(video.start_time)

        first_start = min(vs.start_time for vs in to_update)
        detection_time = video_start + timedelta(seconds=first_start)
        new_visit, _ = vp._get_or_create_visit(species, detection_time)

        for vs in to_update:
            old_species_name = vs.species.name
            vs.species_id = species_id
            vs.species_visit_id = new_visit.id
            vs.species_visit = new_visit
            vs.manually_corrected = True
            v_start = video_start + timedelta(seconds=vs.start_time)
            v_end = video_start + timedelta(seconds=vs.end_time)
            new_visit.end_time = max(new_visit.end_time, v_end)
            new_visit.start_time = min(new_visit.start_time, v_start)
            if vs.source == 'video':
                moved = move_crop_on_species_correction(
                    video_id=vs.video_id,
                    track_id=vs.track_id,
                    old_species_name=old_species_name,
                    new_species_name=species.name,
                )
                if not moved:
                    extract_and_save_crop_for_detection(vs, species.name)

        db.session.flush()
        for ov in old_visits:
            if ov and ov.id != new_visit.id:
                remaining = [x for x in ov.video_species if x not in to_update]
                if not remaining:
                    db.session.delete(ov)

        new_video_detections = [v for v in new_visit.video_species if v.source == 'video']
        if new_video_detections:
            vp._update_simultaneous_count(new_visit, new_video_detections)

        db.session.commit()
        bust_response_caches()
        updated_count = len(to_update)
        return {
            'message': f'All {updated_count} detections merged to {species.name}',
            'species_id': species_id,
            'updated_count': updated_count,
        }, 200
