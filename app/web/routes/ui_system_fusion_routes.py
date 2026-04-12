"""Fusion export/eval и refresh Telegram proxy (#265)."""

from __future__ import annotations

from flask import current_app, request, send_file

from routes.http_guards import require_ui_settings_password
from services.api_json_validation import parse_request_json_object_allow_empty
from services.system_fusion_telegram_jobs_service import (
    fusion_eval_status_snapshot,
    fusion_export_download_file_or_error,
    fusion_export_status_snapshot,
    start_fusion_eval_background,
    start_fusion_export_background,
    start_telegram_proxy_refresh_background,
    telegram_proxy_refresh_status_snapshot,
)


def register_ui_system_fusion_routes(app):
    """Fusion CSV и Telegram proxy refresh."""

    @app.route("/api/ui/system/fusion/export", methods=["POST"])
    @require_ui_settings_password
    def fusion_export():
        """Export decision traces to CSV for fusion calibration/training."""
        return start_fusion_export_background(
            current_app._get_current_object(),
        )

    @app.route("/api/ui/system/fusion/export/status", methods=["GET"])
    @require_ui_settings_password
    def fusion_export_status():
        return fusion_export_status_snapshot(), 200

    @app.route("/api/ui/system/fusion/export/download", methods=["GET"])
    @require_ui_settings_password
    def fusion_export_download():
        path, err, code = fusion_export_download_file_or_error()
        if err is not None:
            return err, code
        return send_file(
            path,
            as_attachment=True,
            download_name=path.name,
            mimetype="text/csv",
        )

    @app.route("/api/ui/system/fusion/eval", methods=["POST"])
    @require_ui_settings_password
    def fusion_eval():
        """Evaluate fusion calibration on a CSV export."""
        payload, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        return start_fusion_eval_background(
            current_app._get_current_object(),
            payload,
        )

    @app.route("/api/ui/system/fusion/eval/status", methods=["GET"])
    @require_ui_settings_password
    def fusion_eval_status():
        return fusion_eval_status_snapshot(), 200

    @app.route("/api/ui/system/telegram-proxy/refresh", methods=["POST"])
    @require_ui_settings_password
    def refresh_telegram_proxy():
        """Refresh Telegram SOCKS proxy using the backend service."""
        return start_telegram_proxy_refresh_background(
            current_app._get_current_object(),
        )

    @app.route("/api/ui/system/telegram-proxy/refresh/status", methods=["GET"])
    @require_ui_settings_password
    def refresh_telegram_proxy_status():
        return telegram_proxy_refresh_status_snapshot(), 200
