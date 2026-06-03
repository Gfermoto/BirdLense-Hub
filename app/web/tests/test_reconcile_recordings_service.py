"""Tests for reconcile_recordings_service (#604)."""

import json
import os
from datetime import datetime, timezone

from models import Video, db


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
