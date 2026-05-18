#!/usr/bin/env python3
"""Seed /labelling queue from existing DB data (P0 emergency helper)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _ensure_active_learning_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_learning_case (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          video_id INTEGER,
          video_species_id INTEGER,
          camera_id TEXT,
          reason_code TEXT NOT NULL,
          confidence REAL,
          blind_score REAL,
          fallback_ratio REAL,
          status TEXT NOT NULL DEFAULT 'pending',
          payload_json TEXT,
          export_tag TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_active_learning_case_unique
        ON active_learning_case(video_species_id, reason_code)
        """
    )


def seed_queue(
    db_path: Path,
    *,
    max_video_cases: int = 120,
    max_runtime_cases: int = 120,
) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_active_learning_table(conn)

    created = 0
    skipped = 0

    # Seed from recent video species rows (media-backed cases).
    try:
        rows = conn.execute(
            """
            SELECT
              vs.id AS video_species_id,
              vs.video_id,
              vs.confidence,
              vs.track_id,
              vs.frames,
              COALESCE(vs.detection_provider, 'legacy') AS detection_provider
            FROM video_species vs
            JOIN video v ON v.id = vs.video_id
            WHERE v.deleted_at IS NULL
              AND vs.source = 'video'
              AND vs.frames IS NOT NULL
              AND TRIM(vs.frames) != ''
            ORDER BY v.start_time DESC, vs.id DESC
            LIMIT ?
            """,
            (int(max_video_cases),),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for row in rows:
        payload = {
            'seed_source': 'recent_video_species',
            'track_id': row['track_id'],
            'frames': json.loads(row['frames']) if row['frames'] else None,
            'detection_provider': row['detection_provider'],
        }
        try:
            conn.execute(
                """
                INSERT INTO active_learning_case(
                  video_id, video_species_id, camera_id, reason_code,
                  confidence, blind_score, fallback_ratio, status, payload_json
                ) VALUES(?, ?, NULL, 'seed_recent_tracklet', ?, NULL, NULL, 'pending', ?)
                """,
                (
                    int(row['video_id']),
                    int(row['video_species_id']),
                    float(row['confidence']) if row['confidence'] is not None else None,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            created += 1
        except sqlite3.IntegrityError:
            skipped += 1

    # Seed from telemetry blind/fallback runtime rows.
    try:
        runtime_rows = conn.execute(
            """
            SELECT id, created_at, camera_id, payload_json
            FROM session_runtime_metrics
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(max_runtime_cases),),
        ).fetchall()
    except sqlite3.OperationalError:
        runtime_rows = []
    for row in runtime_rows:
        payload = json.loads(row['payload_json'] or '{}')
        blind_score = payload.get('yolo_blind_score')
        yolo = int(payload.get('yolo_frames_ran') or 0)
        fr_only = int(payload.get('session_extended_by_frigate_only') or 0)
        fallback_ratio = (float(fr_only) / float(yolo)) if yolo > 0 else None
        reason = None
        if blind_score is not None and float(blind_score) >= 0.5:
            reason = 'seed_yolo_blind'
        elif fallback_ratio is not None and float(fallback_ratio) >= 0.35:
            reason = 'seed_frigate_only'
        if reason is None:
            continue

        # Best-effort link to latest video for media preview.
        vrow = conn.execute(
            """
            SELECT id
            FROM video
            WHERE deleted_at IS NULL
            ORDER BY start_time DESC
            LIMIT 1
            """
        ).fetchone()
        video_id = int(vrow['id']) if vrow else None
        try:
            conn.execute(
                """
                INSERT INTO active_learning_case(
                  video_id, video_species_id, camera_id, reason_code,
                  confidence, blind_score, fallback_ratio, status, payload_json
                ) VALUES(?, NULL, ?, ?, NULL, ?, ?, 'pending', ?)
                """,
                (
                    video_id,
                    row['camera_id'],
                    reason,
                    float(blind_score) if blind_score is not None else None,
                    float(fallback_ratio) if fallback_ratio is not None else None,
                    json.dumps(
                        {
                            'seed_source': 'runtime_metrics',
                            'runtime_id': int(row['id']),
                            'created_at': row['created_at'],
                            'blind_score': blind_score,
                            'fallback_ratio': fallback_ratio,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            created += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()
    conn.close()
    return {'created': created, 'skipped': skipped}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', default='app/data/db/birdlense.db')
    ap.add_argument('--max-video-cases', type=int, default=120)
    ap.add_argument('--max-runtime-cases', type=int, default=120)
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.is_file():
        raise SystemExit(f'DB not found: {db_path}')
    out = seed_queue(
        db_path,
        max_video_cases=max(10, int(args.max_video_cases)),
        max_runtime_cases=max(10, int(args.max_runtime_cases)),
    )
    print(json.dumps({'ok': True, 'db': str(db_path), **out}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
