"""Tests for retention max_gb loop (max_deletes_per_run cap)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from models import Video, db
from services.retention_service import run_retention


@pytest.mark.parametrize("max_deletes", [3, 10])
def test_max_gb_respects_max_deletes_per_run(app, tmp_path, monkeypatch, max_deletes):
    """Size trim deletes up to max_deletes_per_run, not batch_size."""
    rec_root = tmp_path / "data" / "recordings"
    rec_root.mkdir(parents=True)
    app_base = tmp_path / "data"
    monkeypatch.setattr("services.retention_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.retention_service._recordings_dir", lambda: str(rec_root))

    old_days = app.config.get("TESTING")
    with app.app_context():
        from app_config.app_config import app_config

        app_config.set("retention.mode", "cascade")
        app_config.set("retention.days", None)
        app_config.set("retention.max_gb", 0.001)
        app_config.set("retention.batch_size", 2)
        app_config.set("retention.max_deletes_per_run", max_deletes)
        app_config.set("retention.min_videos_keep", 0)
        app_config.set("retention.protect_favorites", False)

        now = datetime.now(timezone.utc)
        for i in range(max_deletes + 5):
            rel = f"data/recordings/2026/01/{i:02d}/video.mp4"
            session_dir = app_base / "recordings" / "2026" / "01" / f"{i:02d}"
            session_dir.mkdir(parents=True, exist_ok=True)
            clip = session_dir / "video.mp4"
            clip.write_bytes(b"x" * 500_000)
            row = Video(
                processor_version="test",
                start_time=now - timedelta(days=30 + i),
                end_time=now - timedelta(days=30 + i) + timedelta(seconds=10),
                video_path=rel,
                favorite=False,
            )
            db.session.add(row)
        db.session.commit()

        with patch("services.retention_service._get_recordings_size_gb", return_value=999.0):
            deleted, _ = run_retention(dry_run=False, mode="cascade")

        assert deleted == max_deletes

        app_config.set("retention.max_gb", None)
        app_config.set("retention.days", 90)


def test_max_gb_respects_min_videos_keep(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    rec_root.mkdir(parents=True)
    app_base = tmp_path / "data"
    monkeypatch.setattr("services.retention_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.retention_service._recordings_dir", lambda: str(rec_root))

    with app.app_context():
        from app_config.app_config import app_config

        app_config.set("retention.mode", "cascade")
        app_config.set("retention.days", None)
        app_config.set("retention.max_gb", 0.001)
        app_config.set("retention.max_deletes_per_run", 50)
        app_config.set("retention.min_videos_keep", 3)
        app_config.set("retention.protect_favorites", False)

        now = datetime.now(timezone.utc)
        for i in range(5):
            rel = f"data/recordings/2026/02/{i:02d}/video.mp4"
            session_dir = app_base / "recordings" / "2026" / "02" / f"{i:02d}"
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / "video.mp4").write_bytes(b"x" * 500_000)
            db.session.add(
                Video(
                    processor_version="test",
                    start_time=now - timedelta(days=40 + i),
                    end_time=now - timedelta(days=40 + i) + timedelta(seconds=10),
                    video_path=rel,
                    favorite=False,
                )
            )
        db.session.commit()

        with patch("services.retention_service._get_recordings_size_gb", return_value=999.0):
            deleted, _ = run_retention(dry_run=False, mode="cascade")

        assert deleted == 2
        assert Video.query.filter(Video.deleted_at.is_(None)).count() == 3

        app_config.set("retention.max_gb", None)
        app_config.set("retention.days", 90)
        app_config.set("retention.min_videos_keep", 0)
