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
from services.species_merge_service import merge_species_into
from app_config.app_config import app_config
from auth import admin_track_regen_access
from util import settings_check_access, recordings_dir, metrics_bearer_denied
from services.cache import cache_get, cache_set
from services.http_response_cache import bust_system_response_caches, bust_response_caches
from services.track_regen_service import (
    derive_track_regen_species_scope as _derive_track_regen_species_scope,
    remap_detection_to_local_scope as _remap_detection_to_local_scope,
    run_track_regen_with_precise_fallback as _run_track_regen_with_precise_fallback,
    summarize_track_regen_detections as _summarize_track_regen_detections,
)
from services.fusion_training_service import repo_root as _repo_root
from data_paths import data_dir, resolve_recording_video_file
from services.activity_notify_insights_service import (
    ingest_gate_reason_counts_24h as _ingest_gate_reason_counts_24h,
    notify_delivery_24h as _notify_delivery_24h,
    notify_fallback_by_reason_24h as _notify_fallback_by_reason_24h,
    notify_preview_by_source_24h as _notify_preview_by_source_24h,
    notify_preview_generated_by_source_24h as _notify_preview_generated_by_source_24h,
    notify_suppressed_reason_counts_24h as _notify_suppressed_reason_counts_24h,
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
from services.storage_tree_utils import get_tree_storage_info
from services.visitor_stats_service import (
    browser_hash as _browser_hash,
    collect_visitor_stats as _collect_visitor_stats,
    device_class_from_user_agent as _device_class_from_user_agent,
    downsample_evenly as _downsample_evenly,
)
from services.system_metrics_constants import (
    SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS,
    SYSTEM_METRICS_HISTORY_MAX_HOURS,
    SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP,
    SYSTEM_METRICS_RETENTION_HOURS,
    SYSTEM_METRICS_SAMPLE_INTERVAL_SEC,
    _CACHE_STORAGE_STATS_SEC,
    _CACHE_SYSTEM_ACTIVITY_SEC,
    _CACHE_SYSTEM_METRICS_HIST_SEC,
    _CACHE_SYSTEM_METRICS_SEC,
    _CACHE_SYSTEM_VISITORS_SEC,
    env_bounded_int,
)

import routes.ui_system_jobs_state as job_state


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

CATALOG_REPAIR_AUTORUN_ENABLED = os.environ.get(
    'BIRDLENSE_CATALOG_REPAIR_AUTORUN',
    '1',
).strip().lower() in ('1', 'true', 'yes')
CATALOG_REPAIR_INTERVAL_MIN = env_bounded_int(
    'BIRDLENSE_CATALOG_REPAIR_INTERVAL_MIN', 180, min_v=15, max_v=1440,
)
CATALOG_REPAIR_LIMIT = env_bounded_int(
    'BIRDLENSE_CATALOG_REPAIR_LIMIT', 150, min_v=20, max_v=6000,
)



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
    if not CATALOG_REPAIR_AUTORUN_ENABLED:
        return
    now_ts = datetime.now(timezone.utc).timestamp()
    if job_state._catalog_cards_next_run_ts and now_ts < job_state._catalog_cards_next_run_ts:
        return
    with job_state._catalog_cards_lock:
        if job_state._catalog_cards_status.get('status') == 'running':
            return
        job_state._catalog_cards_status.update({
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
        with job_state._catalog_cards_lock:
            job_state._catalog_cards_status.update({
                'status': 'done',
                'result': {**result, 'auto': True, 'coverage_after': coverage_after},
                'error': None,
            })
    except Exception as e:
        db.session.rollback()
        with job_state._catalog_cards_lock:
            job_state._catalog_cards_status.update({
                'status': 'error',
                'result': None,
                'error': str(e),
            })
    finally:
        job_state._catalog_cards_next_run_ts = now_ts + (CATALOG_REPAIR_INTERVAL_MIN * 60)


def _catalog_cards_schedule_state() -> dict:
    now_ts = datetime.now(timezone.utc).timestamp()
    next_in = 0
    if job_state._catalog_cards_next_run_ts > now_ts:
        next_in = int(job_state._catalog_cards_next_run_ts - now_ts)
    return {
        'autorun_enabled': CATALOG_REPAIR_AUTORUN_ENABLED,
        'interval_min': CATALOG_REPAIR_INTERVAL_MIN,
        'limit': CATALOG_REPAIR_LIMIT,
        'next_run_in_sec': next_in,
    }


def _start_system_metrics_sampler(app):
    if os.environ.get('DISABLE_SYSTEM_METRICS_SAMPLER', '').strip().lower() in (
        '1', 'true', 'yes',
    ):
        return
    with job_state._sampler_lock:
        if job_state._sampler_started:
            return
        job_state._sampler_started = True
    threading.Thread(
        target=_system_metrics_sampler_worker,
        args=(app,),
        name='system-metrics-sampler',
        daemon=True,
    ).start()


def register_routes(app):
    """Зарегистрировать расширенный набор system API (кроме metrics — отдельный модуль)."""
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

    from routes.ui_system_metrics_routes import register_ui_system_metrics_routes
    register_ui_system_metrics_routes(app)
    from routes.ui_system_diagnostics_routes import register_ui_system_diagnostics_routes
    register_ui_system_diagnostics_routes(app)
    from routes.ui_system_review_queue_routes import register_ui_system_review_queue_routes
    register_ui_system_review_queue_routes(app)
    from routes.ui_system_storage_routes import register_ui_system_storage_routes
    register_ui_system_storage_routes(app)
    from routes.ui_system_db_routes import register_ui_system_db_routes
    register_ui_system_db_routes(app)
    from routes.ui_system_fusion_routes import register_ui_system_fusion_routes
    register_ui_system_fusion_routes(app)
    from routes.ui_system_maintenance_routes import register_ui_system_maintenance_routes
    register_ui_system_maintenance_routes(app)

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

    def _run_regenerate_spectrograms(
        force: bool,
        start_date: str | None,
        end_date: str | None,
        video_ids: list[int] | None = None,
    ):
        """Background task: regenerate spectrograms. Uses own app context and db session.

        If ``video_ids`` is set, only those rows are processed (always overwrite existing file).
        """
        job_state._regenerate_status = {
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
                    job_state._regenerate_status = {'status': 'done', 'result': None, 'error': 'Spectrogram generation failed', 'progress': None}
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
                job_state._regenerate_status['progress']['total'] = total

                generated = 0
                failed = 0
                skipped = 0

                for video in videos:
                    if not video.video_path:
                        skipped += 1
                        job_state._regenerate_status['progress'].update(
                            processed=generated + failed + skipped,
                            generated=generated, failed=failed, skipped=skipped,
                        )
                        continue
                    full_video = os.path.join(base, video.video_path)
                    if not os.path.isfile(full_video):
                        skipped += 1
                        job_state._regenerate_status['progress'].update(
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

                    job_state._regenerate_status['progress'].update(
                        processed=generated + failed + skipped,
                        generated=generated, failed=failed, skipped=skipped,
                    )

                try:
                    db.session.commit()
                    app.logger.info(
                        f'Spectrograms: generated={generated}, failed={failed}, skipped={skipped}'
                    )
                    job_state._regenerate_status = {
                        'status': 'done',
                        'result': {'generated': generated, 'failed': failed, 'skipped': skipped},
                        'error': None,
                        'progress': None,
                    }
                except Exception as e:
                    db.session.rollback()
                    app.logger.exception(f'Spectrogram commit failed: {e}')
                    job_state._regenerate_status = {'status': 'done', 'result': None, 'error': 'Spectrogram generation failed', 'progress': None}
        except Exception:
            app.logger.exception('Regenerate spectrograms failed')
            job_state._regenerate_status = {'status': 'done', 'result': None, 'error': 'Spectrogram generation failed', 'progress': None}

    app.extensions.setdefault('birdlense', {})['run_regenerate_spectrograms'] = (
        _run_regenerate_spectrograms
    )

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
        with job_state._regenerate_lock:
            if job_state._regenerate_status['status'] == 'running':
                return {'error': 'Regeneration already in progress', 'status': job_state._regenerate_status}, 409
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
        with job_state._regenerate_lock:
            if job_state._regenerate_status['status'] == 'running':
                return {
                    'error': 'Regeneration already in progress',
                    'status': job_state._regenerate_status,
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
        return job_state._regenerate_status, 200

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
        job_state._regenerate_tracks_status = {
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
                job_state._regenerate_tracks_status['progress']['regen_params'] = regen_params

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
                job_state._regenerate_tracks_status['progress']['total'] = total
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
                    job_state._regenerate_tracks_status['progress']['current_video'] = (
                        video.video_path or None
                    )
                    if not video.video_path:
                        skipped += 1
                        precise_candidates.append({
                            'video_id': video.id,
                            'video_path': None,
                            'reason': 'missing_video_path',
                        })
                        job_state._regenerate_tracks_status['progress'].update(
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
                        job_state._regenerate_tracks_status['progress'].update(
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
                            job_state._regenerate_tracks_status['progress'].update(
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
                                job_state._regenerate_tracks_status['progress'].update(
                                    processed=generated + failed + skipped,
                                    generated=generated, failed=failed, skipped=skipped,
                                )
                                continue

                        manual_vs = [vs for vs in video.video_species if vs.manually_corrected]
                        if manual_vs:
                            # Только обновить frames (bbox) у manually_corrected-строк — виды не трогаем.
                            # Критично: сопоставлять только при совпадении вида, иначе кадр от другой птицы.
                            import json
                            used_det_indices = set()
                            manual_frames_rows_updated = 0
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
                                    manual_frames_rows_updated += 1
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
                            if manual_frames_rows_updated:
                                frames_updated += manual_frames_rows_updated
                            if len(target_video_ids) == 1 and video.id == target_video_ids[0]:
                                single_video_regen_summary = _summarize_track_regen_detections(
                                    unmatched,
                                )
                                single_video_regen_summary['manual_frames_rows_updated'] = int(
                                    manual_frames_rows_updated
                                )
                            precise_candidates.append({
                                'video_id': video.id,
                                'video_path': video.video_path,
                                'reason': (
                                    'has_manual_corrections'
                                    if manual_frames_rows_updated
                                    else 'has_manual_corrections_no_frame_match'
                                ),
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

                    job_state._regenerate_tracks_status['progress'].update(
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
                job_state._regenerate_tracks_status = {
                    'status': 'done',
                    'result': result,
                    'error': None,
                    'progress': None,
                }
        except Exception:
            db.session.rollback()
            app.logger.exception('Regenerate tracks failed')
            job_state._regenerate_tracks_status = {
                'status': 'done', 'result': None, 'error': 'Track regeneration failed',
                'progress': None,
            }

    @app.route('/api/ui/system/regenerate-tracks/status', methods=['GET'])
    def regenerate_tracks_status():
        """Return last track regeneration result."""
        return job_state._regenerate_tracks_status, 200

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
        with job_state._regenerate_tracks_lock:
            if job_state._regenerate_tracks_status['status'] == 'running':
                return {
                    'error': 'Track regeneration already in progress',
                    'status': job_state._regenerate_tracks_status,
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

    from routes.ui_system_species_registry_routes import register_ui_system_species_registry_routes
    register_ui_system_species_registry_routes(app)

    _start_system_metrics_sampler(app)
