"""Orphan recording files on disk (no Video row)."""

from __future__ import annotations

from services.recording_orphan_inventory import summarize_orphan_recording_files


def test_orphan_inventory_counts_unreferenced_sessions(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    orphan_dir = rec_root / "2026" / "05" / "01" / "120000"
    linked_dir = rec_root / "2026" / "05" / "01" / "130000"
    orphan_dir.mkdir(parents=True)
    linked_dir.mkdir(parents=True)
    orphan_mp4 = orphan_dir / "video.mp4"
    linked_mp4 = linked_dir / "video.mp4"
    orphan_mp4.write_bytes(b"x" * 1000)
    linked_mp4.write_bytes(b"y" * 2000)

    monkeypatch.setattr(
        "services.recording_orphan_inventory.recordings_dir",
        lambda: str(rec_root),
    )

    from datetime import datetime, timedelta, timezone

    from models import Video, db

    linked_path = "data/recordings/2026/05/01/130000/video.mp4"
    now = datetime.now(timezone.utc)
    with app.app_context():
        db.session.add(
            Video(
                processor_version="test",
                start_time=now - timedelta(hours=1),
                end_time=now,
                video_path=linked_path,
                favorite=False,
            )
        )
        db.session.commit()

        summary = summarize_orphan_recording_files()

    assert summary["orphan_session_count"] == 1
    assert summary["orphan_bytes"] == 1000
    assert summary["sample_paths"] == ["data/recordings/2026/05/01/120000/video.mp4"]
