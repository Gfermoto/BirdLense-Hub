"""Оркестрация SQLite backup/restore и retention для UI system API (#293)."""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from typing import Any

from models import db
from services.http_response_cache import bust_system_response_caches
from services.retention_service import run_retention
from services.sqlite_admin_service import (
    backup_sqlite_to_file,
    replace_live_sqlite_db,
    sqlite_main_file_path,
    validate_sqlite_file,
)

_log = logging.getLogger(__name__)


def prepare_sqlite_db_backup_download(
    engine: Any,
) -> tuple[dict | None, dict | None, int]:
    """Успех: (None, {snapshot_path, tmp_dir, filename}, 200). Иначе (error, None, code)."""
    db_path = sqlite_main_file_path(engine)
    if not db_path:
        return {"error": "DB backup is supported only for SQLite"}, None, 400
    if not os.path.isfile(db_path):
        return {"error": "Database file not found"}, None, 404
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    filename = f"birdlense_db_backup_{ts}.db"
    tmp_dir = tempfile.mkdtemp(prefix="birdlense-db-backup-")
    snapshot_path = os.path.join(tmp_dir, filename)
    try:
        backup_sqlite_to_file(db_path, snapshot_path)
        validate_sqlite_file(snapshot_path)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        _log.exception("DB backup failed")
        return {"error": "Failed to create DB backup snapshot"}, None, 500
    return (
        None,
        {
            "snapshot_path": snapshot_path,
            "tmp_dir": tmp_dir,
            "filename": filename,
        },
        200,
    )


def restore_sqlite_database_from_upload(
    upload: Any,
    engine: Any,
) -> tuple[dict, int]:
    """Восстановление из multipart upload; pre-restore backup рядом с live db."""
    if not upload:
        return {"error": "file is required (multipart/form-data)"}, 400
    db_path = sqlite_main_file_path(engine)
    if not db_path:
        return {"error": "DB restore is supported only for SQLite"}, 400
    if not os.path.isfile(db_path):
        return {"error": "Database file not found"}, 404

    tmp_dir = tempfile.mkdtemp(prefix="birdlense-db-restore-")
    uploaded_path = os.path.join(tmp_dir, "uploaded.db")
    restored_path = os.path.join(tmp_dir, "restored.db")
    backup_path = ""
    try:
        upload.save(uploaded_path)
        if not os.path.isfile(uploaded_path) or os.path.getsize(uploaded_path) == 0:
            return {"error": "Uploaded file is empty"}, 400

        try:
            validate_sqlite_file(uploaded_path)
        except sqlite3.DatabaseError:
            return {"error": "Uploaded SQLite file failed integrity_check"}, 400

        db.session.remove()
        db.engine.dispose()

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
        backup_path = f"{db_path}.pre_restore_{ts}.bak"
        backup_sqlite_to_file(db_path, backup_path)
        backup_sqlite_to_file(uploaded_path, restored_path)
        validate_sqlite_file(restored_path)
        replace_live_sqlite_db(db_path, restored_path)
        bust_system_response_caches()

        return {
            "message": "Database restored successfully",
            "backup_path": backup_path,
        }, 200
    except sqlite3.DatabaseError:
        _log.exception("DB restore failed: invalid SQLite payload")
        return {"error": "Invalid SQLite database file"}, 400
    except Exception as e:
        _log.exception("DB restore failed")
        return {"error": f"Failed to restore DB: {e}"}, 500
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except OSError:
            pass


def run_retention_and_bust_caches() -> tuple[dict, int]:
    try:
        count, size = run_retention()
        bust_system_response_caches()
        return {
            "message": f"Deleted {count} recordings",
            "deletedCount": count,
            "deletedSize": size,
        }, 200
    except Exception:
        _log.exception("Retention failed")
        return {"error": "Failed to run retention"}, 500
