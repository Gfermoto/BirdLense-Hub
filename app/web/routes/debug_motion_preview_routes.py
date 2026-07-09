"""Debug API: MOG2 / static calibration preview (SOTA-08)."""

from __future__ import annotations

import json

from auth import settings_check_access
from flask import request


def register_debug_motion_preview_routes(app) -> None:
    @app.route("/api/debug/motion-preview", methods=["GET"])
    def debug_motion_preview():
        if not settings_check_access():
            return {"error": "Password required"}, 403
        from services.motion_preview_debug_service import build_motion_preview_debug_payload

        overrides_raw = (request.args.get("overrides") or "").strip()
        overrides = None
        if overrides_raw:
            try:
                overrides = json.loads(overrides_raw)
            except json.JSONDecodeError:
                return {"error": "invalid_overrides_json"}, 400
        body, status = build_motion_preview_debug_payload(
            camera_id=(request.args.get("camera_id") or "").strip() or None,
            mode=(request.args.get("mode") or "detection_mog2").strip(),
            overrides=overrides if isinstance(overrides, dict) else None,
        )
        return body, status
