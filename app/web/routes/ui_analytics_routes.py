"""Analytics API routes for trajectories, heatmap and visits timeseries."""

from __future__ import annotations

import threading

from flask import jsonify, request

from services.analytics_api_service import (
    fetch_heatmap,
    fetch_quality_health,
    fetch_trajectories,
    fetch_visits_timeseries,
)
from services.cache import cache_get, cache_set
from routes.ui_route_constants import CACHE_ANALYTICS_SEC

_analytics_cache_lock = threading.Lock()

def register_ui_analytics_routes(app):
    def _cached_payload(key: str, builder):
        hit, cached = cache_get(key)
        if hit:
            return cached
        with _analytics_cache_lock:
            hit2, cached2 = cache_get(key)
            if hit2:
                return cached2
            payload = builder()
            cache_set(key, payload, CACHE_ANALYTICS_SEC)
            return payload

    @app.route("/api/ui/analytics/trajectories", methods=["GET"])
    def ui_analytics_trajectories():
        start = request.args.get("start_time")
        end = request.args.get("end_time")
        try:
            limit = int(request.args.get("limit", 250))
        except (TypeError, ValueError):
            limit = 250
        key = f'analytics:traj:v1:{start}:{end}:{limit}'
        payload = _cached_payload(
            key,
            lambda: fetch_trajectories(start_iso=start, end_iso=end, limit=limit),
        )
        return jsonify(payload)

    @app.route("/api/ui/analytics/heatmap", methods=["GET"])
    def ui_analytics_heatmap():
        start = request.args.get("start_time")
        end = request.args.get("end_time")
        try:
            grid = int(request.args.get("grid", 12))
        except (TypeError, ValueError):
            grid = 12
        key = f'analytics:heat:v1:{start}:{end}:{grid}'
        payload = _cached_payload(
            key,
            lambda: fetch_heatmap(start_iso=start, end_iso=end, grid=grid),
        )
        return jsonify(payload)

    @app.route("/api/ui/analytics/visits-timeseries", methods=["GET"])
    def ui_analytics_visits_timeseries():
        start = request.args.get("start_time")
        end = request.args.get("end_time")
        bucket = request.args.get("bucket", "hour")
        key = f'analytics:visits:v1:{start}:{end}:{bucket}'
        payload = _cached_payload(
            key,
            lambda: fetch_visits_timeseries(start_iso=start, end_iso=end, bucket=bucket),
        )
        return jsonify(payload)

    @app.route("/api/ui/analytics/quality-health", methods=["GET"])
    def ui_analytics_quality_health():
        try:
            hours = int(request.args.get("hours", 24))
        except (TypeError, ValueError):
            hours = 24
        key = f'analytics:quality:v1:{hours}'
        payload = _cached_payload(
            key,
            lambda: fetch_quality_health(hours=hours),
        )
        return jsonify(payload)
