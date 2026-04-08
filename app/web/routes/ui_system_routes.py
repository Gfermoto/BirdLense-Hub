"""Админские и служебные маршруты ``/api/ui/system/*``: БД, ретеншн, виды, конфиг, отчёты."""
import os
import re
import threading
import sqlite3
import tempfile
import json
import io
import csv
import yaml
from collections import deque
from datetime import datetime, timezone, timedelta
from flask import request, Response, send_file, jsonify, after_this_request
import shutil
import subprocess
import sys
from pathlib import Path
import util as util_mod
from models import (
    ActivityLog, db, Video, Species, VideoSpecies, SpeciesVisit,
    SystemResourceSample,
)
from sqlalchemy import delete, exists, func, select
from services.retention_service import run_retention, _delete_video_row_cascade
from services.species_registry_service import (
    catalog_cards_coverage_snapshot,
    repair_catalog_cards,
    resolve_species_name,
)
from services.heimdall_service import probe_heimdall
from services.species_visit_maintenance_service import (
    apply_clean_orphaned_visits,
    apply_realign_visit_times,
    apply_split_large_gap_visits,
    preview_clean_orphaned_visits,
    preview_realign_visit_times,
    preview_split_large_gap_visits,
)
from routes.ui_overview_timeline_routes import fetch_review_queue_items
from services.species_merge_service import merge_species_into
from app_config.app_config import app_config
from auth import admin_track_regen_access
from util import settings_check_access, recordings_dir, metrics_bearer_denied
from services.cache import cache_get, cache_set
from services.http_response_cache import bust_system_response_caches, bust_response_caches
from services.telegram_proxy_service import (
    refresh_telegram_proxy as refresh_telegram_proxy_service,
)
from services.track_regen_service import (
    derive_track_regen_species_scope as _derive_track_regen_species_scope,
    remap_detection_to_local_scope as _remap_detection_to_local_scope,
    run_track_regen_with_precise_fallback as _run_track_regen_with_precise_fallback,
    summarize_track_regen_detections as _summarize_track_regen_detections,
)
from services.fusion_training_service import (
    latest_fusion_export_path as _latest_fusion_export_path,
    repo_root as _repo_root,
    run_fusion_eval_job as _run_fusion_eval_job,
    run_fusion_export_job as _run_fusion_export_job,
)
from data_paths import data_dir, resolve_recording_video_file
from services.activity_notify_insights_service import (
    ingest_gate_reason_counts_24h as _ingest_gate_reason_counts_24h,
    notify_delivery_24h as _notify_delivery_24h,
    notify_fallback_by_reason_24h as _notify_fallback_by_reason_24h,
    notify_preview_by_source_24h as _notify_preview_by_source_24h,
    notify_preview_generated_by_source_24h as _notify_preview_generated_by_source_24h,
    notify_suppressed_reason_counts_24h as _notify_suppressed_reason_counts_24h,
)
from services.broken_videos_inventory_service import (
    broken_video_row_payload as _broken_video_row_payload,
    broken_video_row_reason as _broken_video_row_reason,
    scan_broken_videos_inventory as _scan_broken_videos_inventory,
    video_row_has_no_species as _video_row_has_no_species,
    videos_with_species_exist_clause as _videos_with_species_exist_clause,
)
from services.legacy_import_cleanup_service import (
    cleanup_legacy_import_placeholders as _cleanup_legacy_import_placeholders,
)
from services.ml_health_stats_service import ml_health_snapshot as _ml_health_snapshot
from services.ml_lineage_service import (
    current_model_lineage_snapshot as _current_model_lineage_snapshot,
)
from services.prometheus_metrics_service import (
    prometheus_metrics_body as _prometheus_metrics_body,
)
from services.sqlite_admin_service import (
    backup_sqlite_to_file as _sqlite_backup_to_file,
    replace_live_sqlite_db as _sqlite_replace_live_db,
    validate_sqlite_file as _sqlite_validate_file,
)
from services.system_live_metrics_service import (
    collect_live_system_metrics as _collect_live_system_metrics,
)
from services.visitor_stats_service import (
    browser_hash as _browser_hash,
    collect_visitor_stats as _collect_visitor_stats,
    device_class_from_user_agent as _device_class_from_user_agent,
    downsample_evenly as _downsample_evenly,
)

# Last spectrogram regeneration result (for status polling)
_regenerate_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_regenerate_tracks_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_regenerate_lock = threading.Lock()
_regenerate_tracks_lock = threading.Lock()
_species_metadata_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_species_metadata_lock = threading.Lock()
_catalog_cards_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_catalog_cards_lock = threading.Lock()
_catalog_cards_next_run_ts = 0.0
_fusion_export_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_fusion_export_lock = threading.Lock()
_fusion_eval_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_fusion_eval_lock = threading.Lock()
_telegram_proxy_refresh_status = {'status': 'idle', 'result': None, 'error': None, 'progress': None}
_telegram_proxy_refresh_lock = threading.Lock()


LOG_LINES_DEFAULT = 200
LOG_LINES_MAX = 500
DEPRECATED_USER_CONFIG_KEYS = (
    'notifications.enabled',
    'notifications.excluded_species',
    'notifications.rate_limit_per_minute',
    'processor.detection_device',
    'processor.detection_frame_interval',
    'weather.ha_token',
    'weather.ha_url',
)

TERMINAL_CONFIG_MAP_KEYS = {
    'detection.species_mapping',
    'ebird.species_mapping',
    'processor.species_confidence_overrides',
}

IGNORED_CONFIG_AUDIT_KEYS = {
    'camera',
    'secrets.zip',
    # Legacy HA connection (читается как fallback); см. homeassistant.*
    'weather.ha_token',
    'weather.ha_url',
}


def _env_bounded_int(name: str, default: int, *, min_v: int, max_v: int) -> int:
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    try:
        v = int(raw)
    except ValueError:
        return default
    return max(min_v, min(max_v, v))


SYSTEM_METRICS_SAMPLE_INTERVAL_SEC = _env_bounded_int(
    'BIRDLENSE_SYSTEM_METRICS_INTERVAL_SEC', 30, min_v=10, max_v=600,
)
SYSTEM_METRICS_RETENTION_HOURS = _env_bounded_int(
    'BIRDLENSE_SYSTEM_METRICS_RETENTION_HOURS', 72, min_v=6, max_v=720,
)
SYSTEM_METRICS_HISTORY_MAX_HOURS = 168
SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP = 2000
SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS = 500
CATALOG_REPAIR_AUTORUN_ENABLED = os.environ.get(
    'BIRDLENSE_CATALOG_REPAIR_AUTORUN',
    '1',
).strip().lower() in ('1', 'true', 'yes')
CATALOG_REPAIR_INTERVAL_MIN = _env_bounded_int(
    'BIRDLENSE_CATALOG_REPAIR_INTERVAL_MIN', 180, min_v=15, max_v=1440,
)
CATALOG_REPAIR_LIMIT = _env_bounded_int(
    'BIRDLENSE_CATALOG_REPAIR_LIMIT', 150, min_v=20, max_v=6000,
)

_CACHE_SYSTEM_METRICS_SEC = 2.5
_CACHE_SYSTEM_VISITORS_SEC = 25
_CACHE_SYSTEM_METRICS_HIST_SEC = 12
_CACHE_STORAGE_STATS_SEC = 45
_CACHE_SYSTEM_ACTIVITY_SEC = 50

_sampler_lock = threading.Lock()
_sampler_started = False


def _manual_conflict_with_detection(
    manual_rows,
    detection: dict,
    tracks_same_species,
) -> bool:
    """Drop auto detections that conflict with already manual-corrected rows."""
    det_name = (detection.get('species_name') or '').strip()
    det_track_id = detection.get('track_id')
    det_start = float(detection.get('start_time') or 0.0)
    det_end = float(detection.get('end_time') or 0.0)
    for row in manual_rows:
        manual_species = getattr(getattr(row, 'species', None), 'name', '') or ''
        if manual_species and tracks_same_species(manual_species, det_name):
            continue
        row_track_id = getattr(row, 'track_id', None)
        if row_track_id is not None and det_track_id is not None and row_track_id == det_track_id:
            return True
        overlap = min(float(getattr(row, 'end_time', 0.0) or 0.0), det_end) - max(
            float(getattr(row, 'start_time', 0.0) or 0.0),
            det_start,
        )
        if overlap > 0.3:
            return True
    return False


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
                _maybe_run_catalog_cards_repair(app)
        except Exception as e:
            app.logger.warning('system metrics sampler: %s', e)
            try:
                db.session.rollback()
            except Exception:
                pass
        time.sleep(SYSTEM_METRICS_SAMPLE_INTERVAL_SEC)


def _maybe_run_catalog_cards_repair(app) -> None:
    global _catalog_cards_next_run_ts
    if not CATALOG_REPAIR_AUTORUN_ENABLED:
        return
    now_ts = datetime.now(timezone.utc).timestamp()
    if _catalog_cards_next_run_ts and now_ts < _catalog_cards_next_run_ts:
        return
    with _catalog_cards_lock:
        if _catalog_cards_status.get('status') == 'running':
            return
        _catalog_cards_status.update({
            'status': 'running',
            'result': None,
            'error': None,
            'progress': {
                'auto': True,
                'limit': CATALOG_REPAIR_LIMIT,
                'coverage_before': catalog_cards_coverage_snapshot(app_config.get),
            },
        })
    try:
        result = repair_catalog_cards(
            app_config.get,
            dry_run=False,
            limit=CATALOG_REPAIR_LIMIT,
        )
        coverage_after = catalog_cards_coverage_snapshot(app_config.get)
        with _catalog_cards_lock:
            _catalog_cards_status.update({
                'status': 'done',
                'result': {**result, 'auto': True, 'coverage_after': coverage_after},
                'error': None,
            })
    except Exception as e:
        db.session.rollback()
        with _catalog_cards_lock:
            _catalog_cards_status.update({
                'status': 'error',
                'result': None,
                'error': str(e),
            })
    finally:
        _catalog_cards_next_run_ts = now_ts + (CATALOG_REPAIR_INTERVAL_MIN * 60)


def _catalog_cards_schedule_state() -> dict:
    now_ts = datetime.now(timezone.utc).timestamp()
    next_in = 0
    if _catalog_cards_next_run_ts > now_ts:
        next_in = int(_catalog_cards_next_run_ts - now_ts)
    return {
        'autorun_enabled': CATALOG_REPAIR_AUTORUN_ENABLED,
        'interval_min': CATALOG_REPAIR_INTERVAL_MIN,
        'limit': CATALOG_REPAIR_LIMIT,
        'next_run_in_sec': next_in,
    }


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


# Admin diagnostics: broken Video rows (DB без доступного файла) — безопасный cleanup только по явному подтверждению.
BROKEN_VIDEOS_DELETE_CONFIRMATION = 'delete_broken_video_rows'
BROKEN_VIDEOS_PURGE_CONFIRMATION = 'purge_all_broken_video_rows'
NO_SPECIES_VIDEOS_PURGE_CONFIRMATION = 'purge_videos_without_species'
REVIEW_ONLY_NOISE_SPECIES = ('Bird', 'Squirrel', 'Rodent')


def register_routes(app):
    """Зарегистрировать расширенный набор system API (кроме metrics — отдельный модуль)."""
    def _parse_video_ids(payload) -> list[int]:
        raw = (payload or {}).get('video_ids')
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError('video_ids must be an array of integers')
        out: list[int] = []
        for x in raw:
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if v > 0:
                out.append(v)
        return sorted(set(out))

    def _parse_unknown_ids(payload) -> list[int]:
        raw = (payload or {}).get('unknown_ids')
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError('unknown_ids must be an array of integers')
        out: list[int] = []
        for x in raw:
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if v > 0:
                out.append(v)
        return sorted(set(out))

    def _resolve_review_queue_bulk_plan(payload) -> dict:
        date = str((payload or {}).get('date') or '').strip()
        if not date:
            raise ValueError('date is required')
        time_of_day = str((payload or {}).get('time_of_day') or 'all').strip().lower()
        hour_raw = (payload or {}).get('hour')
        hour = None
        if hour_raw not in (None, ''):
            hour = int(hour_raw)
            if hour < 0 or hour > 23:
                raise ValueError('hour must be between 0 and 23')
        unknown_ids = _parse_unknown_ids(payload)
        if not unknown_ids:
            raise ValueError('unknown_ids is required')

        queue_items = fetch_review_queue_items(
            db.session,
            date_param=date,
            time_of_day=time_of_day,
            hour=hour,
            limit=500,
        )
        queue_by_id = {item['id']: item for item in queue_items}
        missing_unknown_ids = [uid for uid in unknown_ids if uid not in queue_by_id]
        if missing_unknown_ids:
            raise ValueError(
                'Selected review items are not present in the current review queue: '
                + ', '.join(str(uid) for uid in missing_unknown_ids)
            )
        selected_items = [queue_by_id[uid] for uid in unknown_ids]
        by_video: dict[int, dict] = {}
        for item in selected_items:
            bucket = by_video.setdefault(item['video_id'], {
                'video_id': item['video_id'],
                'unknown_ids': [],
                'species_names': set(),
                'review_reasons': set(),
            })
            bucket['unknown_ids'].append(item['id'])
            bucket['species_names'].add(item.get('species_name'))
            bucket['review_reasons'].add(item.get('review_reason'))

        video_ids = sorted(by_video)
        videos = db.session.query(Video).filter(Video.id.in_(video_ids)).all()
        videos_by_id = {video.id: video for video in videos}

        preview_videos = []
        missing_video_ids = []
        for video_id in video_ids:
            video = videos_by_id.get(video_id)
            bucket = by_video[video_id]
            if not video:
                missing_video_ids.append(video_id)
                continue
            full_path = util_mod.full_path_for_video(video.video_path) if video.video_path else None
            preview_videos.append({
                'video_id': video.id,
                'video_path': video.video_path,
                'start_time': video.start_time.astimezone(timezone.utc).isoformat() if video.start_time else None,
                'end_time': video.end_time.astimezone(timezone.utc).isoformat() if video.end_time else None,
                'has_video_path': bool(video.video_path),
                'file_exists': bool(full_path and os.path.isfile(full_path)),
                'recording_dir': os.path.dirname(video.video_path) if video.video_path else None,
                'unknown_count': len(bucket['unknown_ids']),
                'unknown_ids': sorted(bucket['unknown_ids']),
                'species_names': sorted(name for name in bucket['species_names'] if name),
                'review_reasons': sorted(reason for reason in bucket['review_reasons'] if reason),
            })

        return {
            'date': date,
            'time_of_day': time_of_day,
            'hour': hour,
            'confirmation_phrase': 'permanent_full',
            'unknown_ids': unknown_ids,
            'unknown_count': len(selected_items),
            'video_ids': video_ids,
            'video_count': len(preview_videos),
            'missing_video_ids': missing_video_ids,
            'videos_by_id': videos_by_id,
            'preview_videos': preview_videos,
        }

    def _parse_species_ids(payload) -> list[int]:
        raw = (payload or {}).get('species_ids')
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError('species_ids must be an array of integers')
        out: list[int] = []
        for x in raw:
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if v > 0:
                out.append(v)
        return sorted(set(out))

    def _flatten_keys(d: dict, prefix: str = '') -> set[str]:
        out = set()
        if not isinstance(d, dict):
            return out
        if prefix in TERMINAL_CONFIG_MAP_KEYS:
            return {prefix} if prefix else set()
        for k, v in d.items():
            p = f'{prefix}.{k}' if prefix else str(k)
            out.add(p)
            if isinstance(v, dict):
                out |= _flatten_keys(v, p)
        return out

    def _safe_get_user_config_dict() -> dict:
        try:
            with open(app_config.user_config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _sqlite_db_path() -> str | None:
        uri = str(db.engine.url)
        if not uri.startswith('sqlite:///'):
            return None
        return db.engine.url.database

    from routes.ui_system_metrics_routes import register_ui_system_metrics_routes
    register_ui_system_metrics_routes(app)

    @app.route('/api/ui/system/config-audit', methods=['GET'])
    def system_config_audit():
        if not settings_check_access():
            return {'error': 'Unauthorized'}, 401
        user_cfg = _safe_get_user_config_dict()
        default_only = {}
        try:
            with open(app_config.default_config_file, 'r', encoding='utf-8') as f:
                default_only = yaml.safe_load(f) or {}
        except Exception:
            pass
        user_keys = _flatten_keys(user_cfg)
        default_keys = _flatten_keys(default_only)
        unknown_keys = sorted([
            k for k in user_keys
            if k not in default_keys
            and k not in IGNORED_CONFIG_AUDIT_KEYS
            and not k.startswith('camera.')
        ])
        deprecated_present = sorted([k for k in DEPRECATED_USER_CONFIG_KEYS if k in user_keys])

        notif = app_config.get('notifications', {}) or {}
        gallery_enabled = bool(app_config.get('gallery.enabled'))
        gallery_url = (app_config.get('gallery.upload_url') or '').strip()
        # Gray/Grey harmonization now lives in detection.species_mapping; check there.
        # Also accept old ebird.species_mapping for backwards compat.
        detection_map = app_config.get('detection.species_mapping') or {}
        ebird_map = app_config.get('ebird.species_mapping') or {}
        combined_map = {**detection_map, **ebird_map}
        gray_pairs = {
            'Gray-headed Woodpecker': combined_map.get('Gray-headed Woodpecker'),
            'Great Gray Shrike': combined_map.get('Great Gray Shrike'),
        }
        gray_to_grey_ok = (
            gray_pairs.get('Gray-headed Woodpecker') == 'Grey-headed Woodpecker'
            and gray_pairs.get('Great Gray Shrike') == 'Great Grey Shrike'
        )
        return {
            'deprecated_keys_present': deprecated_present,
            'unknown_keys': unknown_keys,
            'telegram': {
                'proxy_type': (notif.get('telegram_proxy_type') or 'none'),
                'send_photo': bool(notif.get('send_photo')),
            },
            'gallery': {
                'enabled': gallery_enabled,
                'upload_url': gallery_url or None,
                'min_confidence': app_config.get('gallery.min_confidence'),
            },
            'mapping': {
                'gray_to_grey_ok': gray_to_grey_ok,
                'pairs': gray_pairs,
            },
            'heimdall': {
                'url': (app_config.get('general.heimdall_url') or '').strip() or None,
                'configured': bool((app_config.get('general.heimdall_url') or '').strip()),
                'probe': probe_heimdall((app_config.get('general.heimdall_url') or '').strip()),
            },
        }

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
        ack = f'system_activity:{month}'
        hit, ac = cache_get(ack)
        if hit:
            return ac
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

        out = [{
            'date': day,
            # convert to hours
            'totalUptime': round(duration / 3600, 1) if duration else 0
        } for day, duration in activities]
        cache_set(ack, out, _CACHE_SYSTEM_ACTIVITY_SEC)
        return out

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

    def _recording_days_with_files():
        days = set()
        rec_dir = recordings_dir()
        if not os.path.exists(rec_dir):
            return days
        try:
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
                        file_count, _ = get_day_storage_info(day_path)
                        if file_count > 0:
                            days.add(f'{year}-{month}-{day}')
        except Exception as e:
            app.logger.error(f'Error scanning recording days: {e}')
        return days

    def _get_tree_storage_info(dir_path):
        total_size = 0
        total_files = 0
        for root, _, files in os.walk(dir_path):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    total_size += os.path.getsize(file_path)
                    total_files += 1
                except OSError as e:
                    app.logger.error(f'Error getting size for {file_path}: {e}')
        return total_files, total_size

    @app.route('/api/ui/storage/stats', methods=['GET'])
    def get_storage_stats():
        sck = 'storage_stats:v1'
        hit, sc = cache_get(sck)
        if hit:
            return sc, 200
        if not os.path.exists(recordings_dir()):
            cache_set(sck, [], 30)
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

        cache_set(sck, stats, _CACHE_STORAGE_STATS_SEC)
        return stats, 200

    @app.route('/api/ui/storage/nearest-recording-day', methods=['GET'])
    def get_nearest_recording_day():
        raw_date = (request.args.get('date') or '').strip()
        direction = (request.args.get('direction') or 'next').strip().lower()
        if not raw_date:
            return {'error': 'date is required'}, 400
        if direction not in ('prev', 'next'):
            return {'error': 'direction must be "prev" or "next"'}, 400
        try:
            pivot = datetime.strptime(raw_date, '%Y-%m-%d').date()
        except ValueError:
            return {'error': 'Invalid date format, use YYYY-MM-DD'}, 400

        day_values = sorted(_recording_days_with_files())
        if direction == 'prev':
            match = next((day for day in reversed(day_values) if day < pivot.isoformat()), None)
        else:
            match = next((day for day in day_values if day > pivot.isoformat()), None)
        return {
            'date': match,
            'direction': direction,
            'found': match is not None,
        }, 200

    @app.route('/api/ui/storage/purge', methods=['POST'])
    def purge_storage():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            data = request.json or {}
            date_str = (data.get('date') or '').strip()
            start_date_str = (data.get('start_date') or '').strip()
            end_date_str = (data.get('end_date') or '').strip()

            range_mode = bool(start_date_str or end_date_str)
            purge_date: datetime | None = None
            range_start: datetime | None = None
            range_end: datetime | None = None

            if range_mode:
                if not start_date_str or not end_date_str:
                    return {'error': 'start_date and end_date are required together'}, 400
                try:
                    range_start = datetime.strptime(start_date_str, '%Y-%m-%d')
                    range_end = datetime.strptime(end_date_str, '%Y-%m-%d')
                except ValueError:
                    return {'error': 'Invalid date format, use YYYY-MM-DD'}, 400
                if range_start > range_end:
                    return {'error': 'start_date must be on or before end_date'}, 400
                max_span_days = 366 * 5
                if (range_end - range_start).days > max_span_days:
                    return {'error': f'Date range too large (max {max_span_days} days)'}, 400
            elif date_str:
                try:
                    purge_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    return {'error': 'Invalid date format, use YYYY-MM-DD'}, 400
            else:
                return {'error': 'Provide date or both start_date and end_date'}, 400

            deleted_count = 0
            deleted_size = 0
            rec_dir = recordings_dir()
            app_base = os.path.dirname(os.path.dirname(rec_dir))

            if range_mode:
                assert range_start is not None and range_end is not None
                range_end_exclusive = range_end + timedelta(days=1)
                videos = (
                    Video.query
                    .filter(
                        Video.start_time >= range_start,
                        Video.start_time < range_end_exclusive,
                    )
                    .order_by(Video.start_time.asc())
                    .all()
                )
            else:
                assert purge_date is not None
                purge_cutoff = purge_date + timedelta(days=1)
                videos = (
                    Video.query
                    .filter(Video.start_time < purge_cutoff)
                    .order_by(Video.start_time.asc())
                    .all()
                )

            video_dirs_to_delete = set()
            for video in videos:
                rel_dir = os.path.dirname(video.video_path or '')
                if rel_dir:
                    video_dirs_to_delete.add(os.path.join(app_base, rel_dir))
                _delete_video_row_cascade(video)
            db.session.commit()

            for dir_path in sorted(video_dirs_to_delete):
                if not os.path.isdir(dir_path):
                    continue
                count, size = _get_tree_storage_info(dir_path)
                deleted_count += count
                deleted_size += size
                shutil.rmtree(dir_path)

            # Walk the recordings tree to remove stray day directories that no longer have DB rows.
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

                        try:
                            dir_date = datetime.strptime(
                                f"{year}-{month}-{day}", '%Y-%m-%d')
                        except ValueError:
                            continue

                        if range_mode:
                            assert range_start is not None and range_end is not None
                            if dir_date < range_start or dir_date > range_end:
                                continue
                        else:
                            assert purge_date is not None
                            if dir_date > purge_date:
                                continue

                        count, size = get_day_storage_info(day_path)
                        deleted_count += count
                        deleted_size += size
                        shutil.rmtree(day_path)

                    if os.path.isdir(month_path) and not os.listdir(month_path):
                        os.rmdir(month_path)

                if os.path.isdir(year_path) and not os.listdir(year_path):
                    os.rmdir(year_path)

            bust_system_response_caches()
            return {
                'message': f'Successfully deleted {deleted_count} files',
                'deletedCount': deleted_count,
                'deletedSize': deleted_size
            }, 200

        except Exception as e:
            db.session.rollback()
            app.logger.exception('Purge storage failed')
            return {'error': 'Failed to purge storage'}, 500

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
                row = _broken_video_row_payload(video)
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
            video_ids = _parse_video_ids(payload)
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
                row = _broken_video_row_payload(v)
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
            video_ids = _parse_video_ids(payload)
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
                if _broken_video_row_payload(by_id[vid]) is None:
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
                count, size = _get_tree_storage_info(dir_path)
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
                inv = _scan_broken_videos_inventory(
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

            inv = _scan_broken_videos_inventory(
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
                if _broken_video_row_payload(by_id[vid]) is None:
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
                count, size = _get_tree_storage_info(dir_path)
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

            has_species = _videos_with_species_exist_clause()
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
                if not _video_row_has_no_species(v.id):
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
                count, size = _get_tree_storage_info(dir_path)
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
            br, _ = _broken_video_row_reason(v.video_path)
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

    @app.route('/api/ui/system/review-queue/delete-preview', methods=['POST'])
    def preview_review_queue_delete():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            plan = _resolve_review_queue_bulk_plan(payload)
            return {
                'confirmation_phrase': plan['confirmation_phrase'],
                'date': plan['date'],
                'time_of_day': plan['time_of_day'],
                'hour': plan['hour'],
                'unknown_count': plan['unknown_count'],
                'video_count': plan['video_count'],
                'unknown_ids': plan['unknown_ids'],
                'video_ids': plan['video_ids'],
                'missing_video_ids': plan['missing_video_ids'],
                'videos': plan['preview_videos'],
            }, 200
        except ValueError as exc:
            return {'error': str(exc)}, 400
        except Exception as e:
            app.logger.exception('Review queue delete preview failed: %s', e)
            return {'error': 'Failed to build review queue delete preview'}, 500

    @app.route('/api/ui/system/review-queue/delete', methods=['POST'])
    def delete_review_queue_videos():
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            plan = _resolve_review_queue_bulk_plan(payload)
            confirm_text = str((payload or {}).get('confirm_text') or '').strip()
            if confirm_text != plan['confirmation_phrase']:
                return {
                    'error': f'Confirmation text must be "{plan["confirmation_phrase"]}"',
                }, 400

            deleted_video_ids = []
            deleted_dirs = set()
            deleted_files = 0
            deleted_size = 0
            for video_id in plan['video_ids']:
                video = plan['videos_by_id'].get(video_id)
                if not video:
                    continue
                full_path = util_mod.full_path_for_video(video.video_path) if video.video_path else None
                if full_path and os.path.isdir(os.path.dirname(full_path)):
                    deleted_dirs.add(os.path.dirname(full_path))
                _delete_video_row_cascade(video)
                deleted_video_ids.append(video_id)

            db.session.commit()

            for dir_path in sorted(deleted_dirs):
                if not os.path.isdir(dir_path):
                    continue
                count, size = _get_tree_storage_info(dir_path)
                deleted_files += count
                deleted_size += size
                shutil.rmtree(dir_path)

            bust_response_caches()
            bust_system_response_caches()
            return {
                'message': f'Deleted {len(deleted_video_ids)} review-queue videos',
                'deletedCount': len(deleted_video_ids),
                'deletedVideoIds': deleted_video_ids,
                'deletedDirs': len(deleted_dirs),
                'deletedFiles': deleted_files,
                'deletedSize': deleted_size,
                'confirmation_phrase': plan['confirmation_phrase'],
            }, 200
        except ValueError as exc:
            db.session.rollback()
            return {'error': str(exc)}, 400
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Review queue delete failed: %s', e)
            return {'error': 'Failed to delete review queue videos'}, 500

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
        tmp_dir = tempfile.mkdtemp(prefix='birdlense-db-backup-')
        snapshot_path = os.path.join(tmp_dir, filename)
        try:
            _sqlite_backup_to_file(db_path, snapshot_path)
            _sqlite_validate_file(snapshot_path)
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            app.logger.exception('DB backup failed')
            return {'error': 'Failed to create DB backup snapshot'}, 500

        @after_this_request
        def _cleanup_snapshot(response):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return response

        return send_file(
            snapshot_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream',
        )

    @app.route('/api/ui/system/db/restore', methods=['POST'])
    def restore_database():
        """Restore SQLite DB from uploaded .db file; keep pre-restore backup."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        upload = request.files.get('file')
        if not upload:
            return {'error': 'file is required (multipart/form-data)'}, 400
        db_path = _sqlite_db_path()
        if not db_path:
            return {'error': 'DB restore is supported only for SQLite'}, 400
        if not os.path.isfile(db_path):
            return {'error': 'Database file not found'}, 404

        tmp_dir = tempfile.mkdtemp(prefix='birdlense-db-restore-')
        uploaded_path = os.path.join(tmp_dir, 'uploaded.db')
        restored_path = os.path.join(tmp_dir, 'restored.db')
        backup_path = ''
        try:
            upload.save(uploaded_path)
            if not os.path.isfile(uploaded_path) or os.path.getsize(uploaded_path) == 0:
                return {'error': 'Uploaded file is empty'}, 400

            try:
                _sqlite_validate_file(uploaded_path)
            except sqlite3.DatabaseError:
                return {'error': 'Uploaded SQLite file failed integrity_check'}, 400

            db.session.remove()
            db.engine.dispose()

            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')
            backup_path = f'{db_path}.pre_restore_{ts}.bak'
            _sqlite_backup_to_file(db_path, backup_path)
            _sqlite_backup_to_file(uploaded_path, restored_path)
            _sqlite_validate_file(restored_path)
            _sqlite_replace_live_db(db_path, restored_path)
            bust_system_response_caches()

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
            bust_system_response_caches()
            return {
                'message': f'Deleted {count} recordings',
                'deletedCount': count,
                'deletedSize': size,
            }, 200
        except Exception as e:
            app.logger.exception('Retention failed')
            return {'error': 'Failed to run retention'}, 500

    def _run_regenerate_spectrograms(
        force: bool,
        start_date: str | None,
        end_date: str | None,
        video_ids: list[int] | None = None,
    ):
        """Background task: regenerate spectrograms. Uses own app context and db session.

        If ``video_ids`` is set, only those rows are processed (always overwrite existing file).
        """
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
                if video_ids:
                    ids = sorted({int(x) for x in video_ids if x is not None})
                    query = query.filter(Video.id.in_(ids))
                elif not force:
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
            args=(force, start_date, end_date, None),
            daemon=True,
        )
        t.start()
        return {
            'message': 'Regeneration started in background.',
            'started': True,
        }, 202

    @app.route('/api/ui/videos/<int:video_id>/regenerate-spectrogram', methods=['POST'])
    def regenerate_spectrogram_single_video(video_id):
        """Перегенерация спектрограммы для одной записи (админ при двухуровневом доступе)."""
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        video = db.session.get(Video, video_id)
        if not video:
            return {'error': 'Video not found'}, 404
        with _regenerate_lock:
            if _regenerate_status['status'] == 'running':
                return {
                    'error': 'Regeneration already in progress',
                    'status': _regenerate_status,
                }, 409
        t = threading.Thread(
            target=_run_regenerate_spectrograms,
            args=(True, None, None, [video_id]),
            daemon=True,
        )
        t.start()
        return {
            'message': 'Spectrogram regeneration started for this video.',
            'started': True,
            'video_id': video_id,
        }, 202

    @app.route('/api/ui/system/regenerate-spectrograms/status', methods=['GET'])
    def regenerate_spectrograms_status():
        """Return last regeneration result: {status, result: {generated, failed, skipped}, error}."""
        return _regenerate_status, 200

    def _run_regenerate_tracks(
        force: bool,
        start_date: str | None,
        end_date: str | None,
        frame_step_override: int | None = None,
        video_ids: list[int] | None = None,
        species_ids: list[int] | None = None,
    ):
        """Background: run YOLO+ByteTrack on old videos, replace VideoSpecies with tracks.
        start_date, end_date: YYYY-MM-DD — период. None = все.
        species_ids: если задан — только видео, где есть детекция хотя бы одного из видов.
        """
        global _regenerate_tracks_status
        _regenerate_tracks_status = {
            'status': 'running', 'result': None, 'error': None,
            'progress': {
                'processed': 0,
                'total': 0,
                'generated': 0,
                'failed': 0,
                'skipped': 0,
                'current_video': None,
            },
        }
        try:
            with app.app_context():
                import sys
                from datetime import datetime, timezone, timedelta
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'processor', 'src'))
                from track_regenerator import (
                    build_detection_pipeline,
                    process_video_for_tracks,
                )
                from detection_fusion import build_fused_video_detections
                from services.visit_processor import VisitProcessor

                match_live = bool(
                    app_config.get('processor.track_regen_match_live_pipeline', False),
                )
                if match_live:
                    try:
                        lores_px = int(
                            app_config.get('processor.inference_lores_px') or 640,
                        )
                    except (TypeError, ValueError):
                        lores_px = 640
                    lores_px = max(320, min(lores_px, 960))
                    lores_size = (lores_px, lores_px)
                    frame_step = 1
                else:
                    lores_px = int(app_config.get('processor.track_regen_lores_px') or 640)
                    lores_px = max(320, min(lores_px, 960))
                    lores_size = (lores_px, lores_px)
                    frame_step = int(
                        frame_step_override
                        or app_config.get('processor.track_regen_frame_step')
                        or 1
                    )
                    frame_step = max(1, min(frame_step, 30))
                regen_strategy = (
                    app_config.get('processor.track_regen_detection_strategy')
                    or app_config.get('processor.detection_strategy')
                    or 'two_stage'
                )
                max_runtime_sec = int(
                    app_config.get('processor.track_regen_video_timeout_sec') or 300
                )
                dt_start = None
                dt_end = None
                species_ids_f = sorted(set(species_ids or []))
                target_video_ids = sorted(set(video_ids or []))
                regen_params = {
                    'frame_step': frame_step,
                    'lores_px': lores_px,
                    'detection_strategy': str(regen_strategy).strip(),
                    'max_runtime_sec': max_runtime_sec,
                }
                if species_ids_f:
                    regen_params['species_ids'] = species_ids_f
                    regen_params['species_partial_regen'] = True
                regen_params['ignore_regional_species'] = bool(
                    app_config.get('processor.track_regen_ignore_regional_species', True)
                )
                regen_params['match_live_pipeline'] = match_live
                _regenerate_tracks_status['progress']['regen_params'] = regen_params

                # Явные video_ids (один ролик из UI): не фильтровать по пустым frames.
                # Иначе ролик с frames='[]', только audio-строками или «левыми» frames
                # не попадал в join-выборку — пользователь видел «перегенерация ничего не сделала».
                if target_video_ids:
                    q = Video.query.filter(Video.id.in_(target_video_ids))
                elif force:
                    q = Video.query
                elif species_ids_f:
                    # Выбраны виды (напр. Rodent): брать все записи с этими детекциями,
                    # иначе при уже заполненных frames ролик не попадал бы в выборку.
                    q = (
                        Video.query.join(VideoSpecies)
                        .filter(VideoSpecies.species_id.in_(species_ids_f))
                        .distinct()
                    )
                else:
                    from sqlalchemy import or_
                    q = Video.query.join(VideoSpecies).filter(
                        or_(
                            VideoSpecies.frames.is_(None),
                            VideoSpecies.frames == '',
                            VideoSpecies.frames == '[]',
                        )
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

                if species_ids_f and force:
                    vid_subq = (
                        select(VideoSpecies.video_id)
                        .where(VideoSpecies.species_id.in_(species_ids_f))
                        .distinct()
                    )
                    q = q.filter(Video.id.in_(vid_subq))

                videos = q.order_by(Video.start_time.asc()).all()
                total = len(videos)
                _regenerate_tracks_status['progress']['total'] = total
                if total == 0 and target_video_ids:
                    app.logger.warning(
                        'Track regen: no videos for explicit ids %s (missing or filtered out)',
                        target_video_ids,
                    )
                if total == 0 and species_ids_f:
                    app.logger.info(
                        'Track regen: empty queue (species_ids=%s, start_date=%s, end_date=%s, force=%s)',
                        species_ids_f,
                        start_date,
                        end_date,
                        force,
                    )

                generated = 0
                failed = 0
                skipped = 0
                frames_updated = 0  # videos with manually_corrected: only frames updated
                single_video_regen_summary: dict | None = None
                precise_candidates: list[dict] = []
                regen_species_scope = None
                regen_species_scope_lc: set[str] = set()
                if (
                    app_config.get('processor.track_regen_ignore_regional_species', True)
                    and not match_live
                ):
                    regen_species_scope = _derive_track_regen_species_scope(dt_start)
                    if regen_species_scope:
                        regen_species_scope_lc = {
                            str(name).strip().lower()
                            for name in regen_species_scope
                            if str(name).strip()
                        }
                        regen_params['local_species_scope_count'] = len(regen_species_scope)

                visit_timeout = int(app_config.get('detection.dedup_window_seconds') or 60)
                visit_processor = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
                # Reuse YOLO+tracker pipeline across all videos in the batch.
                frame_processor, decision_maker = build_detection_pipeline(
                    app_config,
                    strategy_override=regen_strategy,
                    for_track_regen=True,
                )
                precise_lores_px = max(lores_px, 640)
                precise_frame_step = min(frame_step, 2)
                precise_strategy = (
                    app_config.get('processor.track_regen_precise_detection_strategy')
                    or app_config.get('processor.track_regen_detection_strategy')
                    or
                    app_config.get('processor.detection_strategy')
                    or regen_strategy
                    or 'two_stage'
                )
                precise_max_runtime_sec = min(
                    max_runtime_sec,
                    int(app_config.get('processor.track_regen_precise_timeout_sec') or 420),
                )
                precise_min_center_dist = float(
                    app_config.get('processor.track_regen_precise_min_center_dist') or 0.02
                )
                precise_enabled = any((
                    precise_lores_px != lores_px,
                    precise_frame_step != frame_step,
                    str(precise_strategy).strip() != str(regen_strategy).strip(),
                    precise_max_runtime_sec != max_runtime_sec,
                    app_config.get('processor.track_regen_precise_min_center_dist') is not None,
                ))
                precise_params = {
                    'frame_step': precise_frame_step,
                    'lores_px': precise_lores_px,
                    'detection_strategy': str(precise_strategy).strip(),
                    'max_runtime_sec': precise_max_runtime_sec,
                    'min_center_dist': precise_min_center_dist,
                } if precise_enabled else None
                if precise_params:
                    regen_params['precise_fallback'] = precise_params
                precise_pipeline = None
                species_scope = set(species_ids_f) if species_ids_f else None
                scope_catalog_species: list[Species] = []
                scope_names_lc: set[str] = set()
                scope_taxon_ids: set[int] = set()
                if species_scope:
                    for sid in species_ids_f:
                        sp = db.session.get(Species, sid)
                        if not sp:
                            continue
                        scope_catalog_species.append(sp)
                        if sp.name:
                            scope_names_lc.add(sp.name.strip().lower())
                        if sp.taxon_id is not None:
                            scope_taxon_ids.add(sp.taxon_id)
                species_name_to_id_cache: dict[str, int | None] = {}

                def _resolved_species_id_for_det(detection: dict) -> int | None:
                    name = (detection.get('species_name') or '').strip()
                    if not name:
                        return None
                    if name not in species_name_to_id_cache:
                        sp = visit_processor._get_or_create_species(name)
                        species_name_to_id_cache[name] = sp.id if sp else None
                    return species_name_to_id_cache[name]

                def _detection_in_species_scope(detection: dict) -> bool:
                    if not species_scope:
                        return True
                    sid = _resolved_species_id_for_det(detection)
                    if sid and sid in species_scope:
                        return True
                    name = (detection.get('species_name') or '').strip()
                    if not name:
                        return False
                    if name.lower() in scope_names_lc:
                        return True
                    res = resolve_species_name(name, source='ingest')
                    if res.found and res.taxon and res.taxon.id in scope_taxon_ids:
                        return True
                    return False

                def _remap_det_for_scope(detection: dict) -> dict:
                    if not species_scope:
                        return detection
                    sid = _resolved_species_id_for_det(detection)
                    if sid and sid in species_scope:
                        return detection
                    name = (detection.get('species_name') or '').strip()
                    if not name:
                        return detection
                    nlc = name.lower()
                    if nlc in scope_names_lc:
                        for sp in scope_catalog_species:
                            if sp.name and sp.name.strip().lower() == nlc:
                                return {**detection, 'species_name': sp.name}
                    res = resolve_species_name(name, source='ingest')
                    if res.found and res.taxon:
                        tid = res.taxon.id
                        for sp in scope_catalog_species:
                            if sp.taxon_id == tid:
                                return {**detection, 'species_name': sp.name}
                    return detection

                def _tracks_same_species(db_name: str, det_name: str) -> bool:
                    if not db_name or not det_name:
                        return False
                    if db_name.strip().lower() == det_name.strip().lower():
                        return True
                    ra = resolve_species_name(db_name.strip(), source='ingest')
                    rb = resolve_species_name(det_name.strip(), source='ingest')
                    if (
                        ra.found
                        and rb.found
                        and ra.taxon
                        and rb.taxon
                        and ra.taxon.id == rb.taxon.id
                    ):
                        return True
                    return False

                for video in videos:
                    species_name_to_id_cache.clear()
                    _regenerate_tracks_status['progress']['current_video'] = (
                        video.video_path or None
                    )
                    if not video.video_path:
                        skipped += 1
                        precise_candidates.append({
                            'video_id': video.id,
                            'video_path': None,
                            'reason': 'missing_video_path',
                        })
                        _regenerate_tracks_status['progress'].update(
                            processed=generated + failed + skipped,
                            generated=generated, failed=failed, skipped=skipped,
                        )
                        continue
                    full_video = resolve_recording_video_file(video.video_path)
                    if not full_video:
                        skipped += 1
                        precise_candidates.append({
                            'video_id': video.id,
                            'video_path': video.video_path,
                            'reason': 'video_file_missing',
                        })
                        _regenerate_tracks_status['progress'].update(
                            processed=generated + failed + skipped,
                            generated=generated, failed=failed, skipped=skipped,
                        )
                        continue

                    try:
                        fast_kwargs = {
                            'lores_size': lores_size,
                            'frame_processor': frame_processor,
                            'decision_maker': decision_maker,
                            'frame_step': frame_step,
                            'max_runtime_sec': max_runtime_sec,
                        }

                        def _precise_kwargs():
                            nonlocal precise_pipeline
                            if not precise_params:
                                return None
                            if precise_pipeline is None:
                                precise_scope_override = regen_species_scope
                                precise_pipeline = build_detection_pipeline(
                                    app_config,
                                    strategy_override=precise_strategy,
                                    for_track_regen=True,
                                    regional_species_override=precise_scope_override,
                                    min_center_dist_override=precise_min_center_dist,
                                )
                            precise_frame_processor, precise_decision_maker = precise_pipeline
                            return {
                                'lores_size': (precise_lores_px, precise_lores_px),
                                'frame_processor': precise_frame_processor,
                                'decision_maker': precise_decision_maker,
                                'frame_step': precise_frame_step,
                                'max_runtime_sec': precise_max_runtime_sec,
                            }

                        track_detections, precise_used = _run_track_regen_with_precise_fallback(
                            full_video,
                            process_video_for_tracks,
                            fast_kwargs,
                            _precise_kwargs if precise_enabled else None,
                        )
                        detections = build_fused_video_detections(
                            track_detections,
                            [],
                            start_time=video.start_time,
                            end_time=video.end_time,
                            app_config=app_config,
                        )
                        if (
                            not detections
                            and track_detections
                            and precise_enabled
                            and not precise_used
                        ):
                            precise_kwargs = _precise_kwargs()
                            if precise_kwargs:
                                track_detections = process_video_for_tracks(
                                    full_video,
                                    **precise_kwargs,
                                )
                                precise_used = True
                                detections = build_fused_video_detections(
                                    track_detections,
                                    [],
                                    start_time=video.start_time,
                                    end_time=video.end_time,
                                    app_config=app_config,
                                )
                                app.logger.info(
                                    'Track regen: post-fusion precise pass '
                                    '(video_id=%s path=%s)',
                                    video.id,
                                    video.video_path,
                                )
                        if regen_species_scope_lc:
                            detections = [
                                _remap_detection_to_local_scope(d, regen_species_scope_lc)
                                for d in detections
                            ]
                        if not detections:
                            reason = 'no_detections_after_precise_pass' if precise_used else 'no_detections_fast_run'
                            skipped += 1
                            precise_candidates.append({
                                'video_id': video.id,
                                'video_path': video.video_path,
                                'reason': reason,
                            })
                            _regenerate_tracks_status['progress'].update(
                                processed=generated + failed + skipped,
                                generated=generated, failed=failed, skipped=skipped,
                            )
                            continue
                        if precise_used:
                            app.logger.info(
                                'Track regen precise fallback recovered detections '
                                '(video_id=%s path=%s strategy=%s frame_step=%s lores_px=%s)',
                                video.id,
                                video.video_path,
                                precise_strategy,
                                precise_frame_step,
                                precise_lores_px,
                            )

                        scoped_detections: list[dict] | None = None
                        if species_scope:
                            scoped_detections = []
                            for d in detections:
                                if not _detection_in_species_scope(d):
                                    continue
                                scoped_detections.append(_remap_det_for_scope(d))
                            if not scoped_detections:
                                sample = [d.get('species_name') for d in detections[:8]]
                                app.logger.info(
                                    'Track regen: no detections match species scope '
                                    '(video_id=%s scope=%s sample_model_names=%s)',
                                    video.id,
                                    sorted(species_scope),
                                    sample,
                                )
                                skipped += 1
                                precise_candidates.append({
                                    'video_id': video.id,
                                    'video_path': video.video_path,
                                    'reason': 'no_detections_for_selected_species',
                                })
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
                            manuals_ordered = sorted(
                                (
                                    [vs for vs in manual_vs if vs.species_id in species_scope]
                                    if species_scope
                                    else manual_vs
                                ),
                                key=lambda x: x.start_time,
                            )
                            for vs in manuals_ordered:
                                best_idx = None
                                best_overlap = 0.0
                                vs_species_name = vs.species.name if vs.species else None
                                for i, d in enumerate(detections):
                                    if i in used_det_indices:
                                        continue
                                    # Только если вид совпадает — иначе присвоим кадр от другой птицы
                                    if vs_species_name and not _tracks_same_species(
                                        vs_species_name, d.get('species_name') or ''
                                    ):
                                        continue
                                    overlap = min(vs.end_time, d['end_time']) - max(vs.start_time, d['start_time'])
                                    if overlap > best_overlap and overlap > 0.3:
                                        best_overlap = overlap
                                        best_idx = i
                                if best_idx is not None and detections[best_idx].get('frames'):
                                    vs.frames = json.dumps(detections[best_idx]['frames'])
                                    used_det_indices.add(best_idx)
                            db.session.flush()
                            unmatched = [d for i, d in enumerate(detections) if i not in used_det_indices]
                            unmatched = [
                                d for d in unmatched
                                if not _manual_conflict_with_detection(
                                    manuals_ordered, d, _tracks_same_species
                                )
                            ]
                            if species_scope:
                                unmatched = [
                                    _remap_det_for_scope(d)
                                    for d in unmatched
                                    if _detection_in_species_scope(d)
                                ]
                            if species_scope:
                                ids_touched = {
                                    _resolved_species_id_for_det(d)
                                    for d in unmatched
                                }
                                ids_touched &= species_scope
                                to_delete = [
                                    vs for vs in video.video_species
                                    if not vs.manually_corrected
                                    and vs.species_id in ids_touched
                                ]
                            else:
                                to_delete = [
                                    vs for vs in video.video_species
                                    if not vs.manually_corrected
                                ]
                            for vs in to_delete:
                                db.session.delete(vs)
                            if unmatched:
                                visit_processor.process_detections(video, unmatched)
                            frames_updated += 1
                            if len(target_video_ids) == 1 and video.id == target_video_ids[0]:
                                single_video_regen_summary = _summarize_track_regen_detections(
                                    unmatched,
                                )
                            precise_candidates.append({
                                'video_id': video.id,
                                'video_path': video.video_path,
                                'reason': 'has_manual_corrections',
                            })
                        elif species_scope:
                            ids_touched = {
                                _resolved_species_id_for_det(d)
                                for d in scoped_detections
                            }
                            ids_touched &= species_scope
                            if ids_touched:
                                VideoSpecies.query.filter(
                                    VideoSpecies.video_id == video.id,
                                    VideoSpecies.species_id.in_(ids_touched),
                                    VideoSpecies.manually_corrected.is_(False),
                                ).delete(synchronize_session=False)
                            visit_processor.process_detections(video, scoped_detections)
                            generated += 1
                            if len(target_video_ids) == 1 and video.id == target_video_ids[0]:
                                single_video_regen_summary = _summarize_track_regen_detections(
                                    scoped_detections,
                                )
                        else:
                            VideoSpecies.query.filter_by(video_id=video.id).delete()
                            visit_processor.process_detections(video, detections)
                            generated += 1
                            if len(target_video_ids) == 1 and video.id == target_video_ids[0]:
                                single_video_regen_summary = _summarize_track_regen_detections(
                                    detections,
                                )
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        app.logger.exception(f'Track regen failed {video.video_path}: {e}')
                        failed += 1
                        precise_candidates.append({
                            'video_id': video.id,
                            'video_path': video.video_path,
                            'reason': 'processing_failed',
                        })

                    _regenerate_tracks_status['progress'].update(
                        processed=generated + failed + skipped,
                        generated=generated, failed=failed, skipped=skipped,
                    )

                app.logger.info(
                    f'Tracks: generated={generated}, frames_updated={frames_updated}, failed={failed}, skipped={skipped}'
                )
                if generated or frames_updated or precise_candidates:
                    bust_response_caches()
                result = {
                    'generated': generated,
                    'failed': failed,
                    'skipped': skipped,
                    'regen_params': regen_params,
                }
                if single_video_regen_summary is not None:
                    result['single_video_regen'] = single_video_regen_summary
                if frames_updated:
                    result['frames_updated'] = frames_updated
                if precise_candidates:
                    dedup = {}
                    for item in precise_candidates:
                        dedup[(item['video_id'], item['reason'])] = item
                    result['precise_rerun_candidates'] = list(dedup.values())[:500]
                    result['precise_rerun_candidate_count'] = len(dedup)
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

    @app.route('/api/ui/system/regenerate-tracks/status', methods=['GET'])
    def regenerate_tracks_status():
        """Return last track regeneration result."""
        return _regenerate_tracks_status, 200

    @app.route('/api/ui/videos/<int:video_id>/regenerate-tracks', methods=['POST'])
    def regenerate_tracks_single_video(video_id):
        """Перегенерация треков только для одной записи (админ при двухуровневом доступе)."""
        if not admin_track_regen_access():
            return {'error': 'Access denied'}, 403
        video = db.session.get(Video, video_id)
        if not video:
            return {'error': 'Video not found'}, 404
        data = request.json or {}
        force = bool(data.get('force', False))
        with _regenerate_tracks_lock:
            if _regenerate_tracks_status['status'] == 'running':
                return {
                    'error': 'Track regeneration already in progress',
                    'status': _regenerate_tracks_status,
                }, 409
        t = threading.Thread(
            target=_run_regenerate_tracks,
            args=(force, None, None, None, [video_id], []),
            daemon=True,
        )
        t.start()
        return {
            'message': 'Track regeneration started for this video.',
            'started': True,
            'video_id': video_id,
        }, 202

    @app.route('/api/ui/system/fusion/export', methods=['POST'])
    def fusion_export():
        """Export decision traces to CSV for fusion calibration/training."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _fusion_export_lock:
            if _fusion_export_status['status'] == 'running':
                return {'error': 'Fusion export already in progress', 'status': _fusion_export_status}, 409
            _fusion_export_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': None,
            })

        def _run():
            try:
                with app.app_context():
                    result = _run_fusion_export_job()
                with _fusion_export_lock:
                    _fusion_export_status.update({
                        'status': 'done',
                        'result': result,
                        'error': None,
                        'progress': None,
                    })
            except Exception as e:
                with _fusion_export_lock:
                    _fusion_export_status.update({
                        'status': 'error',
                        'result': None,
                        'error': str(e),
                        'progress': None,
                    })

        threading.Thread(target=_run, daemon=True).start()
        return {'message': 'Fusion export started', 'status': _fusion_export_status}, 202

    @app.route('/api/ui/system/fusion/export/status', methods=['GET'])
    def fusion_export_status():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _fusion_export_lock:
            return dict(_fusion_export_status), 200

    @app.route('/api/ui/system/fusion/export/download', methods=['GET'])
    def fusion_export_download():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        latest = _latest_fusion_export_path()
        if not latest or not latest.exists():
            return {'error': 'Fusion export not found'}, 404
        return send_file(
            latest,
            as_attachment=True,
            download_name=latest.name,
            mimetype='text/csv',
        )

    @app.route('/api/ui/system/fusion/eval', methods=['POST'])
    def fusion_eval():
        """Evaluate fusion calibration on a CSV export."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _fusion_eval_lock:
            if _fusion_eval_status['status'] == 'running':
                return {'error': 'Fusion eval already in progress', 'status': _fusion_eval_status}, 409
            _fusion_eval_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': None,
            })
        payload = request.get_json(silent=True) or {}

        def _run():
            try:
                with app.app_context():
                    result = _run_fusion_eval_job(
                        source_csv=payload.get('source_csv'),
                        model_path=payload.get('model_path'),
                        score_col=payload.get('score_col'),
                        label_col=payload.get('label_col', 'valid_track_label'),
                        slice_fields=list(payload.get('slice_fields') or []),
                    )
                with _fusion_eval_lock:
                    _fusion_eval_status.update({
                        'status': 'done',
                        'result': result,
                        'error': None,
                        'progress': None,
                    })
            except Exception as e:
                with _fusion_eval_lock:
                    _fusion_eval_status.update({
                        'status': 'error',
                        'result': None,
                        'error': str(e),
                        'progress': None,
                    })

        threading.Thread(target=_run, daemon=True).start()
        return {'message': 'Fusion eval started', 'status': _fusion_eval_status}, 202

    @app.route('/api/ui/system/fusion/eval/status', methods=['GET'])
    def fusion_eval_status():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _fusion_eval_lock:
            return dict(_fusion_eval_status), 200

    @app.route('/api/ui/system/telegram-proxy/refresh', methods=['POST'])
    def refresh_telegram_proxy():
        """Refresh Telegram SOCKS proxy using the backend service."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _telegram_proxy_refresh_lock:
            if _telegram_proxy_refresh_status['status'] == 'running':
                return {
                    'error': 'Telegram proxy refresh already in progress',
                    'status': _telegram_proxy_refresh_status,
                }, 409
            _telegram_proxy_refresh_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': None,
            })

        def _run():
            try:
                with app.app_context():
                    result = refresh_telegram_proxy_service()
                with _telegram_proxy_refresh_lock:
                    _telegram_proxy_refresh_status.update({
                        'status': 'done',
                        'result': result,
                        'error': None,
                        'progress': None,
                    })
            except Exception as e:
                with _telegram_proxy_refresh_lock:
                    _telegram_proxy_refresh_status.update({
                        'status': 'error',
                        'result': None,
                        'error': str(e),
                        'progress': None,
                    })

        threading.Thread(target=_run, daemon=True).start()
        return {'message': 'Telegram proxy refresh started', 'status': _telegram_proxy_refresh_status}, 202

    @app.route('/api/ui/system/telegram-proxy/refresh/status', methods=['GET'])
    def refresh_telegram_proxy_status():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _telegram_proxy_refresh_lock:
            return dict(_telegram_proxy_refresh_status), 200

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

        existing_paths = {
            v.video_path for v in db.session.query(Video.video_path).all()
        }
        imported = 0
        cleaned_legacy_placeholders = 0
        cleaned_legacy_visits = 0
        # YYYY/MM/DD/HHMMSS или YYYY/MM/DD/HH-MM-SS
        pattern = re.compile(
            r'^(\d{4})/(\d{2})/(\d{2})/(\d{2})[-:]?(\d{2})[-:]?(\d{2})$'
        )

        try:
            cleaned_legacy_placeholders, cleaned_legacy_visits = (
                _cleanup_legacy_import_placeholders()
            )
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
                            try:
                                if os.path.getsize(video_mp4) <= 0:
                                    continue
                            except OSError:
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
                                existing_paths.add(rel_path)
                                imported += 1
                            except Exception as e:
                                app.logger.warning(
                                    f'Import failed {rel_path}: {e}'
                                )
                                continue

            db.session.commit()
            bust_response_caches()
            bust_system_response_caches()

            # Auto-start spectrogram regeneration for newly imported videos (если не запущена)
            spectrogram_started = False
            if imported > 0:
                with _regenerate_lock:
                    if _regenerate_status['status'] != 'running':
                        t = threading.Thread(
                            target=_run_regenerate_spectrograms,
                            args=(False, None, None, None),
                            daemon=True,
                        )
                        t.start()
                        spectrogram_started = True

            message = f'Imported {imported} recordings'
            if cleaned_legacy_placeholders:
                message += (
                    f'; cleaned {cleaned_legacy_placeholders} legacy placeholders'
                )
            return {
                'imported': imported,
                'cleaned_legacy_placeholders': cleaned_legacy_placeholders,
                'cleaned_legacy_visits': cleaned_legacy_visits,
                'message': message,
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
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            if dry_run:
                return preview_clean_orphaned_visits(db.session), 200

            body = apply_clean_orphaned_visits(db.session)
            db.session.commit()
            bust_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Clean orphaned visits failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/realign-visit-times', methods=['POST'])
    def realign_visit_times():
        """Preview/apply SpeciesVisit time realignment from actual detection timestamps."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            if dry_run:
                return preview_realign_visit_times(db.session), 200

            body = apply_realign_visit_times(db.session)
            db.session.commit()
            bust_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Realign visit times failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/split-large-gap-visits', methods=['POST'])
    def split_large_gap_visits():
        """Preview/apply splitting of visits with large internal detection gaps."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            gap_seconds = int(app_config.get('detection.dedup_window_seconds') or 60)
            if dry_run:
                return preview_split_large_gap_visits(db.session, gap_seconds), 200

            body = apply_split_large_gap_visits(db.session, gap_seconds)
            db.session.commit()
            bust_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Split large-gap visits failed: %s', e)
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
                    if target.name != canonical:
                        target.name = canonical
                    merge_species_into(other.id, target.id)
                    details.append(f"{other.name} -> {canonical}")
                    merged += 1
            db.session.commit()
            bust_response_caches()
            return {'merged': merged, 'details': details, 'message': f'Merged {merged} duplicate species'}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Merge duplicate species failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-catalog/reconcile', methods=['POST'])
    def species_catalog_reconcile():
        """
        Привести каталог видов: слияние дубликатов по нормализованному имени;
        опционально перенос подозрительных (блоклист) и строк вне allowlist на «Unknown».

        body JSON:
          dry_run (default true),
          merge_normalized_duplicate_names (default true),
          reassign_suspects_to_unknown, delete_empty_suspects,
          reassign_off_allowlist_to_unknown, delete_empty_off_allowlist,
          duplicate_group_limit (default 500).

        Allowlist: species.catalog_allowlist_file → scripts/datasets/dump_classifier_allowlist.py
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            from services.species_catalog_allowlist_service import clear_allowlist_cache
            from services.species_catalog_reconcile_service import reconcile_species_catalog

            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            dup_limit = payload.get('duplicate_group_limit', 500)
            try:
                dup_limit = int(dup_limit)
            except (TypeError, ValueError):
                return {'error': 'duplicate_group_limit must be int'}, 400
            dup_limit = max(10, min(dup_limit, 5000))

            body = reconcile_species_catalog(
                dry_run=dry_run,
                merge_normalized_duplicate_names=bool(
                    payload.get('merge_normalized_duplicate_names', True),
                ),
                reassign_suspects_to_unknown=bool(
                    payload.get('reassign_suspects_to_unknown', False),
                ),
                reassign_off_allowlist_to_unknown=bool(
                    payload.get('reassign_off_allowlist_to_unknown', False),
                ),
                delete_empty_suspects=bool(payload.get('delete_empty_suspects', False)),
                delete_empty_off_allowlist=bool(
                    payload.get('delete_empty_off_allowlist', False),
                ),
                duplicate_group_limit=dup_limit,
                app_config_get=app_config.get,
            )
            if not dry_run:
                clear_allowlist_cache()
                bust_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Species catalog reconcile failed: %s', e)
            return {'error': str(e)}, 500

    from routes.ui_system_species_registry_routes import register_ui_system_species_registry_routes
    register_ui_system_species_registry_routes(app)

    _start_system_metrics_sampler(app)
