"""SQLite backup/restore и retention (#265)."""

from __future__ import annotations

import shutil

from flask import after_this_request, request, send_file

from models import db
from routes.http_guards import require_ui_settings_password
from services.system_sqlite_admin_api_service import (
    prepare_sqlite_db_backup_download,
    restore_sqlite_database_from_upload,
    run_retention_and_bust_caches,
)
from services.recording_orphan_purge_service import purge_orphan_recording_files

_RETENTION_ALLOWED_MODES = {"cascade", "files_only", "disabled"}


def _nullable_number(value, *, field: str, minimum: float = 0) -> tuple[float | int | None, str | None]:
    if value is None or value == "":
        return None, None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, f"{field} must be a number or null"
    if value < minimum:
        return None, f"{field} must be >= {minimum:g}"
    return value, None


def _non_negative_int(value, *, field: str, minimum: int = 0) -> tuple[int | None, str | None]:
    if isinstance(value, bool) or not isinstance(value, int):
        return None, f"{field} must be an integer"
    if value < minimum:
        return None, f"{field} must be >= {minimum}"
    return value, None


def _validate_retention_update(data: dict) -> tuple[dict, dict | None]:
    allowed = {
        "mode",
        "days",
        "max_gb",
        "dataset_max_age_days",
        "migration_max_age_days",
        "protect_favorites",
        "min_age_hours",
        "batch_size",
        "max_deletes_per_run",
        "auto_run_enabled",
        "auto_run_interval_hours",
    }
    extra = sorted(set(data) - allowed)
    if extra:
        return {}, {"error": f"Unknown retention fields: {', '.join(extra)}"}

    update = {}
    if "mode" in data:
        mode = data["mode"]
        if not isinstance(mode, str) or mode not in _RETENTION_ALLOWED_MODES:
            return {}, {"error": "Invalid mode (allowed: cascade, files_only, disabled)"}
        update["mode"] = mode

    for field in ("days", "max_gb"):
        if field in data:
            value, error = _nullable_number(data[field], field=field)
            if error:
                return {}, {"error": error}
            update[field] = value

    for field, minimum in (
        ("dataset_max_age_days", 0),
        ("migration_max_age_days", 0),
        ("min_age_hours", 0),
        ("batch_size", 1),
        ("max_deletes_per_run", 1),
        ("auto_run_interval_hours", 1),
    ):
        if field in data:
            value, error = _non_negative_int(data[field], field=field, minimum=minimum)
            if error:
                return {}, {"error": error}
            update[field] = value

    if "protect_favorites" in data:
        if not isinstance(data["protect_favorites"], bool):
            return {}, {"error": "protect_favorites must be a boolean"}
        update["protect_favorites"] = data["protect_favorites"]

    if "auto_run_enabled" in data:
        if not isinstance(data["auto_run_enabled"], bool):
            return {}, {"error": "auto_run_enabled must be a boolean"}
        update["auto_run_enabled"] = data["auto_run_enabled"]

    return update, None


def register_ui_system_db_routes(app):
    """DB backup/restore и POST retention."""

    @app.route("/api/ui/system/db/backup", methods=["GET"])
    @require_ui_settings_password
    def backup_database():
        """Download current SQLite database snapshot."""
        err, data, code = prepare_sqlite_db_backup_download(db.engine)
        if err is not None or data is None:
            return err or {"error": "Backup preparation failed"}, code
        snapshot_path = data["snapshot_path"]
        tmp_dir = data["tmp_dir"]
        filename = data["filename"]

        @after_this_request
        def _cleanup_snapshot(response):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return response

        return send_file(
            snapshot_path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/octet-stream",
        )

    @app.route("/api/ui/system/db/restore", methods=["POST"])
    @require_ui_settings_password
    def restore_database():
        """Restore SQLite DB from uploaded .db file; keep pre-restore backup."""
        return restore_sqlite_database_from_upload(
            request.files.get("file"),
            db.engine,
        )

    @app.route("/api/ui/system/retention", methods=["GET"])
    @require_ui_settings_password
    def get_retention_config():
        """Get retention configuration and last run stats."""
        from app_config.app_config import app_config as cfg

        rc = cfg.get("retention", {})
        # safe public values
        safe = {
            "mode": rc.get("mode", "cascade"),
            "days": rc.get("days"),
            "max_gb": rc.get("max_gb"),
            "dataset_max_age_days": rc.get("dataset_max_age_days", 0),
            "migration_max_age_days": rc.get("migration_max_age_days", 0),
            "protect_favorites": rc.get("protect_favorites", True),
            "min_age_hours": rc.get("min_age_hours", 1),
            "batch_size": rc.get("batch_size", 50),
            "max_deletes_per_run": rc.get("max_deletes_per_run", 500),
            "auto_run_enabled": rc.get("auto_run_enabled", False),
            "auto_run_interval_hours": rc.get("auto_run_interval_hours", 6),
        }
        # add last-run metrics
        try:
            from services.retention_service import _fetch_metrics

            m = _fetch_metrics()
            safe["last_run"] = m.get("retention_last_run")
            safe["last_deleted_count"] = m.get("retention_last_deleted_count", 0)
            safe["last_freed_bytes"] = m.get("retention_last_freed_bytes", 0)
            safe["last_mode"] = m.get("retention_mode", "cascade")
        except Exception:
            app.logger.debug("retention last_run metrics unavailable", exc_info=True)
        try:
            from services.recording_orphan_inventory import summarize_orphan_recording_files

            safe["orphan_recording_files"] = summarize_orphan_recording_files()
        except Exception:
            app.logger.debug("retention orphan file inventory unavailable", exc_info=True)
            safe["orphan_recording_files"] = {
                "orphan_session_count": 0,
                "orphan_bytes": 0,
                "sample_paths": [],
            }
        return safe, 200

    @app.route("/api/ui/system/retention", methods=["PUT"])
    @require_ui_settings_password
    def update_retention_config():
        """Update retention parameters in user_config.yaml.
        Accepts JSON with any of the retention fields (mode, days, max_gb, dataset_max_age_days,
        migration_max_age_days, protect_favorites, min_age_hours, batch_size). Returns the
        updated safe config (same shape as GET)."""
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return {"error": "JSON object required"}, 400
        update, error = _validate_retention_update(data)
        if error:
            return error, 400
        from app_config.app_config import app_config as cfg

        safe = cfg.update_retention_config(update)
        return safe, 200

    @app.route("/api/ui/system/retention", methods=["POST"])
    @require_ui_settings_password
    def trigger_retention():
        """Run retention policy (delete old recordings)."""
        data = request.get_json(silent=True) or {}
        dry_run = bool(data.get("dry_run", False))
        mode = data.get("mode")
        # validate mode if provided
        if mode is not None:
            if not isinstance(mode, str) or mode not in _RETENTION_ALLOWED_MODES:
                return {"error": "Invalid mode (allowed: cascade, files_only, disabled)"}, 400
        return run_retention_and_bust_caches(dry_run=dry_run, mode=mode)

    @app.route("/api/ui/system/retention/orphan-files/purge", methods=["POST"])
    @require_ui_settings_password
    def purge_orphan_recording_files_route():
        """Delete disk-only recording sessions (no Video row). Default dry_run=true."""
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return {"error": "JSON object required"}, 400
        return purge_orphan_recording_files(data)
