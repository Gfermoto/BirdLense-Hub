"""Debug API: bbox parity metrics (SOTA-06)."""

from __future__ import annotations

from auth import settings_check_access
from flask import request


def register_debug_bbox_parity_routes(app) -> None:
    @app.route("/api/debug/bbox-parity", methods=["GET"])
    def debug_bbox_parity():
        if not settings_check_access():
            return {"error": "Password required"}, 403
        from services.bbox_parity_debug_service import build_bbox_parity_debug_payload

        session_id = (request.args.get("session_id") or "").strip() or None
        return build_bbox_parity_debug_payload(session_id=session_id), 200
