"""API тестового прогона file source (#270)."""

from __future__ import annotations

from flask import request

from app_config.app_config import app_config
from routes.http_guards import require_admin_track_regen, require_ui_settings_password
from services.api_json_validation import parse_request_json_object_allow_empty
from services.system_file_test_service import (
    delete_file_test_video,
    get_file_test_status,
    list_file_test_files,
    save_file_test_upload,
    write_desired,
)


def _file_mode_ok() -> bool:
    return (app_config.get("video.source") or "").strip().lower() == "file"


def register_ui_system_file_test_routes(app) -> None:
    @app.route("/api/ui/system/file-test/files", methods=["GET"])
    @require_ui_settings_password
    def file_test_list_files():
        if not _file_mode_ok():
            return {"error": "video.source is not file"}, 409
        body, code = list_file_test_files()
        return body, code

    @app.route("/api/ui/system/file-test/status", methods=["GET"])
    @require_ui_settings_password
    def file_test_status():
        if not _file_mode_ok():
            return {"error": "video.source is not file"}, 409
        body, code = get_file_test_status()
        return body, code

    @app.route("/api/ui/system/file-test/upload", methods=["POST"])
    @require_admin_track_regen
    def file_test_upload():
        if not _file_mode_ok():
            return {"error": "video.source is not file"}, 409
        f = request.files.get("file")
        return save_file_test_upload(f, request.args.get("filename"))

    @app.route("/api/ui/system/file-test/files/<name>", methods=["DELETE"])
    @require_admin_track_regen
    def file_test_delete(name: str):
        if not _file_mode_ok():
            return {"error": "video.source is not file"}, 409
        return delete_file_test_video(name)

    @app.route("/api/ui/system/file-test/run", methods=["POST"])
    @require_admin_track_regen
    def file_test_run():
        if not _file_mode_ok():
            return {"error": "video.source is not file"}, 409
        body, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        armed_kw = bool(body["armed"]) if "armed" in body else None
        loop_kw = bool(body["loop"]) if "loop" in body else None
        if armed_kw is None and loop_kw is None:
            armed_kw = True
        return write_desired(armed=armed_kw, loop=loop_kw)

    @app.route("/api/ui/system/file-test/stop", methods=["POST"])
    @require_admin_track_regen
    def file_test_stop():
        if not _file_mode_ok():
            return {"error": "video.source is not file"}, 409
        body, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        return write_desired(armed=False, abort=bool(body.get("abort", True)))
