"""Persistent session/runtime state for processor (SQLite-backed)."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from processor_support import get_data_dir


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> str:
    env = (os.environ.get("BIRDLENSE_DB_PATH") or "").strip()
    if env:
        return env
    return os.path.join(get_data_dir(), "db", "birdlense.db")


class SessionStateRepository:
    """Repository pattern for runtime session metrics and detector health events."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _db_path()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS session_runtime_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    camera_id TEXT,
                    duration_s REAL,
                    frames_seen INTEGER NOT NULL DEFAULT 0,
                    yolo_frames_ran INTEGER NOT NULL DEFAULT 0,
                    yolo_frames_with_tracks INTEGER NOT NULL DEFAULT 0,
                    yolo_frames_with_raw_boxes INTEGER NOT NULL DEFAULT 0,
                    yolo_raw_boxes_total INTEGER NOT NULL DEFAULT 0,
                    yolo_accepted_boxes_total INTEGER NOT NULL DEFAULT 0,
                    low_light_blocked_frames INTEGER NOT NULL DEFAULT 0,
                    session_extended_by_frigate_only INTEGER NOT NULL DEFAULT 0,
                    bytetrack_rows INTEGER NOT NULL DEFAULT 0,
                    post_fusion_persisted INTEGER NOT NULL DEFAULT 0,
                    rejected_decision_rows INTEGER NOT NULL DEFAULT 0,
                    mqtt_events_in_window INTEGER NOT NULL DEFAULT 0,
                    yolo_blind_confirmed INTEGER NOT NULL DEFAULT 0,
                    runtime_profile TEXT,
                    video_file_ok INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS detector_health_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    camera_id TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    details_json TEXT
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_srm_camera_created ON session_runtime_metrics(camera_id, created_at DESC)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_srm_created ON session_runtime_metrics(created_at DESC)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_dhe_camera_created ON detector_health_events(camera_id, created_at DESC)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_dhe_type_created ON detector_health_events(event_type, created_at DESC)"
            )
            con.commit()

    def save_session_runtime(self, summary: dict[str, Any]) -> int:
        camera_id = str(summary.get("triggered_camera") or "").strip() or None
        blind = bool(summary.get("yolo_blind_confirmed"))
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO session_runtime_metrics (
                    created_at, camera_id, duration_s, frames_seen, yolo_frames_ran,
                    yolo_frames_with_tracks, yolo_frames_with_raw_boxes, yolo_raw_boxes_total,
                    yolo_accepted_boxes_total, low_light_blocked_frames,
                    session_extended_by_frigate_only, bytetrack_rows, post_fusion_persisted,
                    rejected_decision_rows, mqtt_events_in_window, yolo_blind_confirmed,
                    runtime_profile, video_file_ok, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now_iso(),
                    camera_id,
                    float(summary.get("duration_s") or 0.0),
                    int(summary.get("frames_seen") or 0),
                    int(summary.get("yolo_frames_ran") or 0),
                    int(summary.get("yolo_frames_with_tracks") or 0),
                    int(summary.get("yolo_frames_with_raw_boxes") or 0),
                    int(summary.get("yolo_raw_boxes_total") or 0),
                    int(summary.get("yolo_accepted_boxes_total") or 0),
                    int(summary.get("low_light_blocked_frames") or 0),
                    int(summary.get("session_extended_by_frigate_only") or 0),
                    int(summary.get("bytetrack_rows") or 0),
                    int(summary.get("post_fusion_persisted") or 0),
                    int(summary.get("rejected_decision_rows") or 0),
                    int(summary.get("mqtt_events_in_window") or 0),
                    1 if blind else 0,
                    str(summary.get("runtime_profile") or "").strip() or None,
                    1 if bool(summary.get("video_file_ok")) else 0,
                    json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            con.commit()
            return int(cur.lastrowid)

    def append_detector_health_event(
        self,
        *,
        event_type: str,
        severity: str = "info",
        camera_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO detector_health_events(created_at, camera_id, event_type, severity, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _utc_now_iso(),
                    (str(camera_id or "").strip() or None),
                    str(event_type).strip(),
                    str(severity).strip() or "info",
                    json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            con.commit()
            return int(cur.lastrowid)

    def recent_blind_sessions(self, *, camera_id: str | None, limit: int = 6) -> list[sqlite3.Row]:
        cam = (str(camera_id or "").strip() or None)
        where = "WHERE camera_id IS NULL OR camera_id = ?" if cam is None else "WHERE camera_id = ?"
        arg = (None,) if cam is None else (cam,)
        with self._connect() as con:
            return list(
                con.execute(
                    f"""
                    SELECT *
                    FROM session_runtime_metrics
                    {where}
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (*arg, int(max(1, limit))),
                ).fetchall()
            )

    def is_blind_confirmed(
        self,
        *,
        camera_id: str | None,
        min_recent_sessions: int = 3,
        min_yolo_frames: int = 1,
        min_frigate_only_frames: int = 1,
        min_duration_seconds: float = 0.0,
    ) -> bool:
        rows = self.recent_blind_sessions(camera_id=camera_id, limit=max(min_recent_sessions, 6))
        if not rows or len(rows) < min_recent_sessions:
            return False
        checked = rows[:min_recent_sessions]
        for row in checked:
            yolo_ran = int(row["yolo_frames_ran"] or 0)
            raw_total = int(row["yolo_raw_boxes_total"] or 0)
            ext = int(row["session_extended_by_frigate_only"] or 0)
            duration_s = float(row["duration_s"] or 0.0)
            if (
                yolo_ran < int(max(1, min_yolo_frames))
                or raw_total > 0
                or ext < int(max(1, min_frigate_only_frames))
                or duration_s < float(max(0.0, min_duration_seconds))
            ):
                return False
        return True
