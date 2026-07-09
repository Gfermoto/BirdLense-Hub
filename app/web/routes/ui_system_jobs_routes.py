"""Unified async jobs API: POST/GET/DELETE /api/ui/jobs/* (#513)."""

from __future__ import annotations

import auth as auth_mod
from flask import request

from routes.http_guards import require_admin_track_regen, require_ui_settings_password
from services.api_json_validation import parse_request_json_object_allow_empty
from services.async_jobs_service import (
    catalog_repair_job_snapshot,
    get_job_payload,
    list_job_types,
    list_jobs_payload,
    request_job_cancel,
    start_job,
)


def _settings_denied():
    if not auth_mod.settings_check_access():
        return {"error": "Password required"}, 403
    return None


def register_ui_system_jobs_routes(app) -> None:
    @app.route("/api/ui/jobs", methods=["GET"])
    @require_ui_settings_password
    def list_ui_jobs():
        return list_jobs_payload(), 200

    @app.route("/api/ui/jobs/types", methods=["GET"])
    @require_ui_settings_password
    def list_ui_job_types():
        return {"types": list_job_types()}, 200

    @app.route("/api/ui/jobs", methods=["POST"])
    def create_ui_job():
        body, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        job_type = (body.get("type") or body.get("job_type") or "").strip()
        if not job_type:
            return {"error": "type is required", "allowed": list_job_types()}, 400
        payload = body.get("payload")
        if payload is not None and not isinstance(payload, dict):
            return {"error": "payload must be an object"}, 400
        pl = payload if isinstance(payload, dict) else {}

        if job_type == "track_regen":
            if not auth_mod.admin_track_regen_access():
                return {"error": "Access denied"}, 403
            return start_job(
                app, job_type, {**pl, **{k: v for k, v in body.items() if k not in ("type", "job_type", "payload")}}
            )

        denied = _settings_denied()
        if denied:
            return denied
        return start_job(app, job_type, pl)

    @app.route("/api/ui/jobs/<job_id>", methods=["GET"])
    def get_ui_job(job_id: str):
        jid = (job_id or "").strip()
        if jid == "track_regen":
            if not auth_mod.admin_track_regen_access():
                return {"error": "Access denied"}, 403
            return get_job_payload(jid)
        denied = _settings_denied()
        if denied:
            return denied
        if jid == "catalog_repair":
            return catalog_repair_job_snapshot(), 200
        return get_job_payload(jid)

    @app.route("/api/ui/jobs/<job_id>", methods=["DELETE"])
    @require_admin_track_regen
    def cancel_ui_job(job_id: str):
        return request_job_cancel((job_id or "").strip())
