"""Метрики, Prometheus, observability, visitors — тонкие роуты (#293)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Response, current_app, jsonify, request

from auth import client_ip_for_rate_limit
from metrics_auth import metrics_bearer_denied
from services.cache import cache_get, cache_set
from services.system_metrics_api_service import (
    clamp_metrics_history_hours,
    clamp_metrics_history_max_points,
    metrics_history_payload_or_error,
    metrics_summary_json_or_error,
    observability_payload_or_error,
    parse_visitors_days,
    prometheus_text_or_error,
    system_metrics_live_payload_or_error,
    track_site_visitor,
    visitor_stats_or_error,
)

if TYPE_CHECKING:
    from flask import Flask

SYSTEM_METRICS_CACHE_TTL = 5
SYSTEM_METRICS_CACHE_KEY = "system_metrics:live"
SYSTEM_VISITORS_CACHE_TTL = 30
SYSTEM_METRICS_HISTORY_CACHE_TTL = 30


def register_ui_system_metrics_routes(app: Flask) -> None:
    @app.route("/api/metrics/summary", methods=["GET"])
    def api_metrics_summary():
        denied = metrics_bearer_denied(prometheus=False)
        if denied is not None:
            return denied
        body, code = metrics_summary_json_or_error(
            current_app._get_current_object(),
        )
        return jsonify(body), code

    @app.route("/metrics", methods=["GET"])
    def metrics_prometheus():
        denied = metrics_bearer_denied(prometheus=True)
        if denied is not None:
            return denied
        text, code = prometheus_text_or_error(
            current_app._get_current_object(),
        )
        return (
            Response(
                text,
                mimetype="text/plain; version=0.0.4; charset=utf-8",
            ),
            code,
        )

    @app.route("/api/metrics", methods=["GET"])
    def api_metrics_prometheus():
        denied = metrics_bearer_denied(prometheus=True)
        if denied is not None:
            return denied
        text, code = prometheus_text_or_error(
            current_app._get_current_object(),
        )
        return (
            Response(
                text,
                mimetype="text/plain; version=0.0.4; charset=utf-8",
            ),
            code,
        )

    @app.route("/api/ui/system/metrics", methods=["GET"])
    def api_system_metrics():
        hit, cached = cache_get(SYSTEM_METRICS_CACHE_KEY)
        if hit:
            return jsonify(cached)
        body, code = system_metrics_live_payload_or_error(
            current_app._get_current_object(),
        )
        if code == 200:
            cache_set(SYSTEM_METRICS_CACHE_KEY, body, SYSTEM_METRICS_CACHE_TTL)
        return jsonify(body), code

    @app.route("/api/ui/system/observability", methods=["GET"])
    def api_system_observability():
        body, code = observability_payload_or_error()
        return jsonify(body), code

    @app.route("/api/ui/system/visitors", methods=["GET"])
    def api_system_visitors():
        days = parse_visitors_days(request.args.get("days"))
        cache_key = f"system_visitors:{days}"
        hit, cached = cache_get(cache_key)
        if hit:
            return jsonify(cached)
        body, code = visitor_stats_or_error(days)
        if code == 200:
            cache_set(cache_key, body, SYSTEM_VISITORS_CACHE_TTL)
        return jsonify(body), code

    @app.route("/api/ui/system/visitors/track", methods=["POST"])
    def api_system_visitors_track():
        data = request.get_json(silent=True) or {}
        browser_id = data.get("browser_id", "")
        user_agent = request.headers.get("User-Agent", "") or ""
        client_ip = client_ip_for_rate_limit(request)
        body, code = track_site_visitor(client_ip, browser_id, user_agent)
        return jsonify(body), code

    @app.route("/api/ui/system/metrics/history", methods=["GET"])
    def api_system_metrics_history():
        hours = clamp_metrics_history_hours(request.args.get("hours"))
        max_points = clamp_metrics_history_max_points(
            request.args.get("max_points"),
        )
        cache_key = f"system_metrics_history:{hours}:{max_points}"
        hit, cached = cache_get(cache_key)
        if hit:
            return jsonify(cached)
        body, code = metrics_history_payload_or_error(hours, max_points)
        if code == 200:
            cache_set(
                cache_key,
                body,
                SYSTEM_METRICS_HISTORY_CACHE_TTL,
            )
        return jsonify(body), code
