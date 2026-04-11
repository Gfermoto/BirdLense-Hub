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

    @app.route('/api/ui/system/db/backup', methods=['GET'])
    @require_ui_settings_password
    def backup_database():
        """Download current SQLite database snapshot."""
        err, data, code = prepare_sqlite_db_backup_download(db.engine)
        if err is not None or data is None:
            return err or {'error': 'Backup preparation failed'}, code
        snapshot_path = data['snapshot_path']
        tmp_dir = data['tmp_dir']
        filename = data['filename']

        @after_this_request
        def _cleanup_snapshot(response):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return response

        return send_file(
            snapshot_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream',
        )

    @app.route('/api/ui/system/db/restore', methods=['POST'])
    @require_ui_settings_password
    def restore_database():
        """Restore SQLite DB from uploaded .db file; keep pre-restore backup."""
        return restore_sqlite_database_from_upload(
            request.files.get('file'),
            db.engine,
        )

    @app.route('/api/ui/system/retention', methods=['POST'])
    @require_ui_settings_password
    def trigger_retention():
        """Run retention policy (delete old recordings)."""
        return run_retention_and_bust_caches()
