import os
import re
import threading
import sqlite3
import tempfile
from collections import deque
from datetime import datetime, timezone, timedelta
import psutil
from flask import request, Response, send_file
import shutil
from models import ActivityLog, db, Video, Species, VideoSpecies, SpeciesVisit, SystemResourceSample
from sqlalchemy import func, select, exists, delete
from services.retention_service import run_retention
from services.species_registry_service import (
    ensure_species_registry_seeded,
    backfill_species_taxa,
    enrich_species_metadata,
    enrich_species_metadata_with_status,
    species_registry_health,
    unresolved_species_report,
)
from app_config.app_config import app_config
from util import settings_check_access, recordings_dir

# Last spectrogram regeneration result (for status polling)
_regenerate_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_regenerate_tracks_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_regenerate_lock = threading.Lock()
_regenerate_tracks_lock = threading.Lock()
_species_metadata_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_species_metadata_lock = threading.Lock()


IMPORT_SPECIES_NAME = "Unknown"
LOG_LINES_DEFAULT = 200
LOG_LINES_MAX = 500

SYSTEM_METRICS_SAMPLE_INTERVAL_SEC = 30
SYSTEM_METRICS_RETENTION_HOURS = 72
SYSTEM_METRICS_HISTORY_MAX_HOURS = 168
SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP = 2000
SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS = 500

_sampler_lock = threading.Lock()
_sampler_started = False


def _downsample_evenly(items, max_n: int):
    """Равномерно проредить список до max_n элементов (сохраняем концы)."""
    n = len(items)
    if n <= max_n or max_n < 2:
        return items
    out = []
    for i in range(max_n):
        idx = int(round(i * (n - 1) / (max_n - 1)))
        out.append(items[idx])
    return out


def _record_system_resource_sample(app) -> None:
    m = _collect_live_system_metrics(app)
    now = datetime.now(timezone.utc)
    row = SystemResourceSample(
        recorded_at=now,
        cpu_percent=float(m['cpu']['percent']),
        memory_percent=float(m['memory']['percent']),
        disk_percent=float(m['disk']['percent']),
        gpu_percent=float(m['gpu_percent']) if m['gpu_percent'] is not None else None,
    )
    db.session.add(row)
    cutoff = now - timedelta(hours=SYSTEM_METRICS_RETENTION_HOURS)
    db.session.execute(
        delete(SystemResourceSample).where(SystemResourceSample.recorded_at < cutoff)
    )
    db.session.commit()


def _system_metrics_sampler_worker(app):
    import time
    while True:
        try:
            with app.app_context():
                _record_system_resource_sample(app)
        except Exception as e:
            app.logger.warning('system metrics sampler: %s', e)
            try:
                db.session.rollback()
            except Exception:
                pass
        time.sleep(SYSTEM_METRICS_SAMPLE_INTERVAL_SEC)


def _start_system_metrics_sampler(app):
    global _sampler_started
    if os.environ.get('DISABLE_SYSTEM_METRICS_SAMPLER', '').strip().lower() in (
        '1', 'true', 'yes',
    ):
        return
    with _sampler_lock:
        if _sampler_started:
            return
        _sampler_started = True
    threading.Thread(
        target=_system_metrics_sampler_worker,
        args=(app,),
        name='system-metrics-sampler',
        daemon=True,
    ).start()


def _collect_visitor_stats(visitors_days: int = 7) -> dict:
    """Агрегаты посетителей по БД (не системные мгновенные метрики)."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    days = max(1, min(int(visitors_days or 7), 365))
    start_utc = now_utc - timedelta(days=days)
    unique_visit_sessions = db.session.query(func.count(SpeciesVisit.id)).filter(
        SpeciesVisit.start_time >= start_utc
    ).scalar() or 0
    active_days = db.session.query(
        func.count(func.distinct(func.strftime('%Y-%m-%d', SpeciesVisit.start_time)))
    ).filter(SpeciesVisit.start_time >= start_utc).scalar() or 0
    return {
        'period_days': days,
        'unique_visits': int(unique_visit_sessions),
        'active_days': int(active_days),
        'method': 'species_visit_sessions',
    }


def _collect_live_system_metrics(app):
    """Мгновенный снимок: CPU, память, диск, GPU (без запросов к БД по посетителям)."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    memory_total_gb = round(memory.total / (1024**3), 1)
    memory_used_gb = round(memory.used / (1024**3), 1)
    memory_percent = memory.percent
    disk = psutil.disk_usage('/')
    disk_total_gb = round(disk.total / (1024**3), 1)
    disk_used_gb = round(disk.used / (1024**3), 1)
    disk_percent = disk.percent

    gpu_percent = None
    for path in ('/sys/class/drm/card0/device/gpu_busy_percent',
                 '/sys/class/drm/card0/device/utilization'):
        try:
            with open(path) as f:
                raw = f.read().strip()
            val = int(raw)
            if 0 <= val <= 100:
                gpu_percent = val
            elif 0 <= val <= 255:
                gpu_percent = round(100 * val / 255)
            if gpu_percent is not None:
                break
        except (OSError, ValueError):
            continue
    encoding_setting = (app_config.get('video.encoding') or 'cpu').strip().lower()
    if encoding_setting not in ('cpu', 'intel'):
        encoding_setting = 'cpu'
    intel_gpu = encoding_setting == 'intel' or os.path.exists('/dev/dri/renderD128')
    if gpu_percent is None and intel_gpu:
        try:
            from gpu_stats import get_intel_gpu_percent
            gpu_percent = get_intel_gpu_percent()
        except Exception as e:
            app.logger.warning("gpu_stats: %s", e)

    return {
        'cpu': {'percent': cpu_percent},
        'memory': {
            'total': memory_total_gb, 'used': memory_used_gb, 'percent': memory_percent,
            'total_bytes': memory.total, 'used_bytes': memory.used,
        },
        'disk': {'total': disk_total_gb, 'used': disk_used_gb, 'percent': disk_percent},
        'encoding': encoding_setting,
        'gpu_percent': gpu_percent,
    }


def register_routes(app):
    def _sqlite_db_path() -> str | None:
        uri = str(db.engine.url)
        if not uri.startswith('sqlite:///'):
            return None
        return db.engine.url.database

    def _prometheus_metrics_body(app):
        sys_m = _collect_live_system_metrics(app)
        detections = db.session.query(func.count(VideoSpecies.id)).scalar() or 0
        species_count = db.session.query(VideoSpecies.species_id).distinct().count()
        videos_count = db.session.query(func.count(Video.id)).scalar() or 0
        lines = [
            '# HELP birdlense_cpu_usage_percent CPU usage',
            '# TYPE birdlense_cpu_usage_percent gauge',
            f'birdlense_cpu_usage_percent {sys_m["cpu"]["percent"]}',
            '# HELP birdlense_memory_used_percent Memory usage percent',
            '# TYPE birdlense_memory_used_percent gauge',
            f'birdlense_memory_used_percent {sys_m["memory"]["percent"]}',
            '# HELP birdlense_memory_total_bytes Memory total in bytes',
            '# TYPE birdlense_memory_total_bytes gauge',
            f'birdlense_memory_total_bytes {sys_m["memory"]["total_bytes"]}',
            '# HELP birdlense_memory_used_bytes Memory used in bytes',
            '# TYPE birdlense_memory_used_bytes gauge',
            f'birdlense_memory_used_bytes {sys_m["memory"]["used_bytes"]}',
            '# HELP birdlense_disk_used_percent Disk usage percent',
            '# TYPE birdlense_disk_used_percent gauge',
            f'birdlense_disk_used_percent {sys_m["disk"]["percent"]}',
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
        if sys_m['gpu_percent'] is not None:
            lines.extend([
                '# HELP birdlense_gpu_usage_percent GPU usage',
                '# TYPE birdlense_gpu_usage_percent gauge',
                f'birdlense_gpu_usage_percent {sys_m["gpu_percent"]}',
            ])
        return '\n'.join(lines) + '\n'

    @app.route('/api/metrics', methods=['GET'])
    def prometheus_metrics_api():
        """Prometheus exposition format для Grafana. CPU, память, диск, GPU, detections, species, videos."""
        try:
            body = _prometheus_metrics_body(app)
            return Response(body, mimetype='text/plain; charset=utf-8')
        except Exception as e:
            app.logger.error(f"Error getting Prometheus metrics: {str(e)}")
            return Response('# Error\n', mimetype='text/plain; charset=utf-8', status=500)

    @app.route('/metrics', methods=['GET'])
    def prometheus_metrics():
        """Prometheus metrics (alias for /api/metrics)."""
        try:
            body = _prometheus_metrics_body(app)
            return Response(body, mimetype='text/plain; charset=utf-8')
        except Exception as e:
            app.logger.error(f"Error getting Prometheus metrics: {str(e)}")
            return Response('# Error\n', mimetype='text/plain; charset=utf-8', status=500)

    @app.route('/api/ui/system/metrics', methods=['GET'])
    def system_metrics():
        """Мгновенные метрики хоста (опрос UI). Без агрегатов посетителей — см. /api/ui/system/visitors."""
        try:
            m = _collect_live_system_metrics(app)
            return {
                'cpu': m['cpu'],
                'memory': m['memory'],
                'disk': m['disk'],
                'encoding': m['encoding'],
                'gpu_percent': m['gpu_percent'],
            }
        except Exception as e:
            app.logger.error(f"Error getting system metrics: {str(e)}")
            return {'error': 'Failed to get system metrics'}, 500

    @app.route('/api/ui/system/visitors', methods=['GET'])
    def system_visitors():
        try:
            try:
                days = int(request.args.get('days', '7'))
            except (TypeError, ValueError):
                days = 7
            return _collect_visitor_stats(days)
        except Exception as e:
            app.logger.error(f"Error getting visitor stats: {str(e)}")
            return {'error': 'Failed to get visitor stats'}, 500

    @app.route('/api/ui/system/metrics/history', methods=['GET'])
    def system_metrics_history():
        """Серверная история снимков (см. фоновый sampler), с прореживанием для графика."""
        try:
            try:
                hours = int(request.args.get('hours', '24'))
            except (TypeError, ValueError):
                hours = 24
            hours = max(1, min(hours, SYSTEM_METRICS_HISTORY_MAX_HOURS))
            try:
                max_points = int(
                    request.args.get('max_points', str(SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS)),
                )
            except (TypeError, ValueError):
                max_points = SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS
            max_points = max(50, min(max_points, SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP))
            now = datetime.now(timezone.utc)
            start = now - timedelta(hours=hours)
            rows = db.session.scalars(
                select(SystemResourceSample)
                .where(SystemResourceSample.recorded_at >= start)
                .order_by(SystemResourceSample.recorded_at.asc())
            ).all()
            rows = _downsample_evenly(rows, max_points)
            return {
                'samples': [
                    {
                        't': r.recorded_at.isoformat(),
                        'cpu': round(r.cpu_percent, 2),
                        'memory': round(r.memory_percent, 2),
                        'disk': round(r.disk_percent, 2),
                        'gpu': None if r.gpu_percent is None else round(r.gpu_percent, 2),
                    }
                    for r in rows
                ],
                'sample_interval_seconds': SYSTEM_METRICS_SAMPLE_INTERVAL_SEC,
                'retention_hours': SYSTEM_METRICS_RETENTION_HOURS,
                'hours_requested': hours,
            }
        except Exception as e:
            app.logger.error(f"Error getting system metrics history: {str(e)}")
            return {'error': 'Failed to get system metrics history'}, 500

    @app.route('/api/ui/system/logs', methods=['GET'])
    def get_processor_logs():
        """Return last N lines of processor.log for remote diagnostics."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            raw = request.args.get('lines', LOG_LINES_DEFAULT)
            lines = max(1, min(int(raw), LOG_LINES_MAX))
        except (ValueError, TypeError):
            lines = LOG_LINES_DEFAULT
        data_dir = os.path.dirname(recordings_dir())
        log_path = os.path.join(data_dir, 'processor.log')
        try:
            if not os.path.isfile(log_path):
                return {'lines': [], 'path': log_path}
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                tail = deque(f, maxlen=lines)
            return {'lines': list(tail), 'path': log_path}
        except OSError as e:
            app.logger.exception('Get processor logs failed')
            return {'error': 'Failed to read logs', 'lines': []}, 500

    @app.route('/api/ui/system/activity', methods=['GET'])
    def get_activity():
        month = request.args.get('month', datetime.now(timezone.utc).strftime('%Y-%m'))
        try:
            start_date = datetime.strptime(month, '%Y-%m')
            if not (2020 <= start_date.year <= 2030 and 1 <= start_date.month <= 12):
                raise ValueError('Year or month out of range')
        except ValueError:
            return {'error': 'Invalid month format, use YYYY-MM'}, 400
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
            data = request.json or {}
            date_str = data.get('date')
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
            app.logger.exception('Purge storage failed')
            return {'error': 'Failed to purge storage'}, 500

    @app.route('/api/ui/system/db/backup', methods=['GET'])
    def backup_database():
        """Download current SQLite database snapshot."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        db_path = _sqlite_db_path()
        if not db_path:
            return {'error': 'DB backup is supported only for SQLite'}, 400
        if not os.path.isfile(db_path):
            return {'error': 'Database file not found'}, 404
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')
        filename = f'birdlense_db_backup_{ts}.db'
        return send_file(
            db_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream',
        )

    @app.route('/api/ui/system/db/restore', methods=['POST'])
    def restore_database():
        """Restore SQLite DB from uploaded .db file; keep pre-restore backup."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        db_path = _sqlite_db_path()
        if not db_path:
            return {'error': 'DB restore is supported only for SQLite'}, 400
        upload = request.files.get('file')
        if not upload:
            return {'error': 'file is required (multipart/form-data)'}, 400

        tmp_dir = tempfile.mkdtemp(prefix='birdlense-db-restore-')
        uploaded_path = os.path.join(tmp_dir, 'uploaded.db')
        backup_path = ''
        try:
            upload.save(uploaded_path)
            if not os.path.isfile(uploaded_path) or os.path.getsize(uploaded_path) == 0:
                return {'error': 'Uploaded file is empty'}, 400

            # Validate uploaded sqlite before touching live DB.
            with sqlite3.connect(uploaded_path) as src:
                check = src.execute('PRAGMA integrity_check;').fetchone()
                if not check or check[0] != 'ok':
                    return {'error': 'Uploaded SQLite file failed integrity_check'}, 400

            db.session.remove()
            db.engine.dispose()

            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')
            backup_path = f'{db_path}.pre_restore_{ts}.bak'
            shutil.copy2(db_path, backup_path)

            with sqlite3.connect(uploaded_path) as src_conn:
                with sqlite3.connect(db_path) as dst_conn:
                    src_conn.backup(dst_conn)

            return {
                'message': 'Database restored successfully',
                'backup_path': backup_path,
            }, 200
        except sqlite3.DatabaseError:
            app.logger.exception('DB restore failed: invalid SQLite payload')
            return {'error': 'Invalid SQLite database file'}, 400
        except Exception as e:
            app.logger.exception('DB restore failed')
            return {'error': f'Failed to restore DB: {e}'}, 500
        finally:
            try:
                shutil.rmtree(tmp_dir)
            except OSError:
                pass

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
            app.logger.exception('Retention failed')
            return {'error': 'Failed to run retention'}, 500

    def _run_regenerate_spectrograms(force: bool, start_date: str | None, end_date: str | None):
        """Background task: regenerate spectrograms. Uses own app context and db session."""
        global _regenerate_status
        _regenerate_status = {
            'status': 'running', 'result': None, 'error': None,
            'progress': {'processed': 0, 'total': 0, 'generated': 0, 'failed': 0, 'skipped': 0},
        }
        try:
            with app.app_context():
                try:
                    import sys
                    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'processor', 'src'))
                    from spectrogram import generate_spectrogram
                except ImportError as e:
                    app.logger.exception('Spectrogram import failed')
                    _regenerate_status = {'status': 'done', 'result': None, 'error': 'Spectrogram generation failed', 'progress': None}
                    return

                base = os.path.dirname(os.path.dirname(recordings_dir()))
                px_per_sec = app_config.get('processor.spectrogram_px_per_sec') or 200
                spectrogram_filename = f'spectrogram_{px_per_sec}.jpg'

                query = Video.query
                if not force:
                    query = query.filter(
                        (Video.spectrogram_path == None) | (Video.spectrogram_path == '')
                    )
                if start_date:
                    try:
                        dt_start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                        query = query.filter(Video.start_time >= dt_start)
                    except ValueError:
                        pass
                if end_date:
                    try:
                        dt_end = datetime.strptime(end_date, '%Y-%m-%d').replace(
                            tzinfo=timezone.utc
                        ) + timedelta(days=1)
                        query = query.filter(Video.start_time < dt_end)
                    except ValueError:
                        pass
                videos = query.order_by(Video.start_time.asc()).all()

                total = len(videos)
                _regenerate_status['progress']['total'] = total

                generated = 0
                failed = 0
                skipped = 0

                for video in videos:
                    if not video.video_path:
                        skipped += 1
                        _regenerate_status['progress'].update(
                            processed=generated + failed + skipped,
                            generated=generated, failed=failed, skipped=skipped,
                        )
                        continue
                    full_video = os.path.join(base, video.video_path)
                    if not os.path.isfile(full_video):
                        skipped += 1
                        _regenerate_status['progress'].update(
                            processed=generated + failed + skipped,
                            generated=generated, failed=failed, skipped=skipped,
                        )
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

                    _regenerate_status['progress'].update(
                        processed=generated + failed + skipped,
                        generated=generated, failed=failed, skipped=skipped,
                    )

                try:
                    db.session.commit()
                    app.logger.info(
                        f'Spectrograms: generated={generated}, failed={failed}, skipped={skipped}'
                    )
                    _regenerate_status = {
                        'status': 'done',
                        'result': {'generated': generated, 'failed': failed, 'skipped': skipped},
                        'error': None,
                        'progress': None,
                    }
                except Exception as e:
                    db.session.rollback()
                    app.logger.exception(f'Spectrogram commit failed: {e}')
                    _regenerate_status = {'status': 'done', 'result': None, 'error': 'Spectrogram generation failed', 'progress': None}
        except Exception:
            app.logger.exception('Regenerate spectrograms failed')
            _regenerate_status = {'status': 'done', 'result': None, 'error': 'Spectrogram generation failed', 'progress': None}

    @app.route('/api/ui/system/regenerate-spectrograms', methods=['POST'])
    def regenerate_spectrograms():
        """
        Start spectrogram regeneration in background. Returns immediately.
        Processes videos without spectrograms (or all if force=true).
        Only available when BirdNET is configured (MQTT broker + birdnet_topic).
        Poll GET .../status to get result.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        mqtt_broker = os.environ.get('MQTT_BROKER') or app_config.get('mqtt.broker')
        birdnet_configured = bool(
            mqtt_broker and (app_config.get('mqtt.birdnet_topic') or '').strip()
        )
        if not birdnet_configured:
            return {
                'error': 'Spectrogram regeneration requires BirdNET (MQTT broker + birdnet_topic)',
            }, 400
        with _regenerate_lock:
            if _regenerate_status['status'] == 'running':
                return {'error': 'Regeneration already in progress', 'status': _regenerate_status}, 409
        data = request.json or {}
        force = data.get('force', False)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        t = threading.Thread(
            target=_run_regenerate_spectrograms,
            args=(force, start_date, end_date),
            daemon=True,
        )
        t.start()
        return {
            'message': 'Regeneration started in background.',
            'started': True,
        }, 202

    @app.route('/api/ui/system/regenerate-spectrograms/status', methods=['GET'])
    def regenerate_spectrograms_status():
        """Return last regeneration result: {status, result: {generated, failed, skipped}, error}."""
        return _regenerate_status, 200

    def _run_regenerate_tracks(force: bool, start_date: str | None, end_date: str | None):
        """Background: run YOLO+ByteTrack on old videos, replace VideoSpecies with tracks.
        start_date, end_date: YYYY-MM-DD — период. None = все.
        """
        global _regenerate_tracks_status
        _regenerate_tracks_status = {
            'status': 'running', 'result': None, 'error': None,
            'progress': {'processed': 0, 'total': 0, 'generated': 0, 'failed': 0, 'skipped': 0},
        }
        try:
            with app.app_context():
                import sys
                from datetime import datetime, timezone, timedelta
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'processor', 'src'))
                from track_regenerator import process_video_for_tracks
                from services.visit_processor import VisitProcessor

                base = os.path.dirname(os.path.dirname(recordings_dir()))
                lores_size = (640, 640)

                if force:
                    q = Video.query
                else:
                    from sqlalchemy import or_
                    q = Video.query.join(VideoSpecies).filter(
                        or_(VideoSpecies.frames.is_(None), VideoSpecies.frames == '')
                    ).distinct()

                if start_date:
                    try:
                        dt_start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                        q = q.filter(Video.start_time >= dt_start)
                    except ValueError:
                        app.logger.warning('Invalid start_date %s, ignoring', start_date)
                if end_date:
                    try:
                        dt_end = datetime.strptime(end_date, '%Y-%m-%d').replace(
                            tzinfo=timezone.utc
                        ) + timedelta(days=1)
                        q = q.filter(Video.start_time < dt_end)
                    except ValueError:
                        app.logger.warning('Invalid end_date %s, ignoring', end_date)

                videos = q.order_by(Video.start_time.asc()).all()
                total = len(videos)
                _regenerate_tracks_status['progress']['total'] = total

                generated = 0
                failed = 0
                skipped = 0
                frames_updated = 0  # videos with manually_corrected: only frames updated

                visit_timeout = int(app_config.get('detection.dedup_window_seconds') or 60)
                visit_processor = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)

                for video in videos:
                    if not video.video_path:
                        skipped += 1
                        _regenerate_tracks_status['progress'].update(
                            processed=generated + failed + skipped,
                            generated=generated, failed=failed, skipped=skipped,
                        )
                        continue
                    full_video = os.path.join(base, video.video_path)
                    if not os.path.isfile(full_video):
                        skipped += 1
                        _regenerate_tracks_status['progress'].update(
                            processed=generated + failed + skipped,
                            generated=generated, failed=failed, skipped=skipped,
                        )
                        continue

                    try:
                        detections = process_video_for_tracks(
                            full_video, lores_size
                        )
                        if not detections:
                            skipped += 1
                            _regenerate_tracks_status['progress'].update(
                                processed=generated + failed + skipped,
                                generated=generated, failed=failed, skipped=skipped,
                            )
                            continue

                        manual_vs = [vs for vs in video.video_species if vs.manually_corrected]
                        if manual_vs:
                            # Только обновить frames (bbox) — виды не трогаем.
                            # Критично: сопоставлять только при совпадении вида, иначе кадр от другой птицы.
                            import json
                            used_det_indices = set()
                            for vs in sorted(manual_vs, key=lambda x: x.start_time):
                                best_idx = None
                                best_overlap = 0.0
                                vs_species_name = vs.species.name if vs.species else None
                                for i, d in enumerate(detections):
                                    if i in used_det_indices:
                                        continue
                                    # Только если вид совпадает — иначе присвоим кадр от другой птицы
                                    if vs_species_name and d.get('species_name') != vs_species_name:
                                        continue
                                    overlap = min(vs.end_time, d['end_time']) - max(vs.start_time, d['start_time'])
                                    if overlap > best_overlap and overlap > 0.3:
                                        best_overlap = overlap
                                        best_idx = i
                                if best_idx is not None and detections[best_idx].get('frames'):
                                    vs.frames = json.dumps(detections[best_idx]['frames'])
                                    used_det_indices.add(best_idx)
                            db.session.flush()
                            # Удалить не-manual, добавить новые детекции (не matched)
                            to_delete = [vs for vs in video.video_species if not vs.manually_corrected]
                            for vs in to_delete:
                                db.session.delete(vs)
                            unmatched = [d for i, d in enumerate(detections) if i not in used_det_indices]
                            if unmatched:
                                visit_processor.process_detections(video, unmatched)
                            frames_updated += 1
                        else:
                            VideoSpecies.query.filter_by(video_id=video.id).delete()
                            visit_processor.process_detections(video, detections)
                            generated += 1
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        app.logger.exception(f'Track regen failed {video.video_path}: {e}')
                        failed += 1

                    _regenerate_tracks_status['progress'].update(
                        processed=generated + failed + skipped,
                        generated=generated, failed=failed, skipped=skipped,
                    )

                app.logger.info(
                    f'Tracks: generated={generated}, frames_updated={frames_updated}, failed={failed}, skipped={skipped}'
                )
                result = {'generated': generated, 'failed': failed, 'skipped': skipped}
                if frames_updated:
                    result['frames_updated'] = frames_updated
                _regenerate_tracks_status = {
                    'status': 'done',
                    'result': result,
                    'error': None,
                    'progress': None,
                }
        except Exception:
            db.session.rollback()
            app.logger.exception('Regenerate tracks failed')
            _regenerate_tracks_status = {
                'status': 'done', 'result': None, 'error': 'Track regeneration failed',
                'progress': None,
            }

    @app.route('/api/ui/system/regenerate-tracks', methods=['POST'])
    def regenerate_tracks():
        """Start track regeneration in background. Processes videos without tracks (or all if force)."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _regenerate_tracks_lock:
            if _regenerate_tracks_status['status'] == 'running':
                return {'error': 'Track regeneration already in progress', 'status': _regenerate_tracks_status}, 409
        data = request.json or {}
        force = data.get('force', False)
        start_date = data.get('start_date')  # YYYY-MM-DD or None
        end_date = data.get('end_date')  # YYYY-MM-DD or None
        t = threading.Thread(
            target=_run_regenerate_tracks,
            args=(force, start_date, end_date),
            daemon=True,
        )
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

            # Auto-start spectrogram regeneration for newly imported videos (если не запущена)
            spectrogram_started = False
            if imported > 0:
                with _regenerate_lock:
                    if _regenerate_status['status'] != 'running':
                        t = threading.Thread(target=_run_regenerate_spectrograms, args=(False,), daemon=True)
                        t.start()
                        spectrogram_started = True

            return {
                'imported': imported,
                'message': f'Imported {imported} recordings',
                'spectrogramRegenerationStarted': spectrogram_started,
            }, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Scan recordings failed')
            return {'error': 'Failed to scan recordings'}, 500

    @app.route('/api/ui/system/clean-orphaned-visits', methods=['POST'])
    def clean_orphaned_visits():
        """
        Удалить осиротевшие SpeciesVisit (без VideoSpecies) и синхронизировать
        VideoSpecies.species_id с visit.species_id. Исправляет некорректные счётчики
        в календаре миграций и каталоге после старых коррекций.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            orphaned = 0
            synced = 0
            # 1. Удалить SpeciesVisit без VideoSpecies (осиротевшие)
            has_vs = exists().where(VideoSpecies.species_visit_id == SpeciesVisit.id)
            orphan_visits = SpeciesVisit.query.filter(~has_vs).all()
            for sv in orphan_visits:
                db.session.delete(sv)
                orphaned += 1
            db.session.flush()
            # 2. Синхронизировать VideoSpecies.species_id с visit.species_id.
            # НЕ перезаписывать manually_corrected — там вид задан пользователем.
            for vs in VideoSpecies.query.filter(VideoSpecies.species_visit_id.isnot(None)).all():
                if not vs.species_visit or vs.species_id == vs.species_visit.species_id:
                    continue
                if vs.manually_corrected:
                    # Вид задан пользователем — обновить visit, а не vs
                    vs.species_visit.species_id = vs.species_id
                    synced += 1
                else:
                    vs.species_id = vs.species_visit.species_id
                    synced += 1
            db.session.commit()
            return {
                'orphaned': orphaned,
                'synced': synced,
                'message': f'Removed {orphaned} orphaned visits, synced {synced} detections',
            }, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Clean orphaned visits failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/merge-duplicate-species', methods=['POST'])
    def merge_duplicate_species():
        """
        Объединить дубликаты видов (Garrulus glandarius (Eurasian Jay) -> Eurasian Jay).
        Использует species_canonical_mapping.txt. Сопоставление без учёта регистра.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            from util import load_species_canonical_mapping
            mapping = load_species_canonical_mapping()
            if not mapping:
                return {'merged': 0, 'message': 'No species_canonical_mapping.txt'}, 200
            # variant_lower -> canonical (для сопоставления без учёта регистра)
            variant_to_canonical = {}
            for variant, canonical in mapping.items():
                variant_to_canonical[variant] = canonical
                variant_to_canonical[variant.lower().strip()] = canonical
            canonical_to_species = {}  # canonical -> [Species]
            for sp in Species.query.all():
                canonical = variant_to_canonical.get(sp.name) or variant_to_canonical.get(sp.name.lower().strip())
                if canonical:
                    canonical_to_species.setdefault(canonical, []).append(sp)
            merged = 0
            details = []
            for canonical, species_list in canonical_to_species.items():
                if len(species_list) <= 1:
                    continue
                target = next((s for s in species_list if s.name == canonical), species_list[0])
                for other in [s for s in species_list if s.id != target.id]:
                    vs_count = VideoSpecies.query.filter_by(species_id=other.id).update(
                        {'species_id': target.id}
                    )
                    sv_count = SpeciesVisit.query.filter_by(species_id=other.id).update(
                        {'species_id': target.id}
                    )
                    Species.query.filter_by(parent_id=other.id).update({'parent_id': target.id})
                    if target.name != canonical:
                        target.name = canonical
                    details.append(f"{other.name} -> {canonical}")
                    db.session.delete(other)
                    merged += 1
            db.session.commit()
            return {'merged': merged, 'details': details, 'message': f'Merged {merged} duplicate species'}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Merge duplicate species failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/seed', methods=['POST'])
    def seed_species_registry():
        """Seed canonical species registry and aliases from mapping file."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            stats = ensure_species_registry_seeded()
            return {'ok': True, **stats}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Seed species registry failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/backfill', methods=['POST'])
    def run_species_registry_backfill():
        """
        Backfill existing Species rows with canonical taxon links.
        body: {"dry_run": true|false, "limit": 500}
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            limit = payload.get('limit')
            if limit is not None:
                try:
                    limit = int(limit)
                except (ValueError, TypeError):
                    return {'error': 'limit must be int'}, 400
            stats = backfill_species_taxa(dry_run=dry_run, limit=limit)
            return {'ok': True, **stats}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Species registry backfill failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/unresolved', methods=['GET'])
    def get_unresolved_species_names():
        """Top unresolved species names captured by resolver."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            raw_limit = request.args.get('limit', 100)
            try:
                limit = int(raw_limit)
            except (ValueError, TypeError):
                limit = 100
            items = unresolved_species_report(limit=limit)
            return {'items': items, 'count': len(items)}, 200
        except Exception as e:
            app.logger.exception('Unresolved species report failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/enrich-metadata', methods=['POST'])
    def run_species_registry_metadata_enrichment():
        """
        Batch metadata enrichment for species cards.
        body: {"dry_run": true|false, "limit": 200}
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            raw_limit = payload.get('limit', 200)
            try:
                limit = int(raw_limit)
            except (TypeError, ValueError):
                return {'error': 'limit must be int'}, 400
            stats = enrich_species_metadata(limit=limit, dry_run=dry_run)
            return {'ok': True, **stats}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Species metadata enrichment failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/enrich-metadata/start', methods=['POST'])
    def start_species_registry_metadata_enrichment():
        """
        Start async enrichment batch.
        body: {"limit": 300, "retry_failed_only": false}
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _species_metadata_lock:
            if _species_metadata_status.get('status') == 'running':
                return {'error': 'Enrichment already running', 'status': _species_metadata_status}, 409
            payload = request.get_json(silent=True) or {}
            try:
                limit = int(payload.get('limit', 300))
            except (ValueError, TypeError):
                return {'error': 'limit must be int'}, 400
            retry_failed_only = bool(payload.get('retry_failed_only', False))
            _species_metadata_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': {'limit': limit, 'retry_failed_only': retry_failed_only},
            })

            def _run():
                try:
                    with app.app_context():
                        stats = enrich_species_metadata_with_status(
                            limit=limit,
                            dry_run=False,
                            retry_failed_only=retry_failed_only,
                        )
                    with _species_metadata_lock:
                        _species_metadata_status.update({
                            'status': 'done',
                            'result': stats,
                            'error': None,
                        })
                except Exception as e:
                    with _species_metadata_lock:
                        _species_metadata_status.update({
                            'status': 'error',
                            'result': None,
                            'error': str(e),
                        })

            threading.Thread(target=_run, daemon=True).start()
            return {'message': 'Species metadata enrichment started', 'status': _species_metadata_status}, 202

    @app.route('/api/ui/system/species-registry/enrich-metadata/status', methods=['GET'])
    def species_registry_metadata_enrichment_status():
        """Get async enrichment status."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _species_metadata_lock:
            return dict(_species_metadata_status), 200

    @app.route('/api/ui/system/species-registry/health', methods=['GET'])
    def get_species_registry_health():
        """Registry rollout health metrics."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            return species_registry_health(), 200
        except Exception as e:
            app.logger.exception('Species registry health failed: %s', e)
            return {'error': str(e)}, 500

    _start_system_metrics_sampler(app)
