import json
import os
import re
from flask import request
from datetime import datetime, timezone
from models import ActivityLog, db, BirdFood, Video, Species, VideoSpecies, SpeciesVisit
from util import fetch_weather, notify, filter_feeder_species
from services.visit_processor import VisitProcessor
from app_config.app_config import app_config

# Path traversal protection: video_path must match data/recordings/YYYY/MM/DD/timestamp/video.mp4
VIDEO_PATH_RE = re.compile(r'^data/recordings/\d{4}/\d{2}/\d{2}/[\d\-:]+/video\.mp4$')


def _check_processor_secret():
    """Return True if request is from processor (has valid secret) or secret is not configured."""
    secret = os.environ.get('PROCESSOR_SECRET', '').strip()
    if not secret:
        return True
    return request.headers.get('X-Processor-Token') == secret


def register_routes(app):
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
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid datetime format: {e}'}, 400

        # Validate required data
        species_list = data.get('species', [])
        if not species_list:
            return {'error': 'Missing species'}, 400

        video_path = (data.get('video_path') or '').strip()
        if not VIDEO_PATH_RE.match(video_path):
            return {'error': 'Invalid video_path format'}, 400

        try:
            # Create video record
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

            # Process all detections
            visit_processor = VisitProcessor(db, app.logger)
            visit_processor.process_detections(video, species_list)

            # Save everything
            db.session.commit()

            return {'message': 'Video and associated data inserted successfully.'}, 201

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
        if not active_names:
            return {"message": "success", "active_feeder_names": []}, 200
        active_feeder_names = filter_feeder_species(active_names)

        # Reset all to inactive
        db.session.query(Species).update({'active': False})

        # Set provided species as active
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
        detection = request.json.get('detection')
        excluded_species = app_config.get(
            'general.notification_excluded_species', [])
        if detection not in excluded_species:
            lower = detection.lower()
            icon = "chipmunk" if any(s in lower for s in ("squirrel", "chipmunk", "mouse", "мышь", "белка")) else "bird"
            notify(f"{detection} Detected", tags=icon)
        return {'message': f'Successfully received notification of {detection}'}, 200

    @app.route('/api/processor/notify/motion', methods=['POST'])
    def notify_motion_route():
        if not _check_processor_secret():
            return {'error': 'Forbidden'}, 403
        return {'message': f'Successfully received notification of motion'}, 200

    @app.route('/api/processor/activity_log', methods=['POST'])
    def add_or_update_activity_log():
        if not _check_processor_secret():
            return {'error': 'Forbidden'}, 403
        try:
            data = request.json or {}
            activity_type = data.get('type')
            raw_data = data.get('data')
            activity_data = json.dumps(raw_data) if raw_data is not None else '{}'
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
                log = ActivityLog.query.get(activity_id)
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
