"""retention_deletion_pending gates scheduled auto-run."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from models import Video, db
from services.retention_service import retention_deletion_pending


def test_pending_false_when_within_days_and_size(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    rec_root.mkdir(parents=True)
    monkeypatch.setattr("services.retention_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.retention_service._recordings_dir", lambda: str(rec_root))

    with app.app_context():
        from app_config.app_config import app_config

        app_config.set("retention.mode", "cascade")
        app_config.set("retention.days", 90)
        app_config.set("retention.max_gb", 32)
        app_config.set("retention.protect_favorites", False)

        now = datetime.now(timezone.utc)
        row = Video(
            processor_version="test",
            start_time=now - timedelta(days=1),
            end_time=now,
            video_path="data/recordings/2026/06/01/video.mp4",
            favorite=False,
        )
        db.session.add(row)
        db.session.commit()

        with patch("services.retention_service._get_recordings_size_gb", return_value=1.0):
            pending, reason = retention_deletion_pending(mode="cascade")

        assert pending is False
        assert reason == ""


def test_pending_true_when_video_older_than_days(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    rec_root.mkdir(parents=True)
    monkeypatch.setattr("services.retention_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.retention_service._recordings_dir", lambda: str(rec_root))

    with app.app_context():
        from app_config.app_config import app_config

        app_config.set("retention.mode", "cascade")
        app_config.set("retention.days", 7)
        app_config.set("retention.max_gb", None)
        app_config.set("retention.protect_favorites", False)

        now = datetime.now(timezone.utc)
        row = Video(
            processor_version="test",
            start_time=now - timedelta(days=30),
            end_time=now - timedelta(days=30) + timedelta(seconds=5),
            video_path="data/recordings/2026/01/01/video.mp4",
            favorite=False,
        )
        db.session.add(row)
        db.session.commit()

        pending, reason = retention_deletion_pending(mode="cascade")
        assert pending is True
        assert reason == "days"


def test_pending_true_when_max_gb_exceeded_and_deletable(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    rec_root.mkdir(parents=True)
    monkeypatch.setattr("services.retention_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.retention_service._recordings_dir", lambda: str(rec_root))

    with app.app_context():
        from app_config.app_config import app_config

        app_config.set("retention.mode", "cascade")
        app_config.set("retention.days", None)
        app_config.set("retention.max_gb", 1)
        app_config.set("retention.protect_favorites", False)

        now = datetime.now(timezone.utc)
        row = Video(
            processor_version="test",
            start_time=now - timedelta(days=1),
            end_time=now,
            video_path="data/recordings/2026/06/01/video.mp4",
            favorite=False,
        )
        db.session.add(row)
        db.session.commit()

        with patch("services.retention_service._get_recordings_size_gb", return_value=50.0):
            pending, reason = retention_deletion_pending(mode="cascade")

        assert pending is True
        assert reason == "max_gb"


def test_pending_false_when_max_gb_exceeded_only_favorites(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    rec_root.mkdir(parents=True)
    monkeypatch.setattr("services.retention_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.retention_service._recordings_dir", lambda: str(rec_root))

    with app.app_context():
        from app_config.app_config import app_config

        app_config.set("retention.mode", "cascade")
        app_config.set("retention.days", None)
        app_config.set("retention.max_gb", 1)
        app_config.set("retention.protect_favorites", True)

        now = datetime.now(timezone.utc)
        row = Video(
            processor_version="test",
            start_time=now - timedelta(days=1),
            end_time=now,
            video_path="data/recordings/2026/06/01/video.mp4",
            favorite=True,
        )
        db.session.add(row)
        db.session.commit()

        with patch("services.retention_service._get_recordings_size_gb", return_value=50.0):
            pending, reason = retention_deletion_pending(mode="cascade")

        assert pending is False
        assert reason == ""
