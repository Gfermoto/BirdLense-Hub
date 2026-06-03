"""Sessions on disk with video.mp4 but no active Video row (retention/finalize drift)."""

from __future__ import annotations

import os
from typing import Any

from models import Video, db
from util import recordings_dir


def _db_video_path_for_mp4(mp4_path: str, rec_dir: str) -> str:
    rel = os.path.relpath(mp4_path, rec_dir)
    return os.path.normpath(f"data/recordings/{rel}").replace("\\", "/")


def summarize_orphan_recording_files(*, sample_limit: int = 5) -> dict[str, Any]:
    """Count recording session dirs whose video.mp4 is not referenced by any Video row."""
    rec_dir = recordings_dir()
    if not rec_dir or not os.path.isdir(rec_dir):
        return {
            "orphan_session_count": 0,
            "orphan_bytes": 0,
            "sample_paths": [],
        }

    db_paths: set[str] = set()
    for (vp,) in db.session.query(Video.video_path).filter(Video.video_path.isnot(None)).all():
        if vp:
            db_paths.add(os.path.normpath(str(vp)).replace("\\", "/"))

    orphan_count = 0
    orphan_bytes = 0
    samples: list[str] = []

    for root, _dirs, files in os.walk(rec_dir):
        if "video.mp4" not in files:
            continue
        mp4 = os.path.join(root, "video.mp4")
        rel_norm = _db_video_path_for_mp4(mp4, rec_dir)
        if rel_norm in db_paths:
            continue
        orphan_count += 1
        try:
            orphan_bytes += os.path.getsize(mp4)
        except OSError:
            pass
        if len(samples) < sample_limit:
            samples.append(rel_norm)

    return {
        "orphan_session_count": orphan_count,
        "orphan_bytes": orphan_bytes,
        "sample_paths": samples,
    }
