import os
import shutil
import secrets
import csv
import io
import re
import time
import hashlib
from urllib.parse import quote, urlparse
import requests
from flask import request, session, Response
import json as json_module
from sqlalchemy import func, distinct, or_
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone, timedelta
from models import db, BirdFood, Video, Species, VideoSpecies, SpeciesVisit, PushSubscription
from util import (
    data_dir,
    fetch_weather,
    fetch_sun_times,
    ensure_utc,
    parse_utc_timestamp,
    get_primary_video_for_visit,
    get_primary_video_for_visit_in_window,
    format_visit_for_timeline,
    format_unlinked_video_for_timeline,
    observer_local_day_bounds,
    observer_local_range,
    settings_check_access,
    contributor_or_admin_access,
    GENERIC_BIRD_SPECIES,
    client_ip_for_rate_limit,
    _check_verify_password_rate_limit,
    _clear_verify_password_attempts,
    _record_verify_password_failure,
    verify_password_retry_after_seconds,
    notify_telegram_test,
    _host_is_wikipedia_family,
    _host_is_inaturalist,
    _url_suggests_inaturalist_asset,
)
from app_config.app_config import app_config
from app_config.cameras import get_valid_cameras, cameras_for_api
from services.feed_service import dispense_feed, get_last_dispense, check_mqtt_connected, check_esphome_reachable
from services.status_service import check_video_reachable, parse_yolo_status_from_heartbeat
from services.visit_processor import VisitProcessor
from services.report_service import get_monthly_report_data, build_monthly_report
from services.xeno_canto_service import fetch_recordings, _search_term_from_species_name
from services.ebird_export_service import build_ebird_csv
from services.detection_crop_service import extract_detection_frame, crop_filename
from services.web_push_service import get_vapid_public_key


def _timeline_visits_deduped_ordered(visits_raw):
    """JOIN с VideoSpecies даёт дубликаты SpeciesVisit при нескольких роликах в одном визите."""
    seen = set()
    visits = []
    for v in visits_raw:
        if v.id in seen:
            continue
        seen.add(v.id)
        visits.append(v)
    visits.sort(
        key=lambda x: (ensure_utc(x.start_time), x.id or 0),
        reverse=True,
    )
    return visits


def _timeline_entry_sort_key(item: dict):
    s = item.get('start_time')
    if not isinstance(s, str):
        return datetime.min.replace(tzinfo=timezone.utc)
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(s)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_timeline_iso(s: str) -> datetime:
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def build_merged_timeline_items(session, start_dt, end_dt) -> list:
    """Визиты за интервал + ролики, которые ни в один визит не попали (те же сутки, пересечение по времени)."""
    visits_raw = (
        session.query(SpeciesVisit)
        .join(Species)
        .join(VideoSpecies)
        .join(Video)
        .options(
            joinedload(SpeciesVisit.video_species).joinedload(VideoSpecies.video),
            joinedload(SpeciesVisit.species),
        )
        .filter(
            SpeciesVisit.end_time >= start_dt,
            SpeciesVisit.start_time <= end_dt,
        )
        .order_by(SpeciesVisit.start_time.desc())
        .all()
    )
    visits = _timeline_visits_deduped_ordered(visits_raw)
    visit_payloads = [format_visit_for_timeline(v) for v in visits]
    video_ids_in_visits: set[int] = set()
    for p in visit_payloads:
        for d in p.get('detections') or []:
            vid = d.get('video_id')
            if vid is not None:
                video_ids_in_visits.add(int(vid))
    fallback_species = (
        session.query(Species).filter(Species.name == GENERIC_BIRD_SPECIES).first()
    )
    unlinked_videos = (
        session.query(Video)
        .options(
            joinedload(Video.video_species).joinedload(VideoSpecies.species),
        )
        .filter(
            Video.end_time > start_dt,
            Video.start_time < end_dt,
        )
        .order_by(Video.start_time.desc())
        .all()
    )
    unlinked_payloads = [
        format_unlinked_video_for_timeline(v, fallback_species=fallback_species)
        for v in unlinked_videos
        if v.id not in video_ids_in_visits
    ]
    merged = visit_payloads + unlinked_payloads
    merged.sort(key=_timeline_entry_sort_key, reverse=True)
    return merged
from services.dataset_export_service import (
    build_dataset_zip,
    move_crop_on_species_correction,
    extract_and_save_crop_for_detection,
    clean_dataset,
    _sanitize_dirname,
)
from services.overview_service import get_overview_data
from services.species_summary_service import build_species_summary
from services.species_data_quality_service import species_ids_to_exclude_from_bird_catalog
from services.migration_calendar_service import get_migration_calendar
from services.ebird_region_service import get_region_comparison
from services.species_regional_scope import compute_regional_scope_species_ids
from services.cache import cache_get, cache_set, cache_delete_prefix
from services.http_response_cache import bust_response_caches

UNKNOWNS_LIMIT_MAX = 500

# TTL процессного кэша (секунды); при смене настроек — инвалидация в PATCH /settings
_CACHE_STATUS_SEC = 5
_CACHE_SPECIES_LIST_SEC = 45
_CACHE_SPECIES_OBSERVED_SEC = 45
_CACHE_SPECIES_TRACK_REGEN_SEC = 45
_CACHE_BIRD_FAMILIES_SEC = 300
_CACHE_MIGRATION_SEC = 120
_CACHE_TIMELINE_SEC = 20
_CACHE_UNKNOWNS_SEC = 12
_CACHE_DETECTION_FRAMES_SEC = 45


def register_routes(app):
    def _get_tuning_target_ids() -> list[int]:
        raw = app_config.get('species.tuning_target_species_ids') or []
        out: list[int] = []
        if isinstance(raw, list):
            for x in raw:
                try:
                    v = int(x)
                except (TypeError, ValueError):
                    continue
                if v > 0:
                    out.append(v)
        return sorted(set(out))

    def _save_tuning_target_ids(ids: list[int]) -> None:
        species_cfg = app_config.config.get('species') or {}
        species_cfg['tuning_target_species_ids'] = sorted(set(int(x) for x in ids if int(x) > 0))
        app_config.config['species'] = species_cfg
        app_config.save()

    def _dataset_class_folders() -> set[str]:
        web_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repo_root = os.path.abspath(os.path.join(web_root, '..', '..'))
        candidates = [
            os.path.join(data_dir(), 'dataset'),
            os.path.join(repo_root, 'datasets', 'merged_cls'),
        ]
        out: set[str] = set()
        for base in candidates:
            for split in ('train', 'val'):
                root = os.path.join(base, split)
                if not os.path.isdir(root):
                    continue
                try:
                    for entry in os.listdir(root):
                        if os.path.isdir(os.path.join(root, entry)):
                            out.add(entry)
                except OSError:
                    continue
        return out

    def _normalize_correction_source(value):
        src = (value or '').strip().lower()
        if src in ('unknowns', 'video'):
            return src
        return 'other'

    def _write_correction_activity(action, source, detection_id, from_species_name=None, to_species_name=None, updated_count=None):
        from models import ActivityLog
        payload = {
            'action': action,
            'source': source,
            'detection_id': detection_id,
            'from_species_name': from_species_name,
            'to_species_name': to_species_name,
            'updated_count': updated_count,
        }
        try:
            log = ActivityLog(type='species_correction', data=json_module.dumps(payload, ensure_ascii=False))
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception('Failed to write species_correction activity log')

    @app.route('/api/ui/health', methods=['GET'])
    def health():
        return {'status': 'ok'}

    @app.route('/api/ui/push/vapid-public', methods=['GET'])
    def push_vapid_public():
        """Public VAPID key for Web Push subscription."""
        key = get_vapid_public_key()
        if not key:
            return {'error': 'Web Push not available'}, 503
        return {'vapid_public_key': key}, 200

    @app.route('/api/ui/push/subscribe', methods=['POST'])
    def push_subscribe():
        """Register a Web Push subscription. Requires web_push.enabled and general.enable_notifications."""
        if not settings_check_access():
            return {'error': 'Unauthorized'}, 401
        if not app_config.get('general.enable_notifications'):
            return {'error': 'Notifications disabled'}, 400
        data = request.json or {}
        sub = data.get('subscription')
        if not sub or not isinstance(sub, dict):
            return {'error': 'subscription required'}, 400
        endpoint = (sub.get('endpoint') or '').strip()
        keys = sub.get('keys') or {}
        p256dh = (keys.get('p256dh') or '').strip()
        auth = (keys.get('auth') or '').strip()
        if not endpoint or not p256dh or not auth:
            return {'error': 'subscription.endpoint and subscription.keys (p256dh, auth) required'}, 400
        # Enable web_push when first subscription is added
        app_config.set('web_push.enabled', True)
        app_config.save()
        existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
        if existing:
            existing.p256dh = p256dh
            existing.auth = auth
            existing.user_agent = (request.headers.get('User-Agent') or '')[:512]
            db.session.commit()
            return {'message': 'Subscription updated'}, 200
        ps = PushSubscription(endpoint=endpoint, p256dh=p256dh, auth=auth,
                              user_agent=(request.headers.get('User-Agent') or '')[:512])
        db.session.add(ps)
        db.session.commit()
        return {'message': 'Subscribed'}, 201

    @app.route('/api/ui/cameras', methods=['GET'])
    def list_cameras():
        """List cameras — только из video.cameras, добавлять по одной. Без default."""
        cameras_config = app_config.get('video.cameras') or []
        valid = get_valid_cameras(cameras_config)
        return {'cameras': cameras_for_api(valid)}

    @app.route('/api/ui/status', methods=['GET'])
    def component_status():
        """Component status for UI indicators (Video/MQTT/YOLO)."""
        hit, cached = cache_get('component_status:v1')
        if hit:
            return cached
        from datetime import datetime, timezone, timedelta
        from models import ActivityLog
        # Processor heartbeat: last activity_log of type heartbeat (процессор шлёт каждые 60 сек)
        last_heartbeat = (
            ActivityLog.query.filter_by(type='heartbeat')
            .order_by(ActivityLog.updated_at.desc())
            .first()
        )
        processor_ok = False
        if last_heartbeat and last_heartbeat.updated_at:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
            try:
                updated = ensure_utc(last_heartbeat.updated_at)
                processor_ok = updated >= cutoff
            except (TypeError, ValueError):
                processor_ok = False
        heartbeat_data = None
        if last_heartbeat and last_heartbeat.data:
            try:
                heartbeat_data = json_module.loads(last_heartbeat.data) if isinstance(last_heartbeat.data, str) else last_heartbeat.data
            except (TypeError, ValueError):
                pass
        mqtt_status = check_mqtt_connected()
        esphome_status = check_esphome_reachable()
        feed_source = app_config.get('feed.source', 'mqtt')
        motion_source = app_config.get('motion.source', 'opencv')
        mqtt_broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
        # Источник правды — процессор (Frigate/BirdNET); веб-клиент birdlense_feed часто «error» из-за гонки loop_start.
        if mqtt_broker:
            if processor_ok and isinstance(heartbeat_data, dict) and 'mqtt_connected' in heartbeat_data:
                mqtt_display = 'ok' if heartbeat_data.get('mqtt_connected') else 'error'
            else:
                mqtt_display = mqtt_status
        elif feed_source == 'mqtt':
            mqtt_display = mqtt_status
        else:
            mqtt_display = 'not_used'
        # ESPHome: show real status if feed source is esphome
        esphome_display = esphome_status if feed_source == 'esphome' else 'not_used'
        birdnet_url = (app_config.get('general.birdnet_url') or '').strip()
        heimdall_url = (app_config.get('general.heimdall_url') or '').strip()
        # Триггер для отображения: frigate → mqtt (триггер идёт через MQTT)
        trigger_display = 'mqtt' if motion_source == 'frigate' else motion_source
        # Video: реальная проверка через go2rtc snapshot
        video_display = check_video_reachable()
        # YOLO: из heartbeat процессора (last_yolo_ok_at в пределах 5 мин)
        yolo_display = parse_yolo_status_from_heartbeat(heartbeat_data) if processor_ok else 'unknown'
        payload = {
            'web': 'ok',
            'processor': 'ok' if processor_ok else 'offline',
            'video': video_display,
            'mqtt': mqtt_display,
            'esphome': esphome_display,
            'yolo': yolo_display,
            'motion_source': motion_source,
            'trigger_display': trigger_display,
            'birdnet_url': birdnet_url or None,
            'heimdall_url': heimdall_url or None,
        }
        cache_set('component_status:v1', payload, _CACHE_STATUS_SEC)
        return payload

    @app.route('/api/ui/status/debug', methods=['GET'])
    def status_debug():
        """Диагностика: почему статус серый. Проверить после деплоя."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from datetime import datetime, timezone, timedelta
        from models import ActivityLog
        last = ActivityLog.query.filter_by(type='heartbeat').order_by(ActivityLog.updated_at.desc()).first()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        return {
            'last_heartbeat': {
                'id': last.id if last else None,
                'updated_at': last.updated_at.isoformat() if last and last.updated_at else None,
                'data': last.data if last else None,
            } if last else None,
            'cutoff_utc': cutoff.isoformat(),
            'processor_secret_configured': bool(os.environ.get('PROCESSOR_SECRET', '').strip()),
            'api_url_base_configured': bool(os.environ.get('API_URL_BASE', '').strip()),
        }

    @app.route('/api/ui/feed/info', methods=['GET'])
    def feed_info():
        """Last dispense time, donate URL, feed source, optional scale weight. No auth required."""
        from app_config.app_config import app_config
        from services.feeder_scale import get_feeder_scale_snapshot

        donate_url = (app_config.get('general.donate_url') or '').strip()
        feed_source = app_config.get('feed.source', 'mqtt')
        scale = get_feeder_scale_snapshot()
        return {
            'last_dispense_at': get_last_dispense(),
            'donate_url': donate_url or None,
            'feed_source': feed_source,
            'scale': scale,
        }, 200

    @app.route('/api/ui/feed/dispense', methods=['POST'])
    def feed_dispense():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        success, message = dispense_feed()
        if success:
            return {'message': message}, 200
        return {'error': message}, 500

    @app.route('/api/ui/weather', methods=['GET'])
    def weather():
        from app_config.app_config import app_config
        weather = fetch_weather()
        return {
            'main': weather.get('weather_main'),
            'description': weather.get('weather_description'),
            'temp': weather.get('weather_temp'),
            'humidity': weather.get('weather_humidity'),
            'pressure': weather.get('weather_pressure'),
            'clouds': weather.get('weather_clouds'),
            'wind_speed': weather.get('weather_wind_speed'),
            'source': app_config.get('weather.source', 'openweather'),
            'fetched_at': datetime.now(timezone.utc).isoformat(),
        } if weather else {}

    @app.route('/api/ui/sun-times', methods=['GET'])
    def sun_times():
        """Sunrise, sunset, dawn, dusk for date at configured location. date=YYYY-MM-DD."""
        date_param = request.args.get('date')
        if not date_param:
            return {'error': 'date (YYYY-MM-DD) required'}, 400
        result = fetch_sun_times(date_param)
        return result if result else {}, 200

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
            # Кадры треков (bbox) — отдельно GET .../detection-frames (payload может быть МБ)
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
                'wind_speed': video.weather_wind_speed
            },
            'species': [build_species_data(vs) for vs in video.video_species],
            'food': [
                {
                    'id': bf.id,
                    'name': bf.name,
                    'image_url': bf.image_url,
                } for bf in video.food
            ]
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
            # JS getTimezoneOffset: UTC - local (e.g. UTC+3 => -180)
            # local = utc - offset, then convert local-day bounds back to UTC.
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
            # Пересечение с локальным/UTC-сутками (как в overview): клип, начавшийся до
            # полуночи, но попадающий в день по длительности, должен участвовать в списке.
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
                frames = json_module.loads(vs.frames)
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
        cache_set(ck, body, _CACHE_DETECTION_FRAMES_SEC)
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
            from models import VideoSpecies, SpeciesVisit
            from util import full_path_for_video
            from services.detection_crop_service import VIDEO_PATH_SAFE_RE

            # Путь к папке записи — до удаления объекта video из сессии
            recording_dir = None
            if video.video_path and VIDEO_PATH_SAFE_RE.match(video.video_path):
                d = full_path_for_video(os.path.dirname(video.video_path))
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

            # Файлы — только после успешного коммита БД (иначе при rollback запись пропала с диска)
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
        from flask import send_file
        from services.detection_crop_service import VIDEO_PATH_SAFE_RE
        from util import full_path_for_video
        if not VIDEO_PATH_SAFE_RE.match(video.video_path):
            return {'error': 'Invalid video path'}, 400
        full_path = full_path_for_video(video.video_path)
        if not full_path or not os.path.isfile(full_path):
            return {'error': 'Video file not found'}, 404
        # Имя файла: birdlense_YYYY-MM-DD_HHMMSS.mp4
        from datetime import datetime
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
        from flask import send_file
        from services.detection_crop_service import VIDEO_PATH_SAFE_RE
        from util import full_path_for_video
        if not VIDEO_PATH_SAFE_RE.match(video.video_path):
            return {'error': 'Invalid video path'}, 400
        full_path = full_path_for_video(video.video_path)
        if not full_path or not os.path.isfile(full_path):
            return {'error': 'Video file not found'}, 404
        return send_file(
            full_path,
            mimetype='video/mp4',
            conditional=True,
        )

    @app.route('/api/ui/birdfood', methods=['POST'])
    def add_birdfood():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        data = request.json
        name = data.get('name')
        if not name:
            return {'error': 'Name is required'}, 400

        bird_food = BirdFood.query.filter_by(name=name).first()
        if bird_food:
            return {'error': 'Bird food with this name already exists'}, 400

        bird_food = BirdFood(name=name, active=data.get('active', True))
        db.session.add(bird_food)
        db.session.commit()

        return {'message': 'Bird food added successfully'}, 201

    @app.route('/api/ui/birdfood/<int:birdfood_id>/toggle', methods=['PATCH'])
    def toggle_birdfood(birdfood_id):
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        bird_food = db.session.get(BirdFood, birdfood_id)
        if not bird_food:
            return {'error': 'Bird food not found'}, 404

        bird_food.active = not bird_food.active
        db.session.commit()

        return {'message': 'Bird food active status toggled successfully'}, 200

    @app.route('/api/ui/birdfood', methods=['GET'])
    def get_birdfood():
        bird_food = BirdFood.query.order_by(
            BirdFood.name.asc()).all()
        bird_food_list = [{
            'id': food.id,
            'name': food.name,
            'active': food.active,
            'description': food.description,
            'image_url': food.image_url
        } for food in bird_food]

        return bird_food_list, 200

    @app.route('/api/ui/overview', methods=['GET'])
    def get_overview():
        date_param = request.args.get('date', None)
        start_time_param = request.args.get('start_time', None)
        end_time_param = request.args.get('end_time', None)
        try:
            if date_param:
                start_of_day, end_of_day = observer_local_day_bounds(date_param)
            elif start_time_param and end_time_param:
                start_of_day = parse_utc_timestamp(start_time_param)
                end_of_day = parse_utc_timestamp(end_time_param)
            else:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        except (ValueError, TypeError):
            return {"error": "Invalid timestamp format."}, 400

        data = get_overview_data(db.session, start_of_day, end_of_day)
        return data, 200

    @app.route('/api/ui/region-comparison', methods=['GET'])
    def get_region_comparison_route():
        """Compare user's observed species with eBird region top. Requires secrets.ebird_api_key."""
        observed = (
            db.session.query(Species.name)
            .join(SpeciesVisit, SpeciesVisit.species_id == Species.id)
            .filter(Species.name != GENERIC_BIRD_SPECIES)
            .distinct()
            .all()
        )
        user_names = [r[0] for r in observed]
        result = get_region_comparison(user_names)
        return result if result is not None else {}, 200

    @app.route('/api/ui/migration-calendar', methods=['GET'])
    def get_migration_calendar_route():
        """Species activity by month — historical pattern for migration calendar."""
        start_year = request.args.get('start_year', type=int)
        end_year = request.args.get('end_year', type=int)
        start_date = request.args.get('start_date', type=str)
        end_date = request.args.get('end_date', type=str)
        catalog = (request.args.get('catalog') or 'observed').strip().lower()
        evidence = 'all'
        if catalog not in ('observed', 'dataset', 'full_eu', 'active', 'full'):
            return {'error': 'catalog must be observed, dataset or full_eu'}, 400
        if start_date and not re.match(r'^\d{4}-\d{2}-\d{2}$', start_date):
            return {'error': 'start_date must be YYYY-MM-DD'}, 400
        if end_date and not re.match(r'^\d{4}-\d{2}-\d{2}$', end_date):
            return {'error': 'end_date must be YYYY-MM-DD'}, 400
        if start_date and end_date and start_date > end_date:
            return {'error': 'start_date must be <= end_date'}, 400
        mck = (
            f"migration_cal:v3:{start_year}:{end_year}:{start_date}:{end_date}:"
            f"{catalog}:{evidence}"
        )
        hit, mcached = cache_get(mck)
        if hit:
            return mcached, 200
        data = get_migration_calendar(
            db.session,
            start_year=start_year,
            end_year=end_year,
            start_date=start_date,
            end_date=end_date,
            catalog=catalog,
            evidence=evidence,
            app_config_get=app_config.get,
        )
        cache_set(mck, data, _CACHE_MIGRATION_SEC)
        return data, 200

    @app.route('/api/ui/timeline', methods=['GET'])
    def get_video_species():
        # Parse query parameters
        date_param = request.args.get('date')
        time_of_day = (request.args.get('time_of_day') or 'all').strip().lower()
        hour_param = request.args.get('hour', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')

        # Validate query parameters
        if date_param:
            try:
                start_dt, end_dt = observer_local_range(
                    date_param,
                    time_of_day=time_of_day,
                    hour=hour_param,
                )
            except ValueError:
                return {'error': 'Invalid local date range parameters'}, 400
            tck = f"timeline:local:{date_param}:{time_of_day}:{hour_param}"
        else:
            if not start_time or not end_time:
                return {'error': 'Both start_time and end_time are required'}, 400
            try:
                start_dt = parse_utc_timestamp(start_time)
                end_dt = parse_utc_timestamp(end_time)
            except ValueError:
                return {'error': 'Invalid datetime format'}, 400
            tck = f"timeline:{start_time}:{end_time}"
        hit, tcached = cache_get(tck)
        if hit:
            return tcached

        if end_dt - start_dt > timedelta(days=1):
            return {'error': 'The interval between start_time and end_time must not exceed 1 day'}, 400

        response = build_merged_timeline_items(db.session, start_dt, end_dt)
        cache_set(tck, response, _CACHE_TIMELINE_SEC)
        return response

    @app.route('/api/ui/timeline/export', methods=['GET'])
    def export_timeline():
        """Export timeline data as CSV or JSON. Same params as /api/ui/timeline."""
        date_param = request.args.get('date')
        time_of_day = (request.args.get('time_of_day') or 'all').strip().lower()
        hour_param = request.args.get('hour', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        fmt = request.args.get('format', 'json').lower()

        if fmt not in ('csv', 'json', 'ebird'):
            return {'error': 'format must be csv, json, or ebird'}, 400

        if date_param:
            try:
                start_dt, end_dt = observer_local_range(
                    date_param,
                    time_of_day=time_of_day,
                    hour=hour_param,
                )
            except ValueError:
                return {'error': 'Invalid local date range parameters'}, 400
        else:
            if not start_time or not end_time:
                return {'error': 'Both start_time and end_time are required'}, 400
            try:
                start_dt = parse_utc_timestamp(start_time)
                end_dt = parse_utc_timestamp(end_time)
            except ValueError:
                return {'error': 'Invalid datetime format'}, 400

        if end_dt - start_dt > timedelta(days=1):
            return {'error': 'Interval must not exceed 1 day'}, 400

        merged = build_merged_timeline_items(db.session, start_dt, end_dt)

        rows = []
        for item in merged:
            st_p = _parse_timeline_iso(item['start_time'])
            et_p = _parse_timeline_iso(item['end_time'])
            duration = max(0, round((et_p - st_p).total_seconds()))
            w = item.get('weather') or {}
            rows.append({
                'id': item['id'],
                'species_name': item['species']['name'],
                'start_time': st_p.astimezone(timezone.utc).isoformat(),
                'end_time': et_p.astimezone(timezone.utc).isoformat(),
                'duration_sec': duration,
                'max_simultaneous': item.get('max_simultaneous', 1),
                'detection_count': len(item.get('detections') or []),
                'temp': w.get('temp'),
                'clouds': w.get('clouds'),
            })

        if fmt == 'ebird':
            # Unique species per period (one row per species for eBird checklist)
            seen = set()
            ebird_rows = []
            for r in rows:
                name = r.get('species_name', '')
                if name and name not in seen:
                    seen.add(name)
                    ebird_rows.append(r)
            body = build_ebird_csv(ebird_rows, start_dt, end_dt)
            return Response(
                body,
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=birdlense_ebird.csv'}
            )

        if fmt == 'json':
            body = json_module.dumps(rows, ensure_ascii=False, indent=2)
            return Response(
                body,
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=birdlense_timeline.json'}
            )

        # CSV
        if not rows:
            output = io.StringIO()
            w = csv.writer(output)
            w.writerow(['id', 'species_name', 'start_time', 'end_time', 'duration_sec', 'max_simultaneous', 'detection_count', 'temp', 'clouds'])
        else:
            output = io.StringIO()
            w = csv.writer(output)
            w.writerow(rows[0].keys())
            for r in rows:
                w.writerow(r.values())
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=birdlense_timeline.csv'}
        )

    @app.route('/api/ui/report/pdf', methods=['GET'])
    def report_pdf():
        """Monthly PDF report: N species, top 5, stats, chart."""
        month_param = request.args.get('month')  # YYYY-MM
        start_param = request.args.get('start_time')
        end_param = request.args.get('end_time')

        if month_param:
            try:
                year, month = map(int, month_param.split('-'))
                start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
                if month == 12:
                    end_dt = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
                else:
                    end_dt = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
                month_label = start_dt.strftime('%B %Y')
            except (ValueError, IndexError):
                return {'error': 'Invalid month format. Use YYYY-MM'}, 400
        elif start_param and end_param:
            try:
                start_dt = parse_utc_timestamp(start_param)
                end_dt = parse_utc_timestamp(end_param)
                if end_dt - start_dt > timedelta(days=93):
                    return {'error': 'Interval must not exceed 3 months'}, 400
                month_label = f"{start_dt.strftime('%Y-%m-%d')} — {end_dt.strftime('%Y-%m-%d')}"
            except ValueError:
                return {'error': 'Invalid datetime format'}, 400
        else:
            return {'error': 'Provide month=YYYY-MM or start_time and end_time'}, 400

        top_species, stats = get_monthly_report_data(db.session, start_dt, end_dt)
        pdf_bytes = build_monthly_report(start_dt, end_dt, top_species, stats, month_label)

        filename = f"birdlense_report_{start_dt.strftime('%Y%m')}.pdf"
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    @app.route('/api/ui/unknowns', methods=['GET'])
    def get_unknowns():
        """List of low-confidence detections for manual review."""
        date_param = request.args.get('date')
        time_of_day = (request.args.get('time_of_day') or 'all').strip().lower()
        hour_param = request.args.get('hour', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        limit = request.args.get('limit', 100, type=int)
        limit = min(max(limit, 1), UNKNOWNS_LIMIT_MAX)

        if date_param:
            try:
                start_dt, end_dt = observer_local_range(
                    date_param,
                    time_of_day=time_of_day,
                    hour=hour_param,
                )
            except ValueError:
                return {'error': 'Invalid local date range parameters'}, 400
        else:
            if not start_time or not end_time:
                return {'error': 'Both start_time and end_time are required'}, 400
            try:
                start_dt = parse_utc_timestamp(start_time)
                end_dt = parse_utc_timestamp(end_time)
            except ValueError:
                return {'error': 'Invalid datetime format'}, 400

        if end_dt - start_dt > timedelta(days=1):
            return {'error': 'Interval must not exceed 1 day'}, 400

        threshold = float(app_config.get('ui.unknown_confidence_threshold') or 0.5)
        threshold = max(0.0, min(1.0, threshold))

        uck = (
            f"unknowns:{date_param or start_time}:{time_of_day}:{hour_param}:"
            f"{end_time}:{limit}:{threshold}"
        )
        hit, uc = cache_get(uck)
        if hit:
            return uc

        # Bird без вида или низкий confidence — показываем в Unknowns.
        # Исключаем manually_corrected: пользователь уже проверил/исправил — убираем из списка.
        rows = (
            db.session.query(VideoSpecies)
            .join(Video)
            .join(Species)
            .filter(
                Video.end_time >= start_dt,
                Video.start_time <= end_dt,
                VideoSpecies.manually_corrected == False,
                or_(
                    VideoSpecies.confidence < threshold,
                    Species.name == GENERIC_BIRD_SPECIES,
                ),
            )
            .order_by(VideoSpecies.created_at.desc())
            .limit(limit * 3)
            .all()
        )

        result = []
        for vs in rows:
            frames = (vs.frames or '').strip() if getattr(vs, 'frames', None) else ''
            if (
                vs.detection_provider == 'legacy'
                and vs.species.name == 'Unknown'
                and float(vs.confidence or 0) <= 0
                and vs.source == 'video'
                and not vs.manually_corrected
                and vs.track_id is None
                and not frames
                and float(vs.start_time or 0) == 0
                and float(vs.end_time or 0) == 30
            ):
                continue
            video_start = ensure_utc(vs.video.start_time)
            det_time = video_start + timedelta(seconds=vs.start_time)
            result.append({
                'id': vs.id,
                'video_id': vs.video_id,
                'species_id': vs.species_id,
                'species_name': vs.species.name,
                'confidence': round(vs.confidence, 4),
                'start_time': det_time.astimezone(timezone.utc).isoformat(),
                'end_time': (video_start + timedelta(seconds=vs.end_time)).astimezone(timezone.utc).isoformat(),
                'source': vs.source,
                'detection_provider': vs.detection_provider,
                'image_url': vs.species.image_url,
            })
            if len(result) >= limit:
                break

        cache_set(uck, result, _CACHE_UNKNOWNS_SEC)
        return result

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
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    @app.route('/api/ui/dataset/export', methods=['GET'])
    def export_dataset():
        """Export dataset crops as ZIP (train/val + dataset_info.json).
        Query params:
        - start_date, end_date (YYYY-MM-DD)
        - only_manually_corrected (bool)
        - ready_for_train (bool): auto split from train into train/val/test
        - val_ratio (float), test_ratio (float), split_seed (int), min_images_per_class (int)
        - strict_quality (bool): fail on duplicate tracks, cross-split video leakage, or skipped classes
          (below min_images_per_class when ready_for_train)
        """
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
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    @app.route('/api/ui/dataset/retro-export', methods=['POST'])
    def retro_export_dataset():
        """Ретроэкспорт: извлечь кадры из видео-детекций в датасет.
        rebuild: удалить crops за период и заново извлечь (гарантированно только кропы).
        """
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
        """Очистить датасет: удалить full-frame по эвристике и/или осиротевшие файлы."""
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
        """Подтвердить вид: пометить как проверенный (manually_corrected=True), убрать из Unknowns."""
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        source = _normalize_correction_source((request.json or {}).get('source'))

        vs = db.session.get(VideoSpecies, detection_id)
        if not vs:
            return {'error': 'Detection not found'}, 404

        # Все детекции того же visit — подтверждаем вместе
        to_confirm = list(vs.species_visit.video_species) if vs.species_visit else [vs]
        for v in to_confirm:
            v.manually_corrected = True
        db.session.commit()
        bust_response_caches()
        _write_correction_activity(
            action='confirm_species',
            source=source,
            detection_id=detection_id,
            from_species_name=vs.species.name,
            to_species_name=vs.species.name,
            updated_count=len(to_confirm),
        )

        return {'message': 'Confirmed', 'updated_count': len(to_confirm)}, 200

    @app.route('/api/ui/corrections/recent', methods=['GET'])
    def recent_corrections():
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        from models import ActivityLog
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
                    parsed = json_module.loads(row.data)
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
            })
        return out, 200

    @app.route('/api/ui/detections/<int:detection_id>', methods=['PATCH'])
    def update_detection_species(detection_id):
        """Correct species for a low-confidence detection."""
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403

        data = request.json or {}
        source = _normalize_correction_source(data.get('source'))
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

        # Обновить одним действием:
        # 1) все дубликаты этого вида в ЭТОМ видео (старые записи)
        # 2) все детекции того же visit в других видео
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

        # Удалить старые visits, оставшиеся без детекций
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

        # Move dataset crops to new species dir when user corrects species.
        # If no file to move (processor didn't save), retro-export: extract from video.
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

        updated_count = len(to_update)
        _write_correction_activity(
            action='correct_species',
            source=source,
            detection_id=detection_id,
            from_species_name=old_species_name,
            to_species_name=species.name,
            updated_count=updated_count,
        )
        return {
            'message': 'Species updated' + (f' ({updated_count} videos)' if updated_count > 1 else ''),
            'species_id': species_id,
            'updated_count': updated_count,
        }, 200

    @app.route('/api/ui/videos/<int:video_id>/merge-species', methods=['POST'])
    def merge_video_species(video_id):
        """Объединить все детекции в видео в один вид. Удобно, когда разные нейросети
        или прерывания дали несколько карточек — выбрать правильный вид и применить ко всем."""
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

        # Все уже этого вида — нечего делать
        if all(vs.species_id == species_id for vs in to_update):
            return {'message': 'All detections already this species', 'updated_count': 0}, 200

        old_visits = {vs.species_visit for vs in to_update if vs.species_visit}
        visit_timeout = int(app_config.get('detection.dedup_window_seconds') or 60)
        vp = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
        video_start = ensure_utc(video.start_time)

        # Создать один визит для целевого вида
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

    @app.route('/api/ui/species', methods=['GET'])
    def get_all_species():
        exclude_suspects = request.args.get(
            'exclude_suspects', '').strip().lower() in ('1', 'true', 'yes')
        cache_key = f'species_list:v3:ex{1 if exclude_suspects else 0}'
        hit, scached = cache_get(cache_key)
        if hit:
            return scached
        # Build base query - get sum of max_simultaneous birds from SpeciesVisit
        query = db.session.query(
            Species,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous),
                          0).label('count')
        ).outerjoin(SpeciesVisit)

        # Group by species and order by name
        species_list = query.group_by(
            Species.id).order_by(Species.name.asc()).all()

        if exclude_suspects:
            bad_ids = species_ids_to_exclude_from_bird_catalog(db.session)
            species_list = [s for s in species_list if s.Species.id not in bad_ids]

        regional_scope_ids = compute_regional_scope_species_ids()

        result = [
            {
                'id': species.Species.id,
                'name': species.Species.name,
                'parent_id': species.Species.parent_id,
                'created_at': species.Species.created_at.isoformat(),
                'image_url': species.Species.image_url,
                'description': species.Species.description,
                'metadata_source': species.Species.metadata_source,
                'metadata_source_url': species.Species.metadata_source_url,
                'active': species.Species.active,
                'regional_scope': species.Species.id in regional_scope_ids,
                'count': species.count
            }
            for species in species_list
        ]
        cache_set(cache_key, result, _CACHE_SPECIES_LIST_SEC)
        return result

    @app.route('/api/ui/species/observed', methods=['GET'])
    def get_observed_species():
        """Lightweight: only species with count > 0 (for Settings exclude list)."""
        hit, oc = cache_get('species_observed:v1')
        if hit:
            return oc
        subq = db.session.query(
            SpeciesVisit.species_id,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0).label('count')
        ).group_by(SpeciesVisit.species_id).having(
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0) > 0
        ).subquery()
        rows = db.session.query(Species, subq.c.count).join(
            subq, Species.id == subq.c.species_id
        ).order_by(Species.name.asc()).all()
        out = [{'id': s.id, 'name': s.name, 'count': int(cnt)} for s, cnt in rows]
        cache_set('species_observed:v1', out, _CACHE_SPECIES_OBSERVED_SEC)
        return out

    @app.route('/api/ui/species/track-regen-options', methods=['GET'])
    def get_species_track_regen_options():
        """Species that have VideoSpecies rows (tracks on at least one video).

        Differs from /species/observed (SpeciesVisit): rare or legacy rows can
        exist on videos without visit aggregates, and the regen queue joins VideoSpecies.
        """
        hit, oc = cache_get('species_track_regen:v1')
        if hit:
            return oc
        subq = (
            db.session.query(
                VideoSpecies.species_id,
                func.count(distinct(VideoSpecies.video_id)).label('video_count'),
            )
            .group_by(VideoSpecies.species_id)
            .subquery()
        )
        rows = (
            db.session.query(Species, subq.c.video_count)
            .join(subq, Species.id == subq.c.species_id)
            .order_by(Species.name.asc())
            .all()
        )
        out = [{'id': s.id, 'name': s.name, 'count': int(vc)} for s, vc in rows]
        cache_set('species_track_regen:v1', out, _CACHE_SPECIES_TRACK_REGEN_SEC)
        return out

    @app.route('/api/ui/bird_families', methods=['GET'])
    def get_bird_families():
        """Get all bird families (categories one level below 'Birds')"""
        hit, fc = cache_get('bird_families:v1')
        if hit:
            return fc
        try:
            birds_category = Species.query.filter_by(name="Birds").first()
            if not birds_category:
                return {'error': 'Birds category not found'}, 404

            families = Species.query.filter_by(
                parent_id=birds_category.id).all()
            payload = [{
                'id': family.id,
                'name': family.name,
            } for family in families]
            cache_set('bird_families:v1', payload, _CACHE_BIRD_FAMILIES_SEC)
            return payload

        except Exception as e:
            app.logger.error(f"Error fetching bird families: {str(e)}")
            return {"error": "Failed to fetch bird families"}, 500

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

    @app.route('/api/ui/settings/requires-password', methods=['GET'])
    def settings_requires_password():
        return {
            'requires': _settings_requires_password(),
            'has_contributor_tier': _has_contributor_tier(),
        }, 200

    @app.route('/api/ui/settings/check-access', methods=['GET'])
    def settings_check_access_route():
        """Lightweight check: always 200 JSON (no 403 — avoids browser console noise).

        Mutating endpoints still return 403 when locked.
        """
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

        cfg = app_config.mask_config_for_api(app_config.config)
        perf = cfg.setdefault('performance', {})
        perf['redis_url_effective_masked'] = redis_url_effective_masked_for_api()
        return cfg, 200

    @app.route('/api/ui/settings/ebird-species-mapping-suggestions', methods=['GET'])
    def ebird_species_mapping_suggestions():
        """Regional eBird top vs Species catalog; same access as GET /settings."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.ebird_mapping_suggestions import build_ebird_mapping_suggestions

        return build_ebird_mapping_suggestions(), 200

    @app.route('/api/ui/settings', methods=['PATCH'])
    def update_settings():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            # Parse JSON body from the request
            updates = request.json
            if not updates:
                return {"error": "No data provided for update"}, 400

            if isinstance(updates.get('performance'), dict):
                updates['performance'].pop('redis_url_effective_masked', None)

            # Filter out empty cameras before merge
            if 'video' in updates and 'cameras' in updates['video']:
                cameras = updates['video']['cameras'] or []
                updates['video']['cameras'] = [
                    c for c in cameras
                    if (c.get('stream_name') or '').strip()
                ]

            # Не перезаписывать секреты placeholder'ами (***)
            updates = app_config.filter_sensitive_placeholders(updates)

            # UI helper field for ZIP lookup is transient and must not persist in config.
            if isinstance(updates.get('secrets'), dict):
                updates['secrets'].pop('zip', None)
            if isinstance(app_config.config.get('secrets'), dict):
                app_config.config['secrets'].pop('zip', None)

            # Recursively merge the updates into the current configuration
            app_config.config = app_config.merge_dicts(
                app_config.config, updates)

            # Save the updated configuration back to the user config file
            app_config.save()

            bust_response_caches()
            cache_delete_prefix('ebird_region_comparison:')
            from services.cache import reset_redis_client

            reset_redis_client()

            # Return the updated configuration (masked)
            return app_config.mask_config_for_api(app_config.config)

        except Exception as e:
            app.logger.exception('Update settings failed')
            return {"error": "Failed to save settings"}, 500

    @app.route('/api/ui/notify/test', methods=['POST'])
    def notify_test():
        """Отправить тестовое уведомление в Telegram. Проверка: token, chat_id, enable_notifications."""
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
        """Create flag file; processor will exit and docker restarts it.
        Also touch .startup_notify_skip so notify_app_startup skips TG on next start (no spam)."""
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
        except Exception as e:
            app.logger.exception('Restart processor failed')
            return {"error": "Failed to restart processor"}, 500

    @app.route('/api/ui/species/<int:species_id>/xeno-canto', methods=['GET'])
    def get_species_xeno_canto(species_id):
        """Fetch bird song recordings from Xeno-canto for species."""
        xck = f"xeno_canto:{species_id}"
        hit, xc = cache_get(xck)
        if hit:
            return xc, 200
        species = db.session.get(Species, species_id)
        if not species:
            return {'error': 'Species not found'}, 404
        recordings = fetch_recordings(species.name, limit=5)
        term = _search_term_from_species_name(species.name) or species.name
        search_url = f"https://xeno-canto.org/explore?query={quote(term)}" if term else None
        body = {
            'recordings': recordings,
            'species_name': species.name,
            'xeno_canto_search_url': search_url,
        }
        cache_set(xck, body, 600)
        return body, 200

    @app.route('/api/ui/species/<int:species_id>/summary', methods=['GET'])
    def get_species_summary(species_id):
        sck = f"species_summary:{species_id}"
        hit, sc = cache_get(sck)
        if hit:
            return sc
        species = db.session.get(Species, species_id)
        if not species:
            return {'error': 'Species not found'}, 404

        children = Species.query.filter_by(parent_id=species_id).all()
        all_species_ids = [species.id] + [c.id for c in children]

        # GET не мутирует БД: enrichment через System / отдельные задачи (см. audit containment).
        out = build_species_summary(db.session, species, children, all_species_ids)
        cache_set(sck, out, 30)
        return out

    @app.route('/api/ui/species-image', methods=['GET'])
    def proxy_species_image():
        """Proxy remote species image URLs to avoid third-party hotlink blocks."""
        raw = (request.args.get('url') or '').strip()
        if not raw:
            return {'error': 'url is required'}, 400
        parsed = urlparse(raw)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            return {'error': 'only absolute http/https URLs are allowed'}, 400
        host = (parsed.hostname or '').lower()
        if not (
            _host_is_wikipedia_family(host)
            or _host_is_inaturalist(host)
            or _url_suggests_inaturalist_asset(raw)
        ):
            return {'error': 'host is not allowed for proxy'}, 400

        # Persistent local cache: avoids repeated external hits and shields UI
        # from Wikimedia/iNaturalist throttling on shared server IPs.
        key = hashlib.sha1(raw.encode('utf-8')).hexdigest()
        cache_dir = os.path.join(data_dir(), 'cache', 'species_proxy')
        body_path = os.path.join(cache_dir, f'{key}.bin')
        ctype_path = os.path.join(cache_dir, f'{key}.ctype')
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except OSError:
            pass

        if os.path.isfile(body_path):
            try:
                with open(body_path, 'rb') as fh:
                    body = fh.read()
                ctype = 'image/jpeg'
                if os.path.isfile(ctype_path):
                    with open(ctype_path, 'r', encoding='utf-8') as fh:
                        ctype = (fh.read().strip() or ctype)
                return Response(body, status=200, mimetype=ctype, headers={'Cache-Control': 'public, max-age=86400'})
            except OSError:
                pass

        last_err = None
        for attempt in range(2):
            try:
                upstream = requests.get(
                    raw,
                    timeout=8,
                    headers={
                        'User-Agent': 'BirdLense-Hub/1.0',
                        'Accept': 'image/*,*/*;q=0.8',
                    },
                    allow_redirects=True,
                    stream=True,
                )
                if upstream.status_code >= 400:
                    last_err = f'upstream status={upstream.status_code}'
                    if attempt == 0:
                        time.sleep(0.35)
                        continue
                    break
                ctype = (upstream.headers.get('Content-Type') or '').lower()
                if ctype and not ctype.startswith('image/'):
                    last_err = 'upstream is not image content'
                    break
                body = upstream.content
                try:
                    with open(body_path, 'wb') as fh:
                        fh.write(body)
                    with open(ctype_path, 'w', encoding='utf-8') as fh:
                        fh.write(ctype or 'image/jpeg')
                except OSError:
                    pass
                headers = {'Cache-Control': 'public, max-age=86400'}
                return Response(body, status=200, mimetype=ctype or 'image/jpeg', headers=headers)
            except requests.RequestException as exc:
                last_err = f'image proxy request failed: {exc}'
                if attempt == 0:
                    time.sleep(0.35)
                    continue
                break

        app.logger.warning('Species image proxy failed for %s: %s', raw, last_err)
        return {'error': last_err or 'image proxy failed'}, 502

    @app.route('/api/ui/species/tuning-targets', methods=['GET'])
    def get_tuning_targets():
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        ids = _get_tuning_target_ids()
        if not ids:
            return {'ids': [], 'targets': []}, 200
        species_rows = Species.query.filter(Species.id.in_(ids)).all()
        by_id = {s.id: s for s in species_rows}

        # observed status
        observed_rows = (
            db.session.query(SpeciesVisit.species_id, func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0))
            .filter(SpeciesVisit.species_id.in_(ids))
            .group_by(SpeciesVisit.species_id)
            .all()
        )
        observed = {int(sid): int(cnt or 0) for sid, cnt in observed_rows if sid is not None}

        # dataset status
        dataset_folders = _dataset_class_folders()

        targets = []
        for sid in ids:
            sp = by_id.get(sid)
            if not sp:
                continue
            in_dataset = _sanitize_dirname(sp.name or '') in dataset_folders
            targets.append({
                'id': sid,
                'name': sp.name,
                'observed_count': observed.get(sid, 0),
                'in_dataset': bool(in_dataset),
                'in_full_catalog': True,
            })
        return {'ids': ids, 'targets': targets}, 200

    @app.route('/api/ui/species/<int:species_id>/tuning-target', methods=['POST'])
    def set_species_tuning_target(species_id: int):
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        sp = db.session.get(Species, species_id)
        if not sp:
            return {'error': 'Species not found'}, 404
        payload = request.json or {}
        enabled = bool(payload.get('enabled'))
        ids = _get_tuning_target_ids()
        id_set = set(ids)
        if enabled:
            id_set.add(species_id)
        else:
            id_set.discard(species_id)
        _save_tuning_target_ids(sorted(id_set))
        bust_response_caches()
        return {
            'ok': True,
            'species_id': species_id,
            'enabled': enabled,
            'tuning_target_species_ids': sorted(id_set),
        }, 200
