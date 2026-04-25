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
            pass
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
            if not isinstance(mode, str) or mode not in {"cascade", "files_only", "disabled"}:
                return {"error": "Invalid mode (allowed: cascade, files_only, disabled)"}, 400
        return run_retention_and_bust_caches(dry_run=dry_run, mode=mode)
