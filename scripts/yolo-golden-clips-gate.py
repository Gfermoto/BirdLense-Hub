#!/usr/bin/env python3
"""Quality gate: golden clip 1819 must produce yolo_frames_with_tracks > 0 (SOTA-05)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _summary_from_db(db_path: Path, video_id: int) -> dict | None:
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            """
            SELECT yolo_frames_with_tracks, yolo_raw_boxes_total, yolo_frames_ran, payload_json
            FROM session_runtime_metrics
            ORDER BY id DESC
            LIMIT 800
            """
        ).fetchall()
    finally:
        con.close()
    for tracks, raw, ran, payload_raw in rows:
        try:
            payload = json.loads(str(payload_raw or "{}"))
        except json.JSONDecodeError:
            payload = {}
        vid = payload.get("video_id") or payload.get("recording_video_id")
        try:
            if int(vid or -1) != int(video_id):
                continue
        except (TypeError, ValueError):
            continue
        return {
            "yolo_frames_with_tracks": int(tracks or 0),
            "yolo_raw_boxes_total": int(raw or 0),
            "yolo_frames_ran": int(ran or 0),
            **payload,
        }
    return None


def assert_has_tracks(summary: dict, *, label: str) -> None:
    tracks = int(summary.get("yolo_frames_with_tracks") or 0)
    if tracks <= 0:
        raise SystemExit(
            f"FAIL {label}: yolo_frames_with_tracks=0 "
            f"(raw={summary.get('yolo_raw_boxes_total')}, ran={summary.get('yolo_frames_ran')})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="YOLO golden clips gate (1819 birds, 1816 noise)")
    parser.add_argument("--db", default=os.environ.get("BIRDLENSE_DB", str(REPO / "app/data/db/birdlense.db")))
    parser.add_argument("--video-id-birds", type=int, default=int(os.environ.get("YOLO_GOLDEN_VIDEO_1819", "1819")))
    parser.add_argument("--video-id-noise", type=int, default=int(os.environ.get("YOLO_GOLDEN_VIDEO_1816", "1816")))
    parser.add_argument("--clip-1819", default=os.environ.get("YOLO_GOLDEN_CLIP_1819", "").strip())
    parser.add_argument("--skip-db", action="store_true")
    args = parser.parse_args()

    if args.clip_1819:
        sys.path.insert(0, str(REPO / "app/processor/src"))
        from track_regenerator import process_video_for_tracks  # type: ignore

        detections = process_video_for_tracks(args.clip_1819)
        summary = {
            "yolo_frames_with_tracks": 1 if detections else 0,
            "yolo_raw_boxes_total": len(detections),
            "yolo_frames_ran": 1,
        }
        assert_has_tracks(summary, label="1819-regen")
        print("PASS 1819 regen: detections=", len(detections))
        return 0

    if not args.skip_db:
        db_path = Path(args.db)
        if db_path.is_file():
            s1819 = _summary_from_db(db_path, args.video_id_birds)
            if s1819:
                assert_has_tracks(s1819, label="1819-db")
                print("PASS 1819 db: tracks=", s1819.get("yolo_frames_with_tracks"))
                s1816 = _summary_from_db(db_path, args.video_id_noise)
                if s1816:
                    print(
                        "INFO 1816 noise: tracks=",
                        s1816.get("yolo_frames_with_tracks"),
                        "raw=",
                        s1816.get("yolo_raw_boxes_total"),
                    )
                return 0
            print(
                f"WARN: no session_runtime_metrics for video_id={args.video_id_birds}; running unit gate",
                file=sys.stderr,
            )
        else:
            print(f"WARN: db not found: {db_path}", file=sys.stderr)

    # Fallback: unit-test logic only
    proc_tests = REPO / "app/processor/tests/test_yolo_golden_clips_gate.py"
    if not proc_tests.is_file():
        print("FAIL: no db, no clip, no tests", file=sys.stderr)
        return 1
    import subprocess

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO / "app/processor/src")
    env["SKIP_HEAVY_PROCESSOR_TESTS"] = "1"
    r = subprocess.run(
        ["python3", "-m", "pytest", str(proc_tests), "-q"],
        cwd=str(REPO / "app/processor"),
        env=env,
    )
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
