import os
import re
import threading
from datetime import datetime, timezone, timedelta
import psutil
from flask import request
import shutil
from models import ActivityLog, db, Video, Species, VideoSpecies, SpeciesVisit
from sqlalchemy import func
from services.retention_service import run_retention
from app_config.app_config import app_config
from util import settings_check_access, recordings_dir

# Last spectrogram regeneration result (for status polling)
_regenerate_status = {'status': 'idle', 'result': None, 'error': None}
_regenerate_tracks_status = {'status': 'idle', 'result': None, 'error': None}


IMPORT_SPECIES_NAME = "Unknown"


def register_routes(app):
    @app.route('/api/ui/system/metrics', methods=['GET'])
    def system_metrics():
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.5)

            # Try to read Raspberry Pi CPU temperature
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = float(f.read().strip()) / 1000.0
                cpu_temp = round(temp, 1)
            except OSError:
                cpu_temp = None

            # Memory information
            memory = psutil.virtual_memory()
            memory_total_gb = round(memory.total / (1024**3), 1)
            memory_used_gb = round(memory.used / (1024**3), 1)
            memory_percent = memory.percent

            # Disk information for the root filesystem
            disk = psutil.disk_usage('/')
            disk_total_gb = round(disk.total / (1024**3), 1)
            disk_used_gb = round(disk.used / (1024**3), 1)
            disk_percent = disk.percent

            metrics = {
                'cpu': {
                    'percent': cpu_percent,
                    'temperature': cpu_temp
                },
                'memory': {
                    'total': memory_total_gb,
                    'used': memory_used_gb,
                    'percent': memory_percent
                },
                'disk': {
                    'total': disk_total_gb,
                    'used': disk_used_gb,
                    'percent': disk_percent
                }
            }

            return metrics

        except Exception as e:
            app.logger.error(f"Error getting system metrics: {str(e)}")
            return {'error': 'Failed to get system metrics'}, 500

    @app.route('/api/ui/system/activity', methods=['GET'])
    def get_activity():
        month = request.args.get('month', datetime.now().strftime('%Y-%m'))
        start_date = datetime.strptime(month, '%Y-%m')
        end_date = (start_date.replace(day=1) +
                    timedelta(days=32)).replace(day=1)

        activities = db.session.query(
            func.strftime('%Y-%m-%d', ActivityLog.created_at).label('date'),
            func.sum(
                func.strftime('%s', ActivityLog.updated_at) -
                func.strftime('%s', ActivityLog.created_at)
            ).label('total_uptime')  # in seconds
        ).filter(
            ActivityLog.type == 'heartbeat',
            ActivityLog.created_at >= start_date,
            ActivityLog.created_at < end_date
        ).group_by(
            func.strftime('%Y-%m-%d', ActivityLog.created_at)
        ).all()

        return [{
            'date': day,
            # convert to hours
            'totalUptime': round(duration / 3600, 1) if duration else 0
        } for day, duration in activities]

    def get_day_storage_info(day_path):
        """Get total size and file count for a day directory including all timestamp subdirs"""
        total_size = 0
        total_files = 0
        try:
            # Iterate through timestamp directories
            for timestamp in os.listdir(day_path):
                timestamp_path = os.path.join(day_path, timestamp)
                if not os.path.isdir(timestamp_path):
                    continue

                # Count all files in timestamp directory
                for file in os.listdir(timestamp_path):
                    file_path = os.path.join(timestamp_path, file)
                    if os.path.isfile(file_path):
                        try:
                            total_size += os.path.getsize(file_path)
                            total_files += 1
                        except OSError as e:
                            app.logger.error(
                                f"Error getting size for {file_path}: {e}")

        except Exception as e:
            app.logger.error(f"Error processing day directory {day_path}: {e}")

        return total_files, total_size

    @app.route('/api/ui/storage/stats', methods=['GET'])
    def get_storage_stats():
        if not os.path.exists(recordings_dir()):
            return [], 200

        stats = []
        # Walk through year/month/day structure
        try:
            rec_dir = recordings_dir()
            for year in sorted(os.listdir(rec_dir), reverse=True):
                year_path = os.path.join(rec_dir, year)
                if not os.path.isdir(year_path):
                    continue

                for month in sorted(os.listdir(year_path), reverse=True):
                    month_path = os.path.join(year_path, month)
                    if not os.path.isdir(month_path):
                        continue

                    for day in sorted(os.listdir(month_path), reverse=True):
                        day_path = os.path.join(month_path, day)
                        if not os.path.isdir(day_path):
                            continue

                        # Get storage info for this day (including all timestamp subdirs)
                        file_count, total_size = get_day_storage_info(day_path)

                        if file_count > 0:  # Only include days with files
                            stats.append({
                                'date': f"{year}-{month}-{day}",
                                'fileCount': file_count,
                                'totalSize': total_size
                            })

        except Exception as e:
            app.logger.error(f"Error scanning recordings directory: {e}")

        return stats, 200

    @app.route('/api/ui/storage/purge', methods=['POST'])
    def purge_storage():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            date_str = request.json.get('date')
            if not date_str:
                return {'error': 'Date is required'}, 400

            try:
                purge_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                return {'error': 'Invalid date format, use YYYY-MM-DD'}, 400

            deleted_count = 0
            deleted_size = 0

            # Walk through the recordings directory
            rec_dir = recordings_dir()
            for year in os.listdir(rec_dir):
                year_path = os.path.join(rec_dir, year)
                if not os.path.isdir(year_path):
                    continue

                for month in os.listdir(year_path):
                    month_path = os.path.join(year_path, month)
                    if not os.path.isdir(month_path):
                        continue

                    for day in os.listdir(month_path):
                        day_path = os.path.join(month_path, day)
                        if not os.path.isdir(day_path):
                            continue

                        # Check if this directory is before or on purge date
                        dir_date = datetime.strptime(
                            f"{year}-{month}-{day}", '%Y-%m-%d')
                        if dir_date <= purge_date:
                            # Calculate stats before deletion
                            count, size = get_day_storage_info(day_path)
                            deleted_count += count
                            deleted_size += size

                            # Remove the directory and all contents
                            shutil.rmtree(day_path)

                    # Clean up empty month directory
                    if not os.listdir(month_path):
                        os.rmdir(month_path)

                # Clean up empty year directory
                if not os.listdir(year_path):
                    os.rmdir(year_path)

            return {
                'message': f'Successfully deleted {deleted_count} files',
                'deletedCount': deleted_count,
                'deletedSize': deleted_size
            }, 200

        except Exception as e:
            app.logger.error(f"Error during purge: {str(e)}")
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/retention', methods=['POST'])
    def trigger_retention():
        """Run retention policy (delete old recordings)."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            count, size = run_retention()
            return {
                'message': f'Deleted {count} recordings',
                'deletedCount': count,
                'deletedSize': size,
            }, 200
        except Exception as e:
            app.logger.error(f"Retention failed: {e}")
            return {'error': str(e)}, 500

    def _run_regenerate_spectrograms(force: bool):
        """Background task: regenerate spectrograms. Uses own app context and db session."""
        global _regenerate_status
        _regenerate_status = {'status': 'running', 'result': None, 'error': None}
        try:
            with app.app_context():
                try:
                    import sys
                    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'processor', 'src'))
                    from spectrogram import generate_spectrogram
                except ImportError as e:
                    app.logger.error(f'Spectrogram import failed: {e}')
                    _regenerate_status = {'status': 'done', 'result': None, 'error': str(e)}
                    return

                base = os.path.dirname(os.path.dirname(recordings_dir()))
                px_per_sec = app_config.get('processor.spectrogram_px_per_sec') or 200
                spectrogram_filename = f'spectrogram_{px_per_sec}.jpg'

                query = Video.query
                if not force:
                    query = query.filter(
                        (Video.spectrogram_path == None) | (Video.spectrogram_path == '')
                    )
                videos = query.all()

                generated = 0
                failed = 0
                skipped = 0

                for video in videos:
                    if not video.video_path:
                        skipped += 1
                        continue
                    full_video = os.path.join(base, video.video_path)
                    if not os.path.isfile(full_video):
                        skipped += 1
                        continue
                    out_dir = os.path.dirname(full_video)
                    out_path = os.path.join(out_dir, spectrogram_filename)

                    if generate_spectrogram(full_video, out_path, px_per_sec):
                        rel_spectrogram = os.path.join(
                            os.path.dirname(video.video_path), spectrogram_filename
                        ).replace('\\', '/')
                        video.spectrogram_path = rel_spectrogram
                        generated += 1
                    else:
                        failed += 1

                try:
                    db.session.commit()
                    app.logger.info(
                        f'Spectrograms: generated={generated}, failed={failed}, skipped={skipped}'
                    )
                    _regenerate_status = {
                        'status': 'done',
                        'result': {'generated': generated, 'failed': failed, 'skipped': skipped},
                        'error': None,
                    }
                except Exception as e:
                    db.session.rollback()
                    app.logger.exception(f'Spectrogram commit failed: {e}')
                    _regenerate_status = {'status': 'done', 'result': None, 'error': str(e)}
        except Exception as e:
            app.logger.exception(f'Regenerate spectrograms failed: {e}')
            _regenerate_status = {'status': 'done', 'result': None, 'error': str(e)}

    @app.route('/api/ui/system/regenerate-spectrograms', methods=['POST'])
    def regenerate_spectrograms():
        """
        Start spectrogram regeneration in background. Returns immediately.
        Processes videos without spectrograms (or all if force=true).
        Poll GET .../status to get result.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        force = (request.json or {}).get('force', False)
        t = threading.Thread(target=_run_regenerate_spectrograms, args=(force,), daemon=True)
        t.start()
        return {
            'message': 'Regeneration started in background.',
            'started': True,
        }, 202

    @app.route('/api/ui/system/regenerate-spectrograms/status', methods=['GET'])
    def regenerate_spectrograms_status():
        """Return last regeneration result: {status, result: {generated, failed, skipped}, error}."""
        return _regenerate_status, 200

    def _run_regenerate_tracks(force: bool):
        """Background: run YOLO+ByteTrack on old videos, replace VideoSpecies with tracks."""
        global _regenerate_tracks_status
        _regenerate_tracks_status = {'status': 'running', 'result': None, 'error': None}
        try:
            with app.app_context():
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'processor', 'src'))
                from track_regenerator import process_video_for_tracks
                from services.visit_processor import VisitProcessor

                base = os.path.dirname(os.path.dirname(recordings_dir()))
                lores_size = (640, 640)

                if force:
                    videos = Video.query.all()
                else:
                    from sqlalchemy import or_
                    videos = Video.query.join(VideoSpecies).filter(
                        or_(VideoSpecies.frames.is_(None), VideoSpecies.frames == '')
                    ).distinct().all()

                generated = 0
                failed = 0
                skipped = 0

                visit_processor = VisitProcessor(db, app.logger)

                for video in videos:
                    if not video.video_path:
                        skipped += 1
                        continue
                    full_video = os.path.join(base, video.video_path)
                    if not os.path.isfile(full_video):
                        skipped += 1
                        continue

                    try:
                        detections = process_video_for_tracks(
                            full_video, lores_size
                        )
                        if not detections:
                            skipped += 1
                            continue

                        VideoSpecies.query.filter_by(video_id=video.id).delete()
                        visit_processor.process_detections(video, detections)
                        generated += 1
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        app.logger.exception(f'Track regen failed {video.video_path}: {e}')
                        failed += 1

                app.logger.info(
                    f'Tracks: generated={generated}, failed={failed}, skipped={skipped}'
                )
                _regenerate_tracks_status = {
                    'status': 'done',
                    'result': {'generated': generated, 'failed': failed, 'skipped': skipped},
                    'error': None,
                }
        except Exception as e:
            db.session.rollback()
            app.logger.exception(f'Regenerate tracks failed: {e}')
            _regenerate_tracks_status = {'status': 'done', 'result': None, 'error': str(e)}

    @app.route('/api/ui/system/regenerate-tracks', methods=['POST'])
    def regenerate_tracks():
        """Start track regeneration in background. Processes videos without tracks (or all if force)."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        force = (request.json or {}).get('force', False)
        t = threading.Thread(target=_run_regenerate_tracks, args=(force,), daemon=True)
        t.start()
        return {'message': 'Track regeneration started.', 'started': True}, 202

    @app.route('/api/ui/system/regenerate-tracks/status', methods=['GET'])
    def regenerate_tracks_status():
        """Return last track regeneration result."""
        return _regenerate_tracks_status, 200

    @app.route('/api/ui/system/recordings/scan', methods=['POST'])
    def scan_recordings():
        """
        Scan data/recordings/ for video.mp4 not in DB and add them.
        Fixes recordings missing from stats after server restart.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        if not os.path.exists(recordings_dir()):
            return {'imported': 0, 'message': 'No recordings directory'}, 200

        species = Species.query.filter_by(name=IMPORT_SPECIES_NAME).first()
        if not species:
            species = Species(name=IMPORT_SPECIES_NAME, active=False)
            db.session.add(species)
            db.session.flush()

        existing_paths = {
            v.video_path for v in db.session.query(Video.video_path).all()
        }
        imported = 0
        # YYYY/MM/DD/HHMMSS или YYYY/MM/DD/HH-MM-SS
        pattern = re.compile(
            r'^(\d{4})/(\d{2})/(\d{2})/(\d{2})[-:]?(\d{2})[-:]?(\d{2})$'
        )

        try:
            rec_dir = recordings_dir()
            for year in os.listdir(rec_dir):
                year_path = os.path.join(rec_dir, year)
                if not os.path.isdir(year_path) or not year.isdigit():
                    continue
                for month in os.listdir(year_path):
                    month_path = os.path.join(year_path, month)
                    if not os.path.isdir(month_path) or not month.isdigit():
                        continue
                    for day in os.listdir(month_path):
                        day_path = os.path.join(month_path, day)
                        if not os.path.isdir(day_path) or not day.isdigit():
                            continue
                        for ts in os.listdir(day_path):
                            ts_path = os.path.join(day_path, ts)
                            if not os.path.isdir(ts_path):
                                continue
                            m = pattern.match(f'{year}/{month}/{day}/{ts}')
                            if not m:
                                continue
                            video_mp4 = os.path.join(ts_path, 'video.mp4')
                            if not os.path.isfile(video_mp4):
                                continue
                            rel_path = f'data/recordings/{year}/{month}/{day}/{ts}/video.mp4'
                            if rel_path in existing_paths:
                                continue

                            try:
                                with db.session.begin_nested():
                                    y, mo, d, h, mi, s = map(int, m.groups())
                                    start_time = datetime(
                                        y, mo, d, h, mi, s,
                                        tzinfo=timezone.utc
                                    )
                                    end_time = start_time + timedelta(
                                        seconds=30
                                    )
                                    spectrogram = None
                                    for f in os.listdir(ts_path):
                                        if (f.startswith('spectrogram') and
                                                f.endswith('.jpg')):
                                            spectrogram = f'data/recordings/{year}/{month}/{day}/{ts}/{f}'
                                            break

                                    video = Video(
                                        processor_version='1',
                                        start_time=start_time,
                                        end_time=end_time,
                                        video_path=rel_path,
                                        spectrogram_path=spectrogram,
                                    )
                                    db.session.add(video)
                                    db.session.flush()

                                    visit = SpeciesVisit(
                                        species_id=species.id,
                                        start_time=start_time,
                                        end_time=end_time,
                                        max_simultaneous=1,
                                    )
                                    db.session.add(visit)
                                    db.session.flush()

                                vs = VideoSpecies(
                                    video_id=video.id,
                                    species_id=species.id,
                                    species_visit_id=visit.id,
                                    start_time=0,
                                    end_time=30,
                                    confidence=0,
                                    source='video',
                                    detection_provider='legacy',
                                    created_at=start_time,
                                )
                                db.session.add(vs)
                                existing_paths.add(rel_path)
                                imported += 1
                            except Exception as e:
                                app.logger.warning(
                                    f'Import failed {rel_path}: {e}'
                                )
                                continue

            db.session.commit()

            # Auto-start spectrogram regeneration for newly imported videos
            if imported > 0:
                t = threading.Thread(target=_run_regenerate_spectrograms, args=(False,), daemon=True)
                t.start()

            return {
                'imported': imported,
                'message': f'Imported {imported} recordings',
                'spectrogramRegenerationStarted': imported > 0,
            }, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception(f'Scan recordings failed: {e}')
            return {'error': str(e)}, 500
