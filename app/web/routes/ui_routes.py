import os
import csv
import io
from urllib.parse import quote
from flask import request, session, Response
import json as json_module
from sqlalchemy import func, case, distinct
from datetime import datetime, timezone, timedelta
from models import db, BirdFood, Video, Species, VideoSpecies, SpeciesVisit, video_bird_food_association
from util import fetch_weather, update_species_info_from_wiki, ensure_utc, settings_check_access
from app_config.app_config import app_config
from app_config.cameras import get_valid_cameras, cameras_for_api
from services.feed_service import dispense_feed, check_mqtt_connected, check_esphome_reachable
from services.visit_processor import VisitProcessor
from services.report_service import get_monthly_report_data, build_monthly_report
from services.xeno_canto_service import fetch_recordings, _search_term_from_species_name



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
        # Parse query parameters - accept UTC timestamps directly from frontend
        start_time_param = request.args.get('start_time', None)
        end_time_param = request.args.get('end_time', None)
        
        try:
            if start_time_param and end_time_param:
                # Frontend sends UTC timestamps for the user's local day boundaries
                start_of_day = datetime.fromtimestamp(int(start_time_param), timezone.utc).replace(tzinfo=None)
                end_of_day = datetime.fromtimestamp(int(end_time_param), timezone.utc).replace(tzinfo=None)
            else:
                # Fallback to server's current day (for backwards compatibility)
                now = datetime.now()
                start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        except (ValueError, TypeError):
            return {"error": "Invalid timestamp format."}, 400

        # Top species: все виды с визитами за день (без фильтра active)
        top_species_query = db.session.query(
            Species.id.label('id'),
            Species.name.label('name'),
            *[
                func.sum(
                    case(
                        (func.strftime('%H', SpeciesVisit.start_time) == str(hour).zfill(2),
                         SpeciesVisit.max_simultaneous),
                        else_=0
                    )
                ).label(f'detection_hour_{hour}')
                for hour in range(24)
            ]
        ).join(
            SpeciesVisit, SpeciesVisit.species_id == Species.id
        ).filter(
            SpeciesVisit.start_time >= start_of_day,
            SpeciesVisit.start_time <= end_of_day
        ).group_by(
            Species.id, Species.name
        ).order_by(
            func.sum(SpeciesVisit.max_simultaneous).desc()
        ).limit(10)

        # Query to get the busiest hour
        busiest_hour_query = db.session.query(
            func.strftime('%H', SpeciesVisit.start_time).label('hour'),
            func.sum(SpeciesVisit.max_simultaneous).label('visit_count')
        ).filter(
            SpeciesVisit.start_time >= start_of_day,
            SpeciesVisit.start_time <= end_of_day
        ).group_by(
            'hour'
        ).order_by(
            func.sum(SpeciesVisit.max_simultaneous).desc()
        ).first()

        # Format the top species data
        top_species = []
        for species in top_species_query:
            species_data = {
                'id': species.id,
                'name': species.name,
                'detections': [getattr(species, f'detection_hour_{hour}', 0) or 0 for hour in range(24)]
            }
            top_species.append(species_data)

        # Statistics query — все визиты за день
        stats_query = db.session.query(
            func.count(distinct(SpeciesVisit.species_id)).label('uniqueSpecies'),
            func.sum(SpeciesVisit.max_simultaneous).label('totalDetections'),
            func.sum(
                case(
                    (SpeciesVisit.start_time >= datetime.now() - timedelta(hours=1),
                     SpeciesVisit.max_simultaneous),
                    else_=0
                )
            ).label('lastHourDetections'),
            func.avg(
                func.strftime('%s', SpeciesVisit.end_time) -
                func.strftime('%s', SpeciesVisit.start_time)
            ).label('avgVisitDuration')
        ).filter(
            SpeciesVisit.start_time >= start_of_day,
            SpeciesVisit.start_time <= end_of_day
        ).first()

        # Calculate total detection durations by source
        source_duration_query = db.session.query(
            func.sum(
                case(
                    (VideoSpecies.source == 'video',
                     VideoSpecies.end_time - VideoSpecies.start_time),
                    else_=0
                )
            ).label('video_duration'),
            func.sum(
                case(
                    (VideoSpecies.source == 'audio',
                     VideoSpecies.end_time - VideoSpecies.start_time),
                    else_=0
                )
            ).label('audio_duration')
        ).join(
            SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id
        ).filter(
            SpeciesVisit.start_time >= start_of_day,
            SpeciesVisit.start_time <= end_of_day
        ).first()

        # Detection count by provider (yolo, frigate, birdnet_mqtt)
        provider_query = (
            db.session.query(
                VideoSpecies.detection_provider,
                func.sum(SpeciesVisit.max_simultaneous).label('count')
            )
            .join(
                SpeciesVisit,
                VideoSpecies.species_visit_id == SpeciesVisit.id
            )
            .filter(
                SpeciesVisit.start_time >= start_of_day,
                SpeciesVisit.start_time <= end_of_day
            )
            .group_by(VideoSpecies.detection_provider)
            .all()
        )
        detection_by_provider = {
            (p or 'legacy'): int(c) for p, c in provider_query
        }

        # Format stats data
        stats = {
            'uniqueSpecies': stats_query.uniqueSpecies if stats_query.uniqueSpecies else 0,
            'totalDetections': stats_query.totalDetections if stats_query.totalDetections else 0,
            'lastHourDetections': stats_query.lastHourDetections if stats_query.lastHourDetections else 0,
            'busiestHour': int(busiest_hour_query.hour) if busiest_hour_query else 0,
            'avgVisitDuration': round(stats_query.avgVisitDuration or 0),
            'videoDuration': round(source_duration_query.video_duration or 0),
            'audioDuration': round(source_duration_query.audio_duration or 0),
            'detectionByProvider': detection_by_provider,
        }

        # Query hourly average temperature from videos
        hourly_temp_query = db.session.query(
            func.strftime('%H', Video.start_time).label('hour'),
            func.avg(Video.weather_temp).label('avg_temp')
        ).filter(
            Video.start_time >= start_of_day,
            Video.start_time <= end_of_day,
            Video.weather_temp.isnot(None)
        ).group_by('hour').all()

        # Format hourly temperature as array of 24 values (null for hours with no data)
        hourly_temperature = [None] * 24
        for hour, avg_temp in hourly_temp_query:
            hourly_temperature[int(hour)] = round(avg_temp, 1) if avg_temp else None

        # Last detection of the day (for "Последняя птица" widget)
        last_visit = (
            db.session.query(SpeciesVisit, Species.name)
            .join(Species, SpeciesVisit.species_id == Species.id)
            .filter(
                SpeciesVisit.start_time >= start_of_day,
                SpeciesVisit.start_time <= end_of_day
            )
            .order_by(SpeciesVisit.start_time.desc())
            .first()
        )
        last_detection = None
        if last_visit:
            visit, species_name = last_visit
            last_detection = {
                'species_name': species_name,
                'start_time': visit.start_time.isoformat() if visit.start_time else None,
            }

        return {
            'topSpecies': top_species,
            'stats': stats,
            'hourlyTemperature': hourly_temperature,
            'lastDetection': last_detection,
        }, 200

    @app.route('/api/ui/timeline', methods=['GET'])
    def get_video_species():
        # Parse query parameters
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')

        # Validate query parameters
        if not start_time or not end_time:
            return {'error': 'Both start_time and end_time are required'}, 400

        try:
            # Use UTC but remove timezone info to match naive DB storage
            start_time = datetime.fromtimestamp(int(start_time), timezone.utc).replace(tzinfo=None)
            end_time = datetime.fromtimestamp(int(end_time), timezone.utc).replace(tzinfo=None)
        except ValueError:
            return {'error': 'Invalid datetime format'}, 400

        # Ensure the interval is no more than 1 day
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

        # Construct the response
        response = []
        for visit in visits:
            # Get the first video for weather data (assuming similar conditions during visit)
            video = visit.video_species[0].video if visit.video_species else None

            # Prepare detections for this visit
            detections = []
            sorted_video_species = sorted(
                visit.video_species, key=lambda x: x.created_at, reverse=True)
            for video_species in sorted_video_species:
                video_start_time = video_species.video.start_time
                det = {
                    'video_id': video_species.video_id,
                    'start_time': (video_start_time + timedelta(seconds=video_species.start_time)).astimezone(timezone.utc).isoformat(),
                    'end_time': (video_start_time + timedelta(seconds=video_species.end_time)).astimezone(timezone.utc).isoformat(),
                    'confidence': video_species.confidence,
                    'source': video_species.source
                }
                if video_species.detection_provider:
                    det['detection_provider'] = video_species.detection_provider
                detections.append(det)

            response.append({
                'id': visit.id,
                'start_time': visit.start_time.astimezone(timezone.utc).isoformat(),
                'end_time': visit.end_time.astimezone(timezone.utc).isoformat(),
                'max_simultaneous': visit.max_simultaneous,
                'weather': {
                    'temp': video.weather_temp if video else None,
                    'clouds': video.weather_clouds if video else None,
                } if video else None,
                'species': {
                    'id': visit.species.id,
                    'name': visit.species.name,
                    'image_url': visit.species.image_url,
                    'parent_id': visit.species.parent_id,
                },
                'detections': detections
            })

        return response

    @app.route('/api/ui/timeline/export', methods=['GET'])
    def export_timeline():
        """Export timeline data as CSV or JSON. Same params as /api/ui/timeline."""
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        fmt = request.args.get('format', 'json').lower()

        if not start_time or not end_time:
            return {'error': 'Both start_time and end_time are required'}, 400
        if fmt not in ('csv', 'json'):
            return {'error': 'format must be csv or json'}, 400

        try:
            start_dt = datetime.fromtimestamp(int(start_time), timezone.utc).replace(tzinfo=None)
            end_dt = datetime.fromtimestamp(int(end_time), timezone.utc).replace(tzinfo=None)
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
            video = visit.video_species[0].video if visit.video_species else None
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
                start_dt = datetime.fromtimestamp(int(start_param), timezone.utc).replace(tzinfo=None)
                end_dt = datetime.fromtimestamp(int(end_param), timezone.utc).replace(tzinfo=None)
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
        limit = min(max(limit, 1), 500)

        if not start_time or not end_time:
            return {'error': 'Both start_time and end_time are required'}, 400

        try:
            start_dt = datetime.fromtimestamp(int(start_time), timezone.utc).replace(tzinfo=None)
            end_dt = datetime.fromtimestamp(int(end_time), timezone.utc).replace(tzinfo=None)
        except ValueError:
            return {'error': 'Invalid datetime format'}, 400

        if end_dt - start_dt > timedelta(days=1):
            return {'error': 'Interval must not exceed 1 day'}, 400

        threshold = float(app_config.get('ui.unknown_confidence_threshold') or 0.5)
        threshold = max(0.0, min(1.0, threshold))

        rows = (
            db.session.query(VideoSpecies)
            .join(Video)
            .join(Species)
            .filter(
                Video.start_time >= start_dt,
                Video.start_time <= end_dt,
                VideoSpecies.confidence < threshold,
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

    @app.route('/api/ui/detections/<int:detection_id>', methods=['PATCH'])
    def update_detection_species(detection_id):
        """Correct species for a low-confidence detection."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403

        data = request.json or {}
        species_id = data.get('species_id')
        if species_id is None:
            return {'error': 'species_id is required'}, 400

        vs = VideoSpecies.query.get(detection_id)
        if not vs:
            return {'error': 'Detection not found'}, 404

        species = Species.query.get(species_id)
        if not species:
            return {'error': 'Species not found'}, 404

        old_visit = vs.species_visit
        old_species_id = vs.species_id

        if vs.species_id == species_id:
            return {'message': 'Species unchanged'}, 200

        vs.species_id = species_id
        vs.species_visit_id = None

        vp = VisitProcessor(db, app.logger)
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
        pw = app_config.get('general.settings_password') or ''
        return bool(pw.strip())

    @app.route('/api/ui/settings/requires-password', methods=['GET'])
    def settings_requires_password():
        return {'requires': _settings_requires_password()}, 200

    @app.route('/api/ui/settings/check-access', methods=['GET'])
    def settings_check_access_route():
        """Lightweight check: 200 if session unlocked, 403 if password required."""
        if settings_check_access():
            return {'unlocked': True}, 200
        return {'error': 'Password required'}, 403

    @app.route('/api/ui/settings/verify-password', methods=['POST'])
    def settings_verify_password():
        data = request.json or {}
        pw = (data.get('password') or '').strip()
        expected = (app_config.get('general.settings_password') or '').strip()
        if not expected:
            return {'ok': True}, 200
        if pw == expected:
            session['settings_unlocked'] = True
            session.permanent = True
            return {'ok': True}, 200
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
        # Get the species and its direct children
        species = Species.query.get(species_id)
        if not species:
            return {'error': 'Species not found'}, 404

        children = Species.query.filter_by(parent_id=species_id).all()
        all_species_ids = [species.id] + [child.id for child in children]

        if update_species_info_from_wiki(species):
            db.session.add(species)
            db.session.commit()

        # Calculate date ranges
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(days=1)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        # Function to get visit stats with species breakdown
        def get_visit_stats(since_time):
            return db.session.query(
                SpeciesVisit.species_id,
                func.sum(SpeciesVisit.max_simultaneous).label('count')
            ).filter(
                SpeciesVisit.species_id.in_(all_species_ids),
                SpeciesVisit.start_time >= since_time
            ).group_by(
                SpeciesVisit.species_id
            ).all()

        # Get visit stats with species breakdown
        stats_24h = dict(get_visit_stats(last_24h))
        stats_7d = dict(get_visit_stats(last_7d))
        stats_30d = dict(get_visit_stats(last_30d))

        # Get first and last sighting dates across all species
        sightings = db.session.query(
            func.min(SpeciesVisit.start_time).label('first'),
            func.max(SpeciesVisit.end_time).label('last')
        ).filter(
            SpeciesVisit.species_id.in_(all_species_ids)
        ).first()

        # Get hourly activity pattern with species breakdown
        hourly_activity = db.session.query(
            SpeciesVisit.species_id,
            func.strftime('%H', SpeciesVisit.start_time).label('hour'),
            func.sum(SpeciesVisit.max_simultaneous).label('count')
        ).filter(
            SpeciesVisit.species_id.in_(all_species_ids),
            SpeciesVisit.start_time >= last_30d
        ).group_by(
            SpeciesVisit.species_id,
            'hour'
        ).all()

        # Process hourly activity
        activity_by_species = {sid: [0] * 24 for sid in all_species_ids}
        activity_total = [0] * 24
        for species_id, hour, count in hourly_activity:
            hour_idx = int(hour)
            activity_by_species[species_id][hour_idx] = int(count or 0)
            activity_total[hour_idx] += int(count or 0)

        # Get weather preferences with all species combined using visits
        weather_stats = db.session.query(
            func.round(Video.weather_temp).label('temp'),
            Video.weather_clouds,
            func.sum(SpeciesVisit.max_simultaneous).label('count')
        ).join(
            VideoSpecies, Video.id == VideoSpecies.video_id
        ).join(
            SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id
        ).filter(
            SpeciesVisit.species_id.in_(all_species_ids),
            Video.weather_temp.isnot(None)
        ).group_by(
            func.round(Video.weather_temp),
            Video.weather_clouds
        ).all()

        # Get food preferences with all species combined using visits
        food_stats = db.session.query(
            BirdFood.name,
            func.sum(SpeciesVisit.max_simultaneous).label('count')
        ).join(
            video_bird_food_association,
            BirdFood.id == video_bird_food_association.c.birdfood_id
        ).join(
            Video,
            Video.id == video_bird_food_association.c.video_id
        ).join(
            VideoSpecies, VideoSpecies.video_id == Video.id
        ).join(
            SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id
        ).filter(
            SpeciesVisit.species_id.in_(all_species_ids)
        ).group_by(
            BirdFood.name
        ).order_by(
            func.sum(SpeciesVisit.max_simultaneous).desc()
        ).limit(5).all()

        # Get 10 most recent visits
        recent_visits = (
            db.session.query(SpeciesVisit)
            .filter(SpeciesVisit.species_id.in_(all_species_ids))
            .order_by(SpeciesVisit.start_time.desc())
            .limit(10)
            .all()
        )

        # Format recent visits to match timeline endpoint format
        formatted_visits = []
        for visit in recent_visits:
            # Get the first video for weather data
            video = visit.video_species[0].video if visit.video_species else None

            # Prepare detections for this visit
            detections = []
            sorted_video_species = sorted(
                visit.video_species, key=lambda x: x.created_at, reverse=True)
            for video_species in sorted_video_species:
                video_start_time = video_species.video.start_time
                det = {
                    'video_id': video_species.video_id,
                    'start_time': (video_start_time + timedelta(seconds=video_species.start_time)).astimezone(timezone.utc).isoformat(),
                    'end_time': (video_start_time + timedelta(seconds=video_species.end_time)).astimezone(timezone.utc).isoformat(),
                    'confidence': video_species.confidence,
                    'source': video_species.source
                }
                if video_species.detection_provider:
                    det['detection_provider'] = video_species.detection_provider
                detections.append(det)

            formatted_visits.append({
                'id': visit.id,
                'start_time': visit.start_time.astimezone(timezone.utc).isoformat(),
                'end_time': visit.end_time.astimezone(timezone.utc).isoformat(),
                'max_simultaneous': visit.max_simultaneous,
                'weather': {
                    'temp': video.weather_temp if video else None,
                    'clouds': video.weather_clouds if video else None,
                } if video else None,
                'species': {
                    'id': visit.species.id,
                    'name': visit.species.name,
                    'image_url': visit.species.image_url,
                    'parent_id': visit.species.parent_id,
                },
                'detections': detections
            })

        # Construct response
        response = {
            'species': {
                'id': species.id,
                'name': species.name,
                'image_url': species.image_url,
                'description': species.description,
                'active': species.active,
                'parent': {
                    'id': species.parent.id,
                    'name': species.parent.name
                } if species.parent else None
            },
            'stats': {
                'detections': {
                    'detections_24h': sum(stats_24h.values() or [0]),
                    'detections_7d': sum(stats_7d.values() or [0]),
                    'detections_30d': sum(stats_30d.values() or [0]),
                },
                'timeRange': {
                    'first_sighting': sightings.first.isoformat() if sightings.first else None,
                    'last_sighting': sightings.last.isoformat() if sightings.last else None,
                },
                'hourlyActivity': activity_total,
                'weather': [
                    {
                        'temp': temp,
                        'clouds': clouds,
                        'count': int(count or 0)
                    } for temp, clouds, count in weather_stats
                ],
                'food': [
                    {
                        'name': name,
                        'count': int(count or 0)
                    } for name, count in food_stats
                ]
            },
            'subspecies': [{
                'species': {
                    'id': child.id,
                    'name': child.name,
                    'image_url': child.image_url,
                },
                'stats': {
                    'detections': {
                        'detections_24h': stats_24h.get(child.id, 0),
                        'detections_7d': stats_7d.get(child.id, 0),
                        'detections_30d': stats_30d.get(child.id, 0),
                    },
                    'hourlyActivity': activity_by_species[child.id]
                }
            } for child in children],
            'recentVisits': formatted_visits  # Add recent visits to the response
        }

        return response
