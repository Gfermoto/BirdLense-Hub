"""Tests for reconcile_recordings_service (#604)."""

import json
import os
import time
from datetime import datetime, timezone

from models import Video, db


def _age_file(path, *, age_seconds: float = 3600.0) -> None:
    old = time.time() - age_seconds
    os.utime(path, (old, old))


def test_read_session_manifest_times(tmp_path):
    session_dir = tmp_path / "2026" / "06" / "03" / "120000"
    session_dir.mkdir(parents=True)
    start = datetime(2026, 6, 3, 10, 15, 30, tzinfo=timezone.utc)
    end = datetime(2026, 6, 3, 10, 16, 0, tzinfo=timezone.utc)
    manifest = {
        "schema": "recording_session_manifest@v1",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "state": "failed",
    }
    (session_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    from services.session_manifest_io import read_session_manifest_times

    got_start, got_end = read_session_manifest_times(str(session_dir))
    assert got_start == start
    assert got_end == end


def test_quota_maintainer_delegates(monkeypatch):
    calls = {}

    def fake_pending():
        return True, "max_gb"

    def fake_run(**kwargs):
        calls.update(kwargs)
        return 1, 1024

    monkeypatch.setattr("services.quota_maintainer.retention_deletion_pending", fake_pending)
    monkeypatch.setattr("services.quota_maintainer.run_retention", fake_run)

    from services.quota_maintainer import run_quota_trim

    deleted, freed = run_quota_trim(dry_run=True, policy_scope="max_gb")
    assert deleted == 1
    assert freed == 1024
    assert calls.get("dry_run") is True


def test_reconcile_imports_orphan_disk(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    orphan_dir = rec_root / "2026" / "06" / "09" / "120000"
    orphan_dir.mkdir(parents=True)
    mp4 = orphan_dir / "video.mp4"
    mp4.write_bytes(b"x" * 800)
    _age_file(mp4)
    start = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 9, 12, 0, 45, tzinfo=timezone.utc)
    (orphan_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "recording_session_manifest@v1",
                "state": "failed",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("services.system_maintenance_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_purge_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_inventory.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr(
        "services.reconcile_recordings_service.apply_broken_video_rows_purge",
        lambda **kwargs: {"deleted_count": 0},
    )

    from services.reconcile_recordings_service import run_disk_db_reconcile

    with app.app_context():
        body = run_disk_db_reconcile(app)

    assert body["ok"] is True
    assert body["imported"] == 1
    assert body["purge_orphan_disk"]["deleted_count"] == 0
    assert body["orphan_after"]["orphan_session_count"] == 0
    assert orphan_dir.is_dir()
    with app.app_context():
        assert db.session.query(Video).count() == 1
        video = db.session.query(Video).one()
        assert video.end_time.replace(tzinfo=timezone.utc) == end


def test_reconcile_skips_active_orphan_purge(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    active_dir = rec_root / "2026" / "06" / "09" / "120100"
    active_dir.mkdir(parents=True)
    mp4 = active_dir / "video.mp4"
    mp4.write_bytes(b"x" * 1200)
    start = datetime(2026, 6, 9, 12, 1, 0, tzinfo=timezone.utc)
    (active_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "recording_session_manifest@v1",
                "state": "recording",
                "start_time": start.isoformat(),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("services.system_maintenance_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_purge_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_inventory.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr(
        "services.reconcile_recordings_service.apply_broken_video_rows_purge",
        lambda **kwargs: {"deleted_count": 0},
    )

    from services.reconcile_recordings_service import run_disk_db_reconcile

    with app.app_context():
        body = run_disk_db_reconcile(app)

    assert body["ok"] is True
    assert body["imported"] == 0
    assert body["skipped_pending"] == 1
    assert body["purge_orphan_disk"]["deleted_count"] == 0
    assert body["purge_orphan_disk"]["skipped_grace"] == 1
    assert active_dir.is_dir()


def test_reconcile_skips_recent_orphan_without_manifest(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    recent_dir = rec_root / "2026" / "06" / "09" / "120200"
    recent_dir.mkdir(parents=True)
    (recent_dir / "video.mp4").write_bytes(b"x" * 1200)

    monkeypatch.setattr("services.system_maintenance_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_purge_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_inventory.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr(
        "services.reconcile_recordings_service.apply_broken_video_rows_purge",
        lambda **kwargs: {"deleted_count": 0},
    )

    from services.reconcile_recordings_service import run_disk_db_reconcile

    with app.app_context():
        body = run_disk_db_reconcile(app)

    assert body["ok"] is True
    assert body["imported"] == 0
    assert body["skipped_pending"] == 1
    assert body["purge_orphan_disk"]["deleted_count"] == 0
    assert body["purge_orphan_disk"]["skipped_grace"] == 1
    assert recent_dir.is_dir()


def test_scan_skips_incomplete_manifest_without_end_time(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    pending_dir = rec_root / "2026" / "06" / "09" / "120300"
    pending_dir.mkdir(parents=True)
    mp4 = pending_dir / "video.mp4"
    mp4.write_bytes(b"x" * 1200)
    _age_file(mp4)
    start = datetime(2026, 6, 9, 12, 3, 0, tzinfo=timezone.utc)
    (pending_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "recording_session_manifest@v1",
                "state": "failed",
                "start_time": start.isoformat(),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("services.system_maintenance_service.recordings_dir", lambda: str(rec_root))

    from services.system_maintenance_service import run_recordings_scan

    with app.app_context():
        body, code = run_recordings_scan(app)

    assert code == 200
    assert body["imported"] == 0
    assert body["skipped_pending"] == 1
    with app.app_context():
        assert db.session.query(Video).count() == 0


def test_reconcile_purges_unimportable_orphan_disk(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    orphan_dir = rec_root / "2026" / "06" / "09" / "120001"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "video.mp4").write_bytes(b"")

    monkeypatch.setattr("services.system_maintenance_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_purge_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_inventory.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr(
        "services.reconcile_recordings_service.apply_broken_video_rows_purge",
        lambda **kwargs: {"deleted_count": 0},
    )

    from services.reconcile_recordings_service import run_disk_db_reconcile

    with app.app_context():
        body = run_disk_db_reconcile(app)

    assert body["ok"] is True
    assert body["imported"] == 0
    assert body["purge_orphan_disk"]["deleted_count"] == 1
    assert not orphan_dir.exists()


def test_reconcile_purges_broken_db_row(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    rec_root.mkdir(parents=True)
    monkeypatch.setattr("services.system_maintenance_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_purge_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_inventory.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("data_paths.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("util.recordings_dir", lambda: str(rec_root))

    with app.app_context():
        video = Video(
            processor_version="1",
            start_time=datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 9, 12, 0, 30, tzinfo=timezone.utc),
            video_path="data/recordings/2026/06/09/120000/video.mp4",
        )
        db.session.add(video)
        db.session.commit()
        vid = video.id

    from services.reconcile_recordings_service import run_disk_db_reconcile

    with app.app_context():
        body = run_disk_db_reconcile(app)

    assert body["ok"] is True
    assert body["purge_broken_db_rows"]["deleted_count"] == 1
    with app.app_context():
        assert db.session.get(Video, vid) is None


def test_reconcile_purge_dry_run_skips_deletes(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    orphan_dir = rec_root / "2026" / "06" / "09" / "120002"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "video.mp4").write_bytes(b"")

    monkeypatch.setattr("services.system_maintenance_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_purge_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_inventory.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.reconcile_recordings_service._purge_dry_run", lambda: True)

    with app.app_context():
        video = Video(
            processor_version="1",
            start_time=datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 9, 12, 0, 30, tzinfo=timezone.utc),
            video_path="data/recordings/2026/06/09/missing/video.mp4",
        )
        db.session.add(video)
        db.session.commit()
        vid = video.id

    from services.reconcile_recordings_service import run_disk_db_reconcile

    with app.app_context():
        body = run_disk_db_reconcile(app)

    assert body["ok"] is True
    assert body["dry_run"] is True
    assert orphan_dir.is_dir()
    assert body["purge_orphan_disk"]["dry_run"] is True
    assert body["purge_orphan_disk"]["would_delete_count"] == 1
    assert body["purge_orphan_disk"]["deleted_count"] == 0
    assert body["purge_broken_db_rows"]["dry_run"] is True
    assert body["purge_broken_db_rows"]["would_delete_count"] == 1
    assert body["purge_broken_db_rows"]["deleted_count"] == 0
    with app.app_context():
        assert db.session.get(Video, vid) is not None
