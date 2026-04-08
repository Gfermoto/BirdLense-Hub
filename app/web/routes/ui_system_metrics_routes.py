"""Prometheus, /api/ui/system/metrics, visitors, metrics/history (#223)."""

import re
from datetime import datetime, timedelta, timezone

from flask import Response, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from auth import check_visitor_track_rate_limit, client_ip_for_rate_limit
from models import (
    db,
    SiteVisitor,
    SystemResourceSample,
    Video,
    VideoSpecies,
)
from services.activity_notify_insights_service import (
    ingest_gate_reason_counts_24h,
    notify_delivery_24h,
    notify_fallback_by_reason_24h,
    notify_preview_by_source_24h,
    notify_preview_generated_by_source_24h,
    notify_suppressed_reason_counts_24h,
)
from services.cache import cache_delete_prefix, cache_get, cache_set
from services.ml_health_stats_service import ml_health_snapshot
from services.ml_lineage_service import current_model_lineage_snapshot
from services.prometheus_metrics_service import prometheus_metrics_body
from services.system_live_metrics_service import collect_live_system_metrics
from services.system_metrics_constants import (
    SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS,
    SYSTEM_METRICS_HISTORY_MAX_HOURS,
    SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP,
    SYSTEM_METRICS_RETENTION_HOURS,
    SYSTEM_METRICS_SAMPLE_INTERVAL_SEC,
    _CACHE_SYSTEM_METRICS_HIST_SEC,
    _CACHE_SYSTEM_METRICS_SEC,
    _CACHE_SYSTEM_VISITORS_SEC,
)
from services.visitor_stats_service import (
    browser_hash,
    collect_visitor_stats,
    device_class_from_user_agent,
    downsample_evenly,
)
from util import metrics_bearer_denied, settings_check_access


def register_ui_system_metrics_routes(app):
    """Метрики Prometheus/JSON, live system metrics, visitors и история нагрузки."""
    @app.route('/api/metrics/summary', methods=['GET'])
    def metrics_summary_json():
        """JSON snapshot for Grafana/Heimdall widgets or external monitors."""
        denied = metrics_bearer_denied(prometheus=False)
        if denied is not None:
            return denied
        try:
            sys_m = collect_live_system_metrics(app)
            detections = db.session.query(func.count(VideoSpecies.id)).scalar() or 0
            species_count = db.session.query(VideoSpecies.species_id).distinct().count()
            videos_count = db.session.query(func.count(Video.id)).scalar() or 0
            preview = notify_preview_by_source_24h()
            preview_generated = notify_preview_generated_by_source_24h()
            fallback = notify_fallback_by_reason_24h()
            delivery = notify_delivery_24h()
            ingest_gate = ingest_gate_reason_counts_24h()
            notify_suppressed = notify_suppressed_reason_counts_24h()
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
                'notify_preview_generated_24h': preview_generated,
                'notify_fallback_24h': fallback,
                'notify_delivery_24h': delivery,
                'ingest_gate_24h': ingest_gate,
                'notify_suppressed_24h': notify_suppressed,
            }
            if sys_m['gpu_percent'] is not None:
                payload['gpu_usage_percent'] = float(sys_m['gpu_percent'])
            return jsonify(payload)
        except Exception as e:
            app.logger.error('metrics summary: %s', e)
            return jsonify({'error': 'Failed to build metrics summary'}), 500

    @app.route('/api/metrics', methods=['GET'])
    def prometheus_metrics_api():
        denied = metrics_bearer_denied(prometheus=True)
        if denied is not None:
            return denied
        try:
            body = prometheus_metrics_body(app)
            return Response(body, mimetype='text/plain; charset=utf-8')
        except Exception as e:
            app.logger.error('Error getting Prometheus metrics: %s', e)
            return Response('# Error\n', mimetype='text/plain; charset=utf-8', status=500)

    @app.route('/metrics', methods=['GET'])
    def prometheus_metrics():
        denied = metrics_bearer_denied(prometheus=True)
        if denied is not None:
            return denied
        try:
            body = prometheus_metrics_body(app)
            return Response(body, mimetype='text/plain; charset=utf-8')
        except Exception as e:
            app.logger.error('Error getting Prometheus metrics: %s', e)
            return Response('# Error\n', mimetype='text/plain; charset=utf-8', status=500)

    @app.route('/api/ui/system/metrics', methods=['GET'])
    def system_metrics():
        hit, cached = cache_get('system_metrics:snapshot')
        if hit:
            return cached
        try:
            m = collect_live_system_metrics(app)
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
            app.logger.error('Error getting system metrics: %s', e)
            return {'error': 'Failed to get system metrics'}, 500

    @app.route('/api/ui/system/observability', methods=['GET'])
    def system_observability():
        if not settings_check_access():
            return {'error': 'Unauthorized'}, 401
        try:
            preview = notify_preview_by_source_24h()
            preview_generated = notify_preview_generated_by_source_24h()
            fallback = notify_fallback_by_reason_24h()
            delivery = notify_delivery_24h()
            ingest_gate = ingest_gate_reason_counts_24h()
            notify_suppressed = notify_suppressed_reason_counts_24h()
            return {
                'notify_preview_24h': preview,
                'notify_preview_generated_24h': preview_generated,
                'notify_fallback_24h': fallback,
                'notify_delivery_24h': delivery,
                'ingest_gate_24h': ingest_gate,
                'notify_suppressed_24h': notify_suppressed,
                'ml_health': {
                    'rolling_7d': ml_health_snapshot(7),
                    'rolling_30d': ml_health_snapshot(30),
                },
                'model_lineage': current_model_lineage_snapshot(),
                'hub_metrics': {
                    'prometheus_text': '/metrics',
                    'prometheus_text_alt': '/api/metrics',
                    'json_summary': '/api/metrics/summary',
                },
            }
        except Exception as e:
            app.logger.error('observability: %s', e)
            return {'error': 'Failed'}, 500

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
            out = collect_visitor_stats(days)
            cache_set(vck, out, _CACHE_SYSTEM_VISITORS_SEC)
            return out
        except Exception as e:
            app.logger.error('Error getting visitor stats: %s', e)
            return {'error': 'Failed to get visitor stats'}, 500

    @app.route('/api/ui/system/visitors/track', methods=['POST'])
    def system_visitors_track():
        try:
            ip = client_ip_for_rate_limit(request)
            if not check_visitor_track_rate_limit(ip):
                return {'error': 'Too many requests'}, 429

            payload = request.get_json(silent=True) or {}
            raw_browser_id = str(payload.get('browser_id') or '').strip()
            if not re.fullmatch(r'[A-Za-z0-9._:-]{16,128}', raw_browser_id):
                return {'error': 'Invalid browser_id'}, 400

            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            seen_day = now_utc.strftime('%Y-%m-%d')
            bh = browser_hash(raw_browser_id)
            device_class = device_class_from_user_agent(
                request.headers.get('User-Agent', ''),
            )

            row = db.session.query(SiteVisitor).filter(
                SiteVisitor.browser_hash == bh,
                SiteVisitor.seen_day == seen_day,
            ).first()
            if row is None:
                row = SiteVisitor(
                    browser_hash=bh,
                    seen_day=seen_day,
                    device_class=device_class,
                    first_seen_at=now_utc,
                    last_seen_at=now_utc,
                )
                db.session.add(row)
            else:
                row.last_seen_at = now_utc
                row.device_class = device_class
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                row = db.session.query(SiteVisitor).filter(
                    SiteVisitor.browser_hash == bh,
                    SiteVisitor.seen_day == seen_day,
                ).first()
                if row is None:
                    raise
                row.last_seen_at = now_utc
                row.device_class = device_class
                db.session.commit()
            cache_delete_prefix('system_visitors:')
            return {'ok': True}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.error('Error tracking site visitor: %s', e)
            return {'error': 'Failed to track site visitor'}, 500

    @app.route('/api/ui/system/metrics/history', methods=['GET'])
    def system_metrics_history():
        try:
            try:
                hours = int(request.args.get('hours', '24'))
            except (TypeError, ValueError):
                hours = 24
            hours = max(1, min(hours, SYSTEM_METRICS_HISTORY_MAX_HOURS))
            try:
                max_points = int(
                    request.args.get(
                        'max_points',
                        str(SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS),
                    ),
                )
            except (TypeError, ValueError):
                max_points = SYSTEM_METRICS_HISTORY_DEFAULT_MAX_POINTS
            max_points = max(
                50,
                min(max_points, SYSTEM_METRICS_HISTORY_MAX_POINTS_CAP),
            )
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
            rows = downsample_evenly(rows, max_points)
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
            app.logger.error('Error getting system metrics history: %s', e)
            return {'error': 'Failed to get system metrics history'}, 500
