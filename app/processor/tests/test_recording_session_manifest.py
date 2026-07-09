"""Tests for recording_session_manifest (FinalizeTransaction #602)."""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import json
import os
import tempfile
from datetime import datetime, timezone

from recording_session_manifest import (
    MANIFEST_FILENAME,
    mark_persist_failed,
    mark_persist_ready,
    write_recording_started,
)


def test_manifest_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        start = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
        write_recording_started(
            tmp,
            video_path_logical="data/recordings/2026/06/03/120000/video.mp4",
            start_time=start,
            camera_id="forest",
        )
        path = os.path.join(tmp, MANIFEST_FILENAME)
        assert os.path.isfile(path)
        data = json.loads(open(path, encoding="utf-8").read())
        assert data["state"] == "recording"
        assert data["schema"] == "recording_session_manifest@v1"

        end = datetime(2026, 6, 3, 12, 0, 30, tzinfo=timezone.utc)
        mark_persist_ready(tmp, video_id=42, end_time=end)
        data = json.loads(open(path, encoding="utf-8").read())
        assert data["state"] == "ready"
        assert data["video_id"] == 42

        mark_persist_failed(tmp, reason="test", end_time=end)
        data = json.loads(open(path, encoding="utf-8").read())
        assert data["state"] == "failed"
        assert data["fail_reason"] == "test"
