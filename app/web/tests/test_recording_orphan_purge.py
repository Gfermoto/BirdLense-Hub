"""Purge orphan recording files on disk."""

from __future__ import annotations

from services.recording_orphan_purge_service import (
    ORPHAN_FILES_PURGE_CONFIRMATION,
    purge_orphan_recording_files,
)


def test_orphan_purge_dry_run(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    orphan_dir = rec_root / "2026" / "05" / "01" / "120000"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "video.mp4").write_bytes(b"x" * 500)

    monkeypatch.setattr("services.recording_orphan_purge_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.recording_orphan_inventory.recordings_dir", lambda: str(rec_root))

    with app.app_context():
        body, code = purge_orphan_recording_files({"dry_run": True, "limit": 10})
    assert code == 200
    assert body["would_delete_count"] == 1
    assert body["would_free_bytes"] == 500
    assert orphan_dir.is_dir()


def test_orphan_purge_apply(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    orphan_dir = rec_root / "2026" / "05" / "01" / "120000"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "video.mp4").write_bytes(b"x" * 500)

    monkeypatch.setattr("services.recording_orphan_purge_service.recordings_dir", lambda: str(rec_root))

    with app.app_context():
        body, code = purge_orphan_recording_files(
            {
                "dry_run": False,
                "limit": 10,
                "confirmation": ORPHAN_FILES_PURGE_CONFIRMATION,
            }
        )
    assert code == 200
    assert body["deleted_count"] == 1
    assert not orphan_dir.exists()
