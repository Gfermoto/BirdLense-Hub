"""HTTP API процессора: приём видео/детекций, вебхуки, защита секретом и SSRF-гварды."""
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
from flask import request
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from models import ActivityLog, db, BirdFood, Video, Species, VideoSpecies, SpeciesVisit
from util import fetch_weather, notify, filter_feeder_species
from services.visit_processor import VisitProcessor
from services.gallery_upload_service import upload_video_detections_to_gallery
from app_config.app_config import app_config
from services.http_response_cache import bust_response_caches
import requests


def _run_gallery_upload_thread(flask_app, video_id: int):
    """Gallery upload runs in a daemon thread — must push Flask app context for DB access."""
    with flask_app.app_context():
        try:
            upload_video_detections_to_gallery(video_id)
        except Exception as e:
            flask_app.logger.warning('Gallery upload thread failed: %s', e)


# Path traversal protection: video_path must match data/recordings/YYYY/MM/DD/timestamp/video.mp4
VIDEO_PATH_RE = re.compile(r'^data/recordings/\d{4}/\d{2}/\d{2}/[\d\-:]+/video\.mp4$')


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not any((
        addr.is_private,
        addr.is_loopback,
        addr.is_link_local,
        addr.is_multicast,
        addr.is_reserved,
        addr.is_unspecified,
    ))


def _is_safe_webhook_url(url: str) -> bool:
    raw = (url or '').strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False
    if parsed.scheme not in ('http', 'https'):
        return False
    host = (parsed.hostname or '').strip()
    if not host:
        return False
    if host.lower() == 'localhost':
        return False
    try:
        infos = socket.getaddrinfo(host, parsed.port or None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        addr = info[4][0]
        if not _is_public_ip(addr):
            return False
    return True


def _fire_webhook(url: str, species_list: list, start_time: datetime, logger):
    """POST each detection to webhook URL. Runs in thread, logs errors."""
    for sp in species_list:
        try:
            species_name = sp.get('species_name') or sp.get('species') or sp.get('name') or 'unknown'
            confidence = float(sp.get('confidence') or 0)
            det_start = float(sp.get('start_time') or 0)
            detection_time = start_time + timedelta(seconds=det_start)
            if detection_time.tzinfo is None:
                detection_time = detection_time.replace(tzinfo=timezone.utc)
            payload = {
                'species': species_name,
                'confidence': round(confidence, 4),
                'time': detection_time.isoformat(),
                'source': sp.get('source', 'video'),
            }
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.warning("Webhook POST failed: %s", e)


def _check_processor_secret():
    """Return True if request is from processor (has valid secret). In production, empty secret blocks access."""
    secret = os.environ.get('PROCESSOR_SECRET', '').strip()
    token = request.headers.get('X-Processor-Token') or ''
    if not secret:
        is_prod = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('BIRDLENSE_ENV') == 'production'
        return not is_prod  # Allow when secret not configured only in dev
    return secrets.compare_digest(token, secret)


def register_routes(app):
    """Зарегистрировать маршруты ``/api/processor/*`` на переданном Flask-приложении."""
    @app.route('/api/processor/videos', methods=['POST'])
    def create_video():
        if not _check_processor_secret():
            return {'error': 'Forbidden'}, 403
        data = request.json
        if not data:
            return {'error': 'JSON body required'}, 400
        try:
            start_time = datetime.fromisoformat(data.get('start_time'))
            end_time = datetime.fromisoformat(data.get('end_time'))
        except (ValueError, TypeError):
            return {'error': 'Invalid datetime format'}, 400

        species_list = data.get('species', []) or []
        if not species_list:
            return {'error': 'Missing species'}, 400
        # Отсечь детекции с низким confidence (4% и т.п.)
        min_conf = float(app_config.get('detection.min_confidence_to_store') or 0.05)
        species_list = [s for s in species_list if float(s.get('confidence') or 0) >= min_conf]
        if not species_list:
            return {'error': 'All species below min_confidence_to_store threshold'}, 400

        video_path = (data.get('video_path') or '').strip()
        if not VIDEO_PATH_RE.match(video_path):
            return {'error': 'Invalid video_path format'}, 400

        try:
            video = Video(
                processor_version=data['processor_version'],
                start_time=start_time,
                end_time=end_time,
                video_path=video_path,
                spectrogram_path=data['spectrogram_path'],
                **fetch_weather()
            )
            db.session.add(video)

            # Add active bird foods
            active_bird_foods = BirdFood.query.filter_by(active=True).all()
            video.food.extend(active_bird_foods)

            visit_timeout = int(app_config.get('detection.dedup_window_seconds') or 60)
            visit_processor = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
            visit_processor.process_detections(video, species_list)

            db.session.commit()
            bust_response_caches()

            # Webhook: fire-and-forget
            webhook_url = (app_config.get('webhook.url') or '').strip()
            if webhook_url and species_list:
                if _is_safe_webhook_url(webhook_url):
                    threading.Thread(
                        target=_fire_webhook,
                        args=(webhook_url, species_list, start_time, app.logger),
                        daemon=True,
                    ).start()
                else:
                    app.logger.warning('Unsafe webhook.url blocked: %s', webhook_url)

            # Публичная галерея: opt-in загрузка кадров (отдельный поток с app context — иначе SQLAlchemy вне контекста)
            if app_config.get('gallery.enabled') and (app_config.get('gallery.upload_url') or '').strip():
                threading.Thread(
                    target=_run_gallery_upload_thread,
                    args=(app, video.id),
                    daemon=True,
                ).start()

            return {'message': 'Video and associated data inserted successfully.', 'video_id': video.id}, 201

        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error processing video: {str(e)}')
            return {'error': 'Failed to process video'}, 500

    @app.route('/api/processor/species/active', methods=['PUT'])
    def set_active_species():
        """Set which species are active (from YOLO regional list or config)."""
        if not _check_processor_secret():
            return {'error': 'Forbidden'}, 403
        active_names = request.json or []
        if not isinstance(active_names, list):
            return {'error': 'active_names must be a list'}, 400
        if len(active_names) > 500:
            return {'error': 'Too many species (max 500)'}, 400
        for name in active_names:
            if not isinstance(name, str) or len(name) > 100:
                return {'error': 'Invalid species name'}, 400
        if not active_names:
            return {"message": "success", "active_feeder_names": []}, 200
        active_feeder_names = filter_feeder_species(active_names)

        db.session.query(Species).update({'active': False})
        for name in active_feeder_names:
            species = db.session.query(Species).filter_by(name=name).first()
            if species:
                species.active = True
            else:
                app.logger.warning(f'Unknown active species "{name}"')

        db.session.commit()
        return {"message": "success", "active_feeder_names": active_feeder_names}, 200

    @app.route('/api/processor/notify/detections', methods=['POST'])
    def notify_detections_route():
        if not _check_processor_secret():
            return {'error': 'Forbidden'}, 403
        data = request.json or {}
        detection = data.get('detection')
        image_path = data.get('image_path')
        image_base64 = data.get('image_base64')
        link = (data.get('link') or 'live')
        preview_source = (data.get('preview_source') or 'unknown')
        image_bytes = None
        image_status = 'missing'
        if image_base64:
            try:
                import base64
                image_bytes = base64.b64decode(image_base64)
            except Exception as e:
                app.logger.warning("Failed to decode image_base64 for notify: %s", e)
                image_status = 'decode_failed'
        if image_base64 and not image_bytes:
            app.logger.warning("notify/detections: image_base64 present but decode produced empty bytes")
            image_status = 'decode_failed'
        elif not image_base64:
            app.logger.info(
                "notify/detections: no image for %s (preview_source=%s)",
                detection,
                preview_source,
            )
            image_status = 'missing'
        else:
            app.logger.info(
                "notify/detections: image present for %s (preview_source=%s, bytes=%s)",
                detection,
                preview_source,
                len(image_bytes or b''),
            )
            image_status = 'present'
        excluded_species = app_config.get(
            'general.notification_excluded_species', [])
        if detection not in excluded_species:
            lower = detection.lower()
            icon = "chipmunk" if any(s in lower for s in (
                "squirrel", "chipmunk", "mouse", "мышь", "белка")) else "bird"
            notify_result = notify(
                f"{detection} Detected",
                tags=icon,
                image_path=image_path,
                image_bytes=image_bytes,
                link=link,
                timestamp=datetime.now(timezone.utc),
                fallback_reason_hint='decode_failed' if image_status == 'decode_failed' else None,
            ) or {}
            fallback_reason = notify_result.get('fallback_reason')
            if image_status == 'decode_failed':
                fallback_reason = 'decode_failed'
            try:
                db.session.add(ActivityLog(
                    type='notify_preview',
                    data=json.dumps({
                        'species': detection,
                        'preview_source': preview_source,
                        'has_image': bool(image_bytes),
                        'image_status': image_status,
                        'telegram_delivery': notify_result.get('telegram_delivery', 'unknown'),
                        'photo_requested': bool(notify_result.get('photo_requested', False)),
                        'photo_available': bool(notify_result.get('photo_available', False)),
                        'photo_sent': bool(notify_result.get('photo_sent', False)),
                        'fallback_reason': fallback_reason,
                    }),
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
        return {'message': f'Successfully received notification of {detection}'}, 200

    @app.route('/api/processor/notify/motion', methods=['POST'])
    def notify_motion_route():
        if not _check_processor_secret():
            return {'error': 'Forbidden'}, 403
        return {'message': f'Successfully received notification of motion'}, 200

    @app.route('/api/processor/activity_log', methods=['POST'])
    def add_or_update_activity_log():
        if not _check_processor_secret():
            app.logger.warning("activity_log: 403 Forbidden (PROCESSOR_SECRET mismatch)")
            return {'error': 'Forbidden'}, 403
        try:
            data = request.json or {}
            activity_type = data.get('type')
            raw_data = data.get('data')
            activity_data = json.dumps(raw_data) if raw_data is not None else '{}'
            if len(activity_data) > 65536:
                return {'error': 'Activity data too large (max 64 KB)'}, 400
            activity_id = data.get('id')
            if activity_id is not None:
                activity_id = int(activity_id)

            if not activity_type:
                return {'error': 'Field "type" is required'}, 400

            if activity_id is None:
                new_log = ActivityLog(type=activity_type, data=activity_data)
                db.session.add(new_log)
                db.session.commit()
                return {'message': 'Activity log created successfully', 'id': new_log.id}, 201
            else:
                log = db.session.get(ActivityLog, activity_id)
                if not log:
                    return {'error': 'Activity log with this ID not found'}, 404
                log.type = activity_type
                log.data = activity_data
                log.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                return {'message': 'Activity log updated successfully', 'id': log.id}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('activity_log failed: %s', e)
            return {'error': 'Internal server error'}, 500
