import os
import csv
import io
from urllib.parse import quote
from flask import request, session, Response
import json as json_module
from sqlalchemy import func, case, distinct, or_
from datetime import datetime, timezone, timedelta
from models import db, BirdFood, Video, Species, VideoSpecies, SpeciesVisit, PushSubscription, video_bird_food_association
from util import (
    fetch_weather,
    update_species_info_from_wiki,
    ensure_utc,
    parse_utc_timestamp,
    get_primary_video_for_visit,
    format_visit_for_timeline,
    settings_check_access,
    contributor_or_admin_access,
    GENERIC_BIRD_SPECIES,
)
from app_config.app_config import app_config
from app_config.cameras import get_valid_cameras, cameras_for_api
from services.feed_service import dispense_feed, check_mqtt_connected, check_esphome_reachable
from services.visit_processor import VisitProcessor
from services.report_service import get_monthly_report_data, build_monthly_report
from services.xeno_canto_service import fetch_recordings, _search_term_from_species_name
from services.ebird_export_service import build_ebird_csv
from services.detection_crop_service import extract_detection_frame, crop_filename
from services.web_push_service import get_vapid_public_key
from services.dataset_export_service import build_dataset_zip, move_crop_on_species_correction
from services.overview_service import get_overview_data
from services.species_summary_service import build_species_summary

UNKNOWNS_LIMIT_MAX = 500


def register_routes(app):
    @app.route('/metrics', methods=['GET'])
    def prometheus_metrics():
        """Prometheus exposition format for Grafana/dashboards."""
        detections = db.session.query(func.count(VideoSpecies.id)).scalar() or 0
        species_count = db.session.query(VideoSpecies.species_id).distinct().count()
        videos_count = db.session.query(func.count(Video.id)).scalar() or 0
        lines = [
            '# HELP birdlense_detections_total Total number of bird detections',
            '# TYPE birdlense_detections_total counter',
            f'birdlense_detections_total {detections}',
            '# HELP birdlense_species_count Number of unique species detected',
            '# TYPE birdlense_species_count gauge',
            f'birdlense_species_count {species_count}',
            '# HELP birdlense_videos_total Total number of recorded videos',
            '# TYPE birdlense_videos_total counter',
            f'birdlense_videos_total {videos_count}',
        ]
        body = '\n'.join(lines) + '\n'
        return Response(body, mimetype='text/plain; charset=utf-8')

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
        if not app_config.get('general.enable_notifications'):
            return {'error': 'Notifications disabled'}, 400
        data = request.json or {}
        sub = data.get('subscription')
        if not sub or not isinstance(sub, dict):
            return {'error': 'subscription required'}, 400
        endpoint = (sub.get('endpoint') or '').strip()
        keys = sub.get('keys') or {}
        p256dh = (keys.get('p256dh') or keys.get('p256dh') or '').strip()
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
        mqtt_status = check_mqtt_connected()
        esphome_status = check_esphome_reachable()
        feed_source = app_config.get('feed.source', 'mqtt')
        motion_source = app_config.get('motion.source', 'opencv')
        # MQTT: feed uses check_mqtt_connected; motion (Frigate) uses aggregator in processor
        if feed_source == 'mqtt':
            mqtt_display = mqtt_status
        elif motion_source in ('frigate', 'mqtt'):
            mqtt_display = 'ok' if processor_ok else 'unknown'
        else:
            mqtt_display = 'not_used'
        # ESPHome: show real status if feed source is esphome
        esphome_display = esphome_status if feed_source == 'esphome' else 'not_used'
        birdnet_url = (app_config.get('general.birdnet_url') or '').strip()
        return {
            'web': 'ok',
            'processor': 'ok' if processor_ok else 'offline',
            'video': 'ok' if processor_ok else 'unknown',
            'mqtt': mqtt_display,
            'esphome': esphome_display,
            'yolo': 'ok' if processor_ok else 'unknown',
            'motion_source': motion_source,
            'birdnet_url': birdnet_url or None,
        }

    @app.route('/api/ui/status/debug', methods=['GET'])
    def status_debug():
        """Диагностика: почему статус серый. Проверить после деплоя."""
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
        weather = fetch_weather()
        return {
            'main': weather.get('weather_main'),
            'description': weather.get('weather_description'),
            'temp': weather.get('weather_temp'),
            'humidity': weather.get('weather_humidity'),
            'pressure': weather.get('weather_pressure'),
            'clouds': weather.get('weather_clouds'),
            'wind_speed': weather.get('weather_wind_speed'),
        } if weather else {}

    @app.route('/api/ui/videos/<int:video_id>', methods=['GET'])
    def get_video_details(video_id):
        # Fetch the video from the database
        video = Video.query.get(video_id)

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
            # Always include frames if available
            if vs.frames:
                data['frames'] = json_module.loads(vs.frames)
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

    @app.route('/api/ui/birdfood', methods=['POST'])
    def add_birdfood():
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
        bird_food = BirdFood.query.get(birdfood_id)
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
        start_time_param = request.args.get('start_time', None)
        end_time_param = request.args.get('end_time', None)
        try:
            if start_time_param and end_time_param:
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

    @app.route('/api/ui/timeline', methods=['GET'])
    def get_video_species():
        # Parse query parameters
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')

        # Validate query parameters
        if not start_time or not end_time:
            return {'error': 'Both start_time and end_time are required'}, 400

        try:
            start_time = parse_utc_timestamp(start_time)
            end_time = parse_utc_timestamp(end_time)
        except ValueError:
            return {'error': 'Invalid datetime format'}, 400

        if end_time - start_time > timedelta(days=1):
            return {'error': 'The interval between start_time and end_time must not exceed 1 day'}, 400

        # Query SpeciesVisit records within the interval
        visits = (
            db.session.query(SpeciesVisit)
            .join(Species)
            .join(VideoSpecies)
            .join(Video)
            .filter(
                # Use overlap logic
                SpeciesVisit.end_time >= start_time,
                SpeciesVisit.start_time <= end_time
            )
            .order_by(SpeciesVisit.start_time.desc())
            .all()
        )

        response = [format_visit_for_timeline(visit) for visit in visits]
        return response

    @app.route('/api/ui/timeline/export', methods=['GET'])
    def export_timeline():
        """Export timeline data as CSV or JSON. Same params as /api/ui/timeline."""
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        fmt = request.args.get('format', 'json').lower()

        if not start_time or not end_time:
            return {'error': 'Both start_time and end_time are required'}, 400
        if fmt not in ('csv', 'json', 'ebird'):
            return {'error': 'format must be csv, json, or ebird'}, 400

        try:
            start_dt = parse_utc_timestamp(start_time)
            end_dt = parse_utc_timestamp(end_time)
        except ValueError:
            return {'error': 'Invalid datetime format'}, 400

        if end_dt - start_dt > timedelta(days=1):
            return {'error': 'Interval must not exceed 1 day'}, 400

        visits = (
            db.session.query(SpeciesVisit)
            .join(Species)
            .join(VideoSpecies)
            .join(Video)
            .filter(
                SpeciesVisit.end_time >= start_dt,
                SpeciesVisit.start_time <= end_dt
            )
            .order_by(SpeciesVisit.start_time.desc())
            .all()
        )

        rows = []
        for visit in visits:
            video = get_primary_video_for_visit(visit)
            duration = (visit.end_time - visit.start_time).total_seconds() if visit.end_time and visit.start_time else 0
            rows.append({
                'id': visit.id,
                'species_name': visit.species.name,
                'start_time': visit.start_time.astimezone(timezone.utc).isoformat(),
                'end_time': visit.end_time.astimezone(timezone.utc).isoformat(),
                'duration_sec': round(duration),
                'max_simultaneous': visit.max_simultaneous,
                'detection_count': len(visit.video_species),
                'temp': video.weather_temp if video else None,
                'clouds': video.weather_clouds if video else None,
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
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        limit = request.args.get('limit', 100, type=int)
        limit = min(max(limit, 1), UNKNOWNS_LIMIT_MAX)

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

        # Bird без вида — всегда неопределённый объект, показываем в Unknowns
        rows = (
            db.session.query(VideoSpecies)
            .join(Video)
            .join(Species)
            .filter(
                Video.start_time >= start_dt,
                Video.start_time <= end_dt,
                or_(
                    VideoSpecies.confidence < threshold,
                    Species.name == GENERIC_BIRD_SPECIES,
                ),
            )
            .order_by(VideoSpecies.created_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for vs in rows:
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

        return result

    @app.route('/api/ui/detections/<int:detection_id>/crop', methods=['GET'])
    def get_detection_crop(detection_id):
        """Extract a frame from video for iNaturalist export. Returns JPEG."""
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        vs = VideoSpecies.query.get(detection_id)
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
        """Export dataset crops as ZIP (train/val + dataset_info.json)."""
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403
        zip_bytes, err = build_dataset_zip()
        if err:
            return {'error': err}, 404
        filename = f'birdlense_dataset_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")}Z.zip'
        return Response(
            zip_bytes,
            mimetype='application/zip',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    @app.route('/api/ui/detections/<int:detection_id>', methods=['PATCH'])
    def update_detection_species(detection_id):
        """Correct species for a low-confidence detection."""
        if not contributor_or_admin_access():
            return {'error': 'Password required'}, 403

        data = request.json or {}
        species_id = data.get('species_id')
        if species_id is None:
            return {'error': 'species_id is required'}, 400
        try:
            species_id = int(species_id)
        except (TypeError, ValueError):
            return {'error': 'species_id must be an integer'}, 400

        vs = VideoSpecies.query.get(detection_id)
        if not vs:
            return {'error': 'Detection not found'}, 404

        species = Species.query.get(species_id)
        if not species:
            return {'error': 'Species not found'}, 404

        old_visit = vs.species_visit
        old_species_id = vs.species_id
        old_species_name = vs.species.name

        if vs.species_id == species_id:
            return {'message': 'Species unchanged'}, 200

        vs.species_id = species_id
        vs.species_visit_id = None

        visit_timeout = int(app_config.get('detection.dedup_window_seconds') or 45)
        vp = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
        video_start = ensure_utc(vs.video.start_time)
        detection_time = video_start + timedelta(seconds=vs.start_time)
        new_visit, _ = vp._get_or_create_visit(species, detection_time)
        new_visit.end_time = max(
            new_visit.end_time,
            video_start + timedelta(seconds=vs.end_time)
        )
        vs.species_visit_id = new_visit.id
        vs.species_visit = new_visit

        db.session.flush()

        if old_visit:
            remaining = [v for v in old_visit.video_species if v.id != detection_id]
            if remaining:
                vp._update_simultaneous_count(old_visit, remaining)
            else:
                db.session.delete(old_visit)

        new_video_detections = [v for v in new_visit.video_species if v.source == 'video']
        if new_video_detections:
            vp._update_simultaneous_count(new_visit, new_video_detections)

        db.session.commit()

        # Move dataset crop to new species dir when user corrects species
        if vs.source == 'video':
            move_crop_on_species_correction(
                video_id=vs.video_id,
                track_id=vs.track_id,
                old_species_name=old_species_name,
                new_species_name=species.name,
            )

        return {'message': 'Species updated', 'species_id': species_id}, 200

    @app.route('/api/ui/species', methods=['GET'])
    def get_all_species():
        # Build base query - get sum of max_simultaneous birds from SpeciesVisit
        query = db.session.query(
            Species,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous),
                          0).label('count')
        ).outerjoin(SpeciesVisit)

        # Group by species and order by name
        species_list = query.group_by(
            Species.id).order_by(Species.name.asc()).all()

        # Construct the response
        return [
            {
                'id': species.Species.id,
                'name': species.Species.name,
                'parent_id': species.Species.parent_id,
                'created_at': species.Species.created_at.isoformat(),
                'image_url': species.Species.image_url,
                'description': species.Species.description,
                'active': species.Species.active,
                'count': species.count
            }
            for species in species_list
        ]

    @app.route('/api/ui/species/observed', methods=['GET'])
    def get_observed_species():
        """Lightweight: only species with count > 0 (for Settings exclude list)."""
        subq = db.session.query(
            SpeciesVisit.species_id,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0).label('count')
        ).group_by(SpeciesVisit.species_id).having(
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0) > 0
        ).subquery()
        rows = db.session.query(Species, subq.c.count).join(
            subq, Species.id == subq.c.species_id
        ).order_by(Species.name.asc()).all()
        return [{'id': s.id, 'name': s.name, 'count': int(cnt)} for s, cnt in rows]

    @app.route('/api/ui/bird_families', methods=['GET'])
    def get_bird_families():
        """Get all bird families (categories one level below 'Birds')"""
        try:
            birds_category = Species.query.filter_by(name="Birds").first()
            if not birds_category:
                return {'error': 'Birds category not found'}, 404

            families = Species.query.filter_by(
                parent_id=birds_category.id).all()
            return [{
                'id': family.id,
                'name': family.name,
            } for family in families]

        except Exception as e:
            app.logger.error(f"Error fetching bird families: {str(e)}")
            return {"error": "Failed to fetch bird families"}, 500

    def _settings_requires_password():
        admin_pw = (app_config.get('general.settings_password') or '').strip()
        contrib_pw = (app_config.get('general.contributor_password') or '').strip()
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
        """Lightweight check: 200 if session unlocked, 403 if password required."""
        if settings_check_access():
            return {'unlocked': True, 'role': 'admin'}, 200
        if contributor_or_admin_access():
            return {'unlocked': True, 'role': 'contributor'}, 200
        return {'error': 'Password required'}, 403

    @app.route('/api/ui/settings/verify-password', methods=['POST'])
    def settings_verify_password():
        data = request.json or {}
        pw = (data.get('password') or '').strip()
        admin_pw = (app_config.get('general.settings_password') or '').strip()
        contrib_pw = (app_config.get('general.contributor_password') or '').strip()
        if not admin_pw and not contrib_pw:
            session['access_role'] = 'admin'
            session['settings_unlocked'] = True
            session.permanent = True
            return {'ok': True, 'role': 'admin'}, 200
        if pw == admin_pw:
            session['access_role'] = 'admin'
            session['settings_unlocked'] = True
            session.permanent = True
            return {'ok': True, 'role': 'admin'}, 200
        if contrib_pw and pw == contrib_pw:
            session['access_role'] = 'contributor'
            session['settings_unlocked'] = False
            session.permanent = True
            return {'ok': True, 'role': 'contributor'}, 200
        return {'ok': False}, 401

    @app.route('/api/ui/settings', methods=['GET'])
    def get_settings():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        return app_config.mask_config_for_api(app_config.config), 200

    @app.route('/api/ui/settings', methods=['PATCH'])
    def update_settings():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            # Parse JSON body from the request
            updates = request.json
            if not updates:
                return {"error": "No data provided for update"}, 400

            # Filter out empty cameras before merge
            if 'video' in updates and 'cameras' in updates['video']:
                cameras = updates['video']['cameras'] or []
                updates['video']['cameras'] = [
                    c for c in cameras
                    if (c.get('stream_name') or '').strip()
                ]

            # Не перезаписывать секреты placeholder'ами (***)
            updates = app_config.filter_sensitive_placeholders(updates)

            # Recursively merge the updates into the current configuration
            app_config.config = app_config.merge_dicts(
                app_config.config, updates)

            # Save the updated configuration back to the user config file
            app_config.save()

            # Return the updated configuration (masked)
            return app_config.mask_config_for_api(app_config.config)

        except Exception as e:
            return {"error": str(e)}, 500

    @app.route('/api/ui/restart-processor', methods=['POST'])
    def restart_processor():
        """Create flag file; processor will exit and docker restarts it."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        import os
        data_dir = os.environ.get('DATA_DIR') or os.path.join(
            os.path.dirname(__file__), '..', '..', 'data')
        flag_path = os.path.join(data_dir, 'restart_processor.flag')
        try:
            os.makedirs(os.path.dirname(flag_path), exist_ok=True)
            with open(flag_path, 'w') as f:
                f.write('1')
            return {"message": "Processor restart requested"}, 200
        except Exception as e:
            return {"error": str(e)}, 500

    @app.route('/api/ui/species/<int:species_id>/xeno-canto', methods=['GET'])
    def get_species_xeno_canto(species_id):
        """Fetch bird song recordings from Xeno-canto for species."""
        species = Species.query.get(species_id)
        if not species:
            return {'error': 'Species not found'}, 404
        recordings = fetch_recordings(species.name, limit=5)
        term = _search_term_from_species_name(species.name) or species.name
        search_url = f"https://xeno-canto.org/explore?query={quote(term)}" if term else None
        return {
            'recordings': recordings,
            'species_name': species.name,
            'xeno_canto_search_url': search_url,
        }, 200

    @app.route('/api/ui/species/<int:species_id>/summary', methods=['GET'])
    def get_species_summary(species_id):
        species = Species.query.get(species_id)
        if not species:
            return {'error': 'Species not found'}, 404

        children = Species.query.filter_by(parent_id=species_id).all()
        all_species_ids = [species.id] + [c.id for c in children]

        if update_species_info_from_wiki(species):
            db.session.add(species)
            db.session.commit()

        return build_species_summary(db.session, species, children, all_species_ids)
