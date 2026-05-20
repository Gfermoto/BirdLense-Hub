"""SOTA 2.0 ScoringEngine debug API."""

from __future__ import annotations

from auth import settings_check_access


def register_debug_scoring_routes(app) -> None:
    @app.route("/api/debug/scoring", methods=["GET"])
    def debug_scoring():
        """
        Live ScoringEngine telemetry: thresholds, 5m histogram, last decisions.
        Requires settings password (same as /api/ui/status/debug).
        """
        if not settings_check_access():
            return {"error": "Password required"}, 403
        from services.scoring_debug_service import build_scoring_debug_payload

        return build_scoring_debug_payload(), 200
