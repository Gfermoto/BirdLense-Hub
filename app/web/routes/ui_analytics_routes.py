"""Analytics API routes for trajectories, heatmap and visits timeseries."""

from __future__ import annotations

from flask import jsonify, request

from services.analytics_api_service import fetch_heatmap, fetch_trajectories, fetch_visits_timeseries


def register_ui_analytics_routes(app):
    @app.route("/api/ui/analytics/trajectories", methods=["GET"])
    def ui_analytics_trajectories():
        start = request.args.get("start_time")
        end = request.args.get("end_time")
        try:
            limit = int(request.args.get("limit", 250))
        except (TypeError, ValueError):
            limit = 250
        return jsonify(fetch_trajectories(start_iso=start, end_iso=end, limit=limit))

    @app.route("/api/ui/analytics/heatmap", methods=["GET"])
    def ui_analytics_heatmap():
        start = request.args.get("start_time")
        end = request.args.get("end_time")
        try:
            grid = int(request.args.get("grid", 12))
        except (TypeError, ValueError):
            grid = 12
        return jsonify(fetch_heatmap(start_iso=start, end_iso=end, grid=grid))

    @app.route("/api/ui/analytics/visits-timeseries", methods=["GET"])
    def ui_analytics_visits_timeseries():
        start = request.args.get("start_time")
        end = request.args.get("end_time")
        bucket = request.args.get("bucket", "hour")
        return jsonify(fetch_visits_timeseries(start_iso=start, end_iso=end, bucket=bucket))
