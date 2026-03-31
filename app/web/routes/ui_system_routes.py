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
import psutil
from flask import request, Response, send_file, jsonify
import shutil
from models import ActivityLog, db, Video, Species, VideoSpecies, SpeciesVisit, SystemResourceSample
from sqlalchemy import func, select, exists, delete
from services.retention_service import run_retention
from services.species_registry_service import (
    ensure_species_registry_seeded,
    backfill_species_taxa,
    enrich_species_metadata,
    enrich_species_metadata_with_status,
    ensure_allowlist_species_materialized,
    repair_catalog_cards,
    catalog_cards_coverage_snapshot,
    species_registry_health,
    unresolved_species_report,
    resolve_species_name,
)
from services.heimdall_service import probe_heimdall
from app_config.app_config import app_config
from util import settings_check_access, recordings_dir
from services.cache import cache_get, cache_set
from services.http_response_cache import bust_system_response_caches, bust_response_caches

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


IMPORT_SPECIES_NAME = "Unknown"
LOG_LINES_DEFAULT = 200
LOG_LINES_MAX = 500
DEPRECATED_USER_CONFIG_KEYS = (
    'notifications.enabled',
    'notifications.excluded_species',
    'notifications.rate_limit_per_minute',
    'processor.detection_device',
    'processor.detection_frame_interval',
)


def _is_legacy_import_placeholder(vs: VideoSpecies) -> bool:
    species = getattr(vs, 'species', None)
    species_name = getattr(species, 'name', None)
    frames = (getattr(vs, 'frames', None) or '').strip()
    return (
        getattr(vs, 'detection_provider', None) == 'legacy'
        and species_name == IMPORT_SPECIES_NAME
        and float(getattr(vs, 'confidence', 0) or 0) <= 0
        and getattr(vs, 'source', None) == 'video'
        and not bool(getattr(vs, 'manually_corrected', False))
        and getattr(vs, 'track_id', None) is None
        and not frames
        and float(getattr(vs, 'start_time', 0) or 0) == 0
        and float(getattr(vs, 'end_time', 0) or 0) == 30
    )


def _cleanup_legacy_import_placeholders() -> tuple[int, int]:
    """Remove synthetic Unknown/legacy detections created by old disk-import flow."""
    rows = (
        db.session.query(VideoSpecies)
        .join(Species)
        .filter(
            VideoSpecies.detection_provider == 'legacy',
            Species.name == IMPORT_SPECIES_NAME,
        )
        .all()
    )
    placeholder_rows = [vs for vs in rows if _is_legacy_import_placeholder(vs)]
    if not placeholder_rows:
        return 0, 0

    visit_ids = {vs.species_visit_id for vs in placeholder_rows if vs.species_visit_id}
    for vs in placeholder_rows:
        db.session.delete(vs)
    db.session.flush()

    cleaned_visits = 0
    for visit_id in visit_ids:
        other = VideoSpecies.query.filter(
            VideoSpecies.species_visit_id == visit_id,
        ).first()
        if other:
            continue
        visit = db.session.get(SpeciesVisit, visit_id)
        if visit:
            db.session.delete(visit)
            cleaned_visits += 1

    return len(placeholder_rows), cleaned_visits


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

    def _notify_preview_rows_24h():
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        preview_since = now_utc - timedelta(hours=24)
        return (
            db.session.query(ActivityLog)
            .filter(ActivityLog.type == 'notify_preview', ActivityLog.created_at >= preview_since)
            .all()
        )

    def _activity_log_payload(row):
        try:
            return row.data if isinstance(row.data, dict) else (
                json.loads(row.data) if row.data else {}
            )
        except Exception:
            return {}

    def _notify_preview_by_source_24h():
        preview_rows = _notify_preview_rows_24h()
        preview_by_source = {'best_frame': 0, 'bbox_crop': 0, 'full_frame': 0, 'none': 0, 'unknown': 0}
        for row in preview_rows:
            src = 'unknown'
            payload = _activity_log_payload(row)
            src = str((payload or {}).get('preview_source') or 'unknown')
            if src not in preview_by_source:
                src = 'unknown'
            preview_by_source[src] += 1
        return preview_by_source

    def _notify_fallback_by_reason_24h():
        preview_rows = _notify_preview_rows_24h()
        by_reason = {
            'none': 0,
            'no_preview': 0,
            'decode_failed': 0,
            'telegram_photo_failed': 0,
            'notifications_disabled': 0,
            'telegram_not_configured': 0,
            'config_disabled': 0,
            'unsafe_path': 0,
            'read_failed': 0,
            'telegram_text_failed': 0,
            'unexpected_error': 0,
            'unknown': 0,
        }
        for row in preview_rows:
            payload = _activity_log_payload(row)
            reason = str((payload or {}).get('fallback_reason') or 'none')
            if reason not in by_reason:
                reason = 'unknown'
            by_reason[reason] += 1
        return by_reason

    def _notify_delivery_24h():
        preview_rows = _notify_preview_rows_24h()
        by_delivery = {
            'photo': 0,
            'text': 0,
            'text_fallback': 0,
            'failed': 0,
            'skipped': 0,
            'unknown': 0,
        }
        for row in preview_rows:
            payload = _activity_log_payload(row)
            delivery = str((payload or {}).get('telegram_delivery') or 'unknown')
            if delivery not in by_delivery:
                delivery = 'unknown'
            by_delivery[delivery] += 1
        return by_delivery

    def _prometheus_metrics_body(app):
        sys_m = _collect_live_system_metrics(app)
        detections = db.session.query(func.count(VideoSpecies.id)).scalar() or 0
        species_count = db.session.query(VideoSpecies.species_id).distinct().count()
        videos_count = db.session.query(func.count(Video.id)).scalar() or 0
        preview_by_source = _notify_preview_by_source_24h()
        fallback_by_reason = _notify_fallback_by_reason_24h()
        delivery_counts = _notify_delivery_24h()
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
            '# HELP birdlense_notify_preview_24h Notification preview source counts for last 24h',
            '# TYPE birdlense_notify_preview_24h gauge',
        ]
        for src, count in preview_by_source.items():
            lines.append(f'birdlense_notify_preview_24h{{source="{src}"}} {count}')
        lines.extend([
            '# HELP birdlense_notify_fallback_24h Notification fallback reason counts for last 24h',
            '# TYPE birdlense_notify_fallback_24h gauge',
        ])
        for reason, count in fallback_by_reason.items():
            lines.append(f'birdlense_notify_fallback_24h{{reason="{reason}"}} {count}')
        lines.extend([
            '# HELP birdlense_notify_delivery_24h Notification delivery outcome counts for last 24h',
            '# TYPE birdlense_notify_delivery_24h gauge',
        ])
        for delivery, count in delivery_counts.items():
            lines.append(f'birdlense_notify_delivery_24h{{delivery="{delivery}"}} {count}')
        if sys_m['gpu_percent'] is not None:
            lines.extend([
                '# HELP birdlense_gpu_usage_percent GPU usage',
                '# TYPE birdlense_gpu_usage_percent gauge',
                f'birdlense_gpu_usage_percent {sys_m["gpu_percent"]}',
            ])
        return '\n'.join(lines) + '\n'

    @app.route('/api/metrics/summary', methods=['GET'])
    def metrics_summary_json():
        """JSON snapshot for Grafana/Heimdall widgets or external monitors (same data as /metrics)."""
        try:
            sys_m = _collect_live_system_metrics(app)
            detections = db.session.query(func.count(VideoSpecies.id)).scalar() or 0
            species_count = db.session.query(VideoSpecies.species_id).distinct().count()
            videos_count = db.session.query(func.count(Video.id)).scalar() or 0
            preview = _notify_preview_by_source_24h()
            fallback = _notify_fallback_by_reason_24h()
            delivery = _notify_delivery_24h()
            payload = {
                'service': 'birdlense-hub',
                'cpu_usage_percent': float(sys_m['cpu']['percent']),
                'memory_used_percent': float(sys_m['memory']['percent']),
                'memory_used_bytes': int(sys_m['memory']['used_bytes']),
                'memory_total_bytes': int(sys_m['memory']['total_bytes']),
                'disk_used_percent': float(sys_m['disk']['percent']),
                'detections_total': int(detections),
                'species_count': int(species_count),
                'videos_total': int(videos_count),
                'notify_preview_24h': preview,
                'notify_fallback_24h': fallback,
                'notify_delivery_24h': delivery,
            }
            if sys_m['gpu_percent'] is not None:
                payload['gpu_usage_percent'] = float(sys_m['gpu_percent'])
            return jsonify(payload)
        except Exception as e:
            app.logger.error('metrics summary: %s', e)
            return jsonify({'error': 'Failed to build metrics summary'}), 500

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
        hit, cached = cache_get('system_metrics:snapshot')
        if hit:
            return cached
        try:
            m = _collect_live_system_metrics(app)
            payload = {
                'cpu': m['cpu'],
                'memory': m['memory'],
                'disk': m['disk'],
                'encoding': m['encoding'],
                'gpu_percent': m['gpu_percent'],
            }
            cache_set('system_metrics:snapshot', payload, _CACHE_SYSTEM_METRICS_SEC)
            return payload
        except Exception as e:
            app.logger.error(f"Error getting system metrics: {str(e)}")
            return {'error': 'Failed to get system metrics'}, 500

    @app.route('/api/ui/system/observability', methods=['GET'])
    def system_observability():
        """Telegram preview-source counts + URLs for exporting Hub metrics (Heimdall/Grafana)."""
        if not settings_check_access():
            return {'error': 'Unauthorized'}, 401
        try:
            preview = _notify_preview_by_source_24h()
            fallback = _notify_fallback_by_reason_24h()
            delivery = _notify_delivery_24h()
            return {
                'notify_preview_24h': preview,
                'notify_fallback_24h': fallback,
                'notify_delivery_24h': delivery,
                'hub_metrics': {
                    'prometheus_text': '/metrics',
                    'prometheus_text_alt': '/api/metrics',
                    'json_summary': '/api/metrics/summary',
                },
            }
        except Exception as e:
            app.logger.error('observability: %s', e)
            return {'error': 'Failed'}, 500

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
        unknown_keys = sorted([k for k in user_keys if k not in default_keys and not k.startswith('camera.')])
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

    @app.route('/api/ui/system/visitors', methods=['GET'])
    def system_visitors():
        try:
            try:
                days = int(request.args.get('days', '7'))
            except (TypeError, ValueError):
                days = 7
            vck = f'system_visitors:{days}'
            hit, vc = cache_get(vck)
            if hit:
                return vc
            out = _collect_visitor_stats(days)
            cache_set(vck, out, _CACHE_SYSTEM_VISITORS_SEC)
            return out
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
            hck = f'system_metrics_hist:{hours}:{max_points}'
            hit, hc = cache_get(hck)
            if hit:
                return hc
            now = datetime.now(timezone.utc)
            start = now - timedelta(hours=hours)
            rows = db.session.scalars(
                select(SystemResourceSample)
                .where(SystemResourceSample.recorded_at >= start)
                .order_by(SystemResourceSample.recorded_at.asc())
            ).all()
            rows = _downsample_evenly(rows, max_points)
            payload = {
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
            cache_set(hck, payload, _CACHE_SYSTEM_METRICS_HIST_SEC)
            return payload
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

            bust_system_response_caches()
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
            bust_system_response_caches()
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
                from services.visit_processor import VisitProcessor

                base = os.path.dirname(os.path.dirname(recordings_dir()))
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
                    or 'single_stage'
                )
                max_runtime_sec = int(
                    app_config.get('processor.track_regen_video_timeout_sec') or 300
                )
                species_ids_f = sorted(set(species_ids or []))
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
                _regenerate_tracks_status['progress']['regen_params'] = regen_params

                if force:
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

                if species_ids_f and force:
                    vid_subq = (
                        select(VideoSpecies.video_id)
                        .where(VideoSpecies.species_id.in_(species_ids_f))
                        .distinct()
                    )
                    q = q.filter(Video.id.in_(vid_subq))

                videos = q.order_by(Video.start_time.asc()).all()
                target_video_ids = sorted(set(video_ids or []))
                if target_video_ids:
                    videos = [v for v in videos if v.id in target_video_ids]
                total = len(videos)
                _regenerate_tracks_status['progress']['total'] = total
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
                precise_candidates: list[dict] = []

                visit_timeout = int(app_config.get('detection.dedup_window_seconds') or 60)
                visit_processor = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
                # Reuse YOLO+tracker pipeline across all videos in the batch.
                frame_processor, decision_maker = build_detection_pipeline(
                    app_config,
                    strategy_override=regen_strategy,
                    for_track_regen=True,
                )
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
                    full_video = os.path.join(base, video.video_path)
                    if not os.path.isfile(full_video):
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
                        detections = process_video_for_tracks(
                            full_video,
                            lores_size,
                            frame_processor=frame_processor,
                            decision_maker=decision_maker,
                            frame_step=frame_step,
                            max_runtime_sec=max_runtime_sec,
                        )
                        if not detections:
                            skipped += 1
                            precise_candidates.append({
                                'video_id': video.id,
                                'video_path': video.video_path,
                                'reason': 'no_detections_fast_run',
                            })
                            _regenerate_tracks_status['progress'].update(
                                processed=generated + failed + skipped,
                                generated=generated, failed=failed, skipped=skipped,
                            )
                            continue

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
                        else:
                            VideoSpecies.query.filter_by(video_id=video.id).delete()
                            visit_processor.process_detections(video, detections)
                            generated += 1
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
                result = {
                    'generated': generated,
                    'failed': failed,
                    'skipped': skipped,
                    'regen_params': regen_params,
                }
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
        frame_step = data.get('frame_step')
        try:
            video_ids = _parse_video_ids(data)
        except ValueError as e:
            return {'error': str(e)}, 400
        try:
            species_ids = _parse_species_ids(data)
        except ValueError as e:
            return {'error': str(e)}, 400
        try:
            frame_step = int(frame_step) if frame_step is not None else None
        except Exception:
            frame_step = None
        t = threading.Thread(
            target=_run_regenerate_tracks,
            args=(force, start_date, end_date, frame_step, video_ids, species_ids),
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
                            args=(False, None, None),
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
            bust_response_caches()
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

    @app.route('/api/ui/system/species-registry/materialize-allowlist', methods=['POST'])
    def species_registry_materialize_allowlist():
        """Create missing Species rows for allowlist and optionally fill metadata."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        payload = request.get_json(silent=True) or {}
        dry_run = bool(payload.get('dry_run', False))
        fill_metadata = bool(payload.get('fill_metadata', True))
        try:
            limit = int(payload.get('limit', 5000))
        except (TypeError, ValueError):
            return {'error': 'limit must be int'}, 400
        try:
            body = ensure_allowlist_species_materialized(
                app_config.get,
                fill_metadata=fill_metadata,
                dry_run=dry_run,
                limit=limit,
            )
            bust_response_caches()
            bust_system_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Materialize allowlist failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/repair-cards', methods=['POST'])
    def species_registry_repair_cards():
        """Auto-heal full catalog cards metadata and blocked image links."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        payload = request.get_json(silent=True) or {}
        dry_run = bool(payload.get('dry_run', False))
        try:
            limit = int(payload.get('limit', 6000))
        except (TypeError, ValueError):
            return {'error': 'limit must be int'}, 400
        try:
            body = repair_catalog_cards(
                app_config.get,
                dry_run=dry_run,
                limit=limit,
            )
            bust_response_caches()
            bust_system_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Repair cards failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/repair-cards/start', methods=['POST'])
    def species_registry_repair_cards_start():
        """Start background repair for species cards."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _catalog_cards_lock:
            if _catalog_cards_status.get('status') == 'running':
                return {'error': 'Repair already running', 'status': _catalog_cards_status}, 409
            payload = request.get_json(silent=True) or {}
            try:
                limit = int(payload.get('limit', 6000))
            except (TypeError, ValueError):
                return {'error': 'limit must be int'}, 400
            _catalog_cards_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': {
                    'limit': limit,
                    'coverage_before': catalog_cards_coverage_snapshot(app_config.get),
                },
            })

            def _run():
                try:
                    with app.app_context():
                        result = repair_catalog_cards(
                            app_config.get,
                            dry_run=False,
                            limit=limit,
                        )
                        coverage_after = catalog_cards_coverage_snapshot(app_config.get)
                    with _catalog_cards_lock:
                        _catalog_cards_status.update({
                            'status': 'done',
                            'result': {**result, 'coverage_after': coverage_after},
                            'error': None,
                        })
                except Exception as e:
                    with _catalog_cards_lock:
                        _catalog_cards_status.update({
                            'status': 'error',
                            'result': None,
                            'error': str(e),
                        })

            threading.Thread(target=_run, daemon=True).start()
            return {'message': 'Catalog cards repair started', 'status': _catalog_cards_status}, 202

    @app.route('/api/ui/system/species-registry/repair-cards/status', methods=['GET'])
    def species_registry_repair_cards_status():
        """Read background repair status with live coverage counters."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with _catalog_cards_lock:
            snap = dict(_catalog_cards_status)
        snap['coverage_now'] = catalog_cards_coverage_snapshot(app_config.get)
        snap['schedule'] = _catalog_cards_schedule_state()
        return snap, 200

    @app.route('/api/ui/system/species-registry/data-quality', methods=['GET'])
    def species_registry_data_quality():
        """Отчёт по мусорным/не-птица строкам каталога и дубликатам имён (слияние)."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.species_data_quality_service import build_data_quality_report

        dup_limit = request.args.get('duplicate_limit', type=int) or 80
        dup_limit = max(10, min(dup_limit, 500))
        try:
            body = build_data_quality_report(
                db.session,
                duplicate_group_limit=dup_limit,
            )
            return body, 200
        except Exception as e:
            app.logger.exception('Species data quality report failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/classifier-dataset-alignment', methods=['GET'])
    def species_registry_classifier_dataset_alignment():
        """Классы классификатора (best.pt) ↔ каталог Species ↔ папки data/dataset."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.species_dataset_alignment_service import build_classifier_dataset_alignment_report

        clf_lim = request.args.get('classifier_limit', type=int) or 600
        cat_lim = request.args.get('catalog_limit', type=int) or 400
        ds_lim = request.args.get('dataset_limit', type=int) or 200
        try:
            body = build_classifier_dataset_alignment_report(
                db.session,
                app_config.get,
                classifier_limit=clf_lim,
                catalog_limit=cat_lim,
                dataset_limit=ds_lim,
            )
            return body, 200
        except Exception as e:
            app.logger.exception('Classifier/dataset alignment report failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/coverage-metrics', methods=['GET'])
    def species_registry_coverage_metrics():
        """Coverage metrics for observed/dataset/full EU catalog segments."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.species_dataset_alignment_service import build_catalog_coverage_metrics

        try:
            body = build_catalog_coverage_metrics(db.session, app_config.get)
            return body, 200
        except Exception as e:
            app.logger.exception('Catalog coverage metrics failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/tuning-targets/export', methods=['GET'])
    def species_registry_tuning_targets_export():
        """Export manually marked tuning targets for training pipeline."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        raw = app_config.get('species.tuning_target_species_ids') or []
        ids = []
        if isinstance(raw, list):
            for x in raw:
                try:
                    v = int(x)
                except (TypeError, ValueError):
                    continue
                if v > 0:
                    ids.append(v)
        ids = sorted(set(ids))
        rows = Species.query.filter(Species.id.in_(ids)).all() if ids else []
        by_id = {s.id: s for s in rows}

        fmt = (request.args.get('format') or 'json').strip().lower()
        body_rows = [{'id': sid, 'name': by_id[sid].name} for sid in ids if sid in by_id]
        if fmt == 'csv':
            buf = io.StringIO()
            wr = csv.writer(buf)
            wr.writerow(['species_id', 'species_name'])
            for r in body_rows:
                wr.writerow([r['id'], r['name']])
            return Response(
                buf.getvalue(),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': 'attachment; filename="birdlense_tuning_targets.csv"',
                },
            )
        return {'count': len(body_rows), 'targets': body_rows}, 200

    _start_system_metrics_sampler(app)
