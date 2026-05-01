#!/usr/bin/env python3
"""Run benchmark-track-regen over all DB videos with historical YOLO regions."""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-step", type=int, default=5)
    parser.add_argument("--max-runtime-sec", type=int, default=150)
    parser.add_argument(
        "--report",
        default="/app/data/benchmark_openvino_openvino_yolo_db_full.json",
    )
    args = parser.parse_args()

    db_path = "/app/data/db/birdlense.db"
    out_path = args.report
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT DISTINCT v.video_path
            FROM video v
            JOIN video_species vs ON vs.video_id = v.id
            WHERE v.deleted_at IS NULL
              AND vs.detection_provider = 'yolo'
              AND vs.frames IS NOT NULL
              AND LENGTH(vs.frames) > 20
            ORDER BY v.video_path
            """
        ).fetchall()
    finally:
        con.close()

    videos: list[str] = []
    for (video_path,) in rows:
        path = "/app/" + str(video_path).lstrip("/")
        if os.path.isfile(path):
            videos.append(path)

    print(f"videos_total {len(videos)}", flush=True)

    cmd = [
        sys.executable,
        "/tmp/benchmark-track-regen.py",
        "--frame-step",
        str(args.frame_step),
        "--max-runtime-sec",
        str(args.max_runtime_sec),
        "--write-report",
        out_path,
    ]
    for path in videos:
        cmd.extend(["--video", path])

    result = subprocess.run(cmd)
    print(f"report {out_path}", flush=True)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
