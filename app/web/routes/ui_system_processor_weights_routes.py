"""API пользовательских весов процессора (#276)."""

from __future__ import annotations

from flask import request

from routes.http_guards import require_admin_track_regen, require_ui_settings_password
from services.api_json_validation import parse_request_json_object_allow_empty
from services.processor_custom_weights_service import (
    get_status,
    reset_roles,
    save_upload,
)
from services.processor_restart_service import write_processor_restart_flag
from util import data_dir


def register_ui_system_processor_weights_routes(app) -> None:
    @app.route("/api/ui/system/processor-weights/status", methods=["GET"])
    @require_ui_settings_password
    def processor_weights_status():
        return get_status(), 200

    @app.route("/api/ui/system/processor-weights/upload", methods=["POST"])
    @require_admin_track_regen
    def processor_weights_upload():
        role = (request.args.get("role") or "").strip().lower()
        ack = (request.args.get("acknowledge_classifier_only") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        f = request.files.get("file")
        body, code = save_upload(
            role,
            f,
            acknowledge_classifier_only=ack,
        )
        if code == 200:
            try:
                write_processor_restart_flag(data_dir())
            except Exception:
                app.logger.exception("processor-weights: restart flag after upload")
        return body, code

    @app.route("/api/ui/system/processor-weights/reset", methods=["POST"])
    @require_admin_track_regen
    def processor_weights_reset():
        body, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        roles = body.get("roles")
        if not isinstance(roles, list):
            return {"error": "roles_must_be_list"}, 400
        out, code = reset_roles([str(x) for x in roles])
        if code == 200:
            try:
                write_processor_restart_flag(data_dir())
            except Exception:
                app.logger.exception("processor-weights: restart flag after reset")
        return out, code
