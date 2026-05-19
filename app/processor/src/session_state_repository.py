"""Persistent session/runtime state for processor (SQLite-backed)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
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
    _maintenance_lock = threading.Lock()
    _last_maintenance_epoch_s = 0.0
    _last_vacuum_epoch_s = 0.0

    """Repository pattern for runtime session metrics and detector health events."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _db_path()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    @staticmethod
    def _execute_with_retry(
        con: sqlite3.Connection,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        retries: int = 3,
        retry_delay_s: float = 0.08,
    ) -> sqlite3.Cursor:
        last_exc: Exception | None = None
        for attempt in range(max(1, retries)):
            try:
                return con.execute(query, params)
            except sqlite3.OperationalError as exc:
                last_exc = exc
                msg = str(exc).lower()
                if "locked" not in msg and "busy" not in msg:
                    raise
                if attempt >= retries - 1:
                    raise
                time.sleep(retry_delay_s * (attempt + 1))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("sqlite execute failed without exception")

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
                """
                CREATE TABLE IF NOT EXISTS analytics_visit_hourly (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bucket_hour TEXT NOT NULL,
                    camera_id TEXT,
                    detections INTEGER NOT NULL DEFAULT 0,
                    yolo_rows INTEGER NOT NULL DEFAULT 0,
                    frigate_rows INTEGER NOT NULL DEFAULT 0,
                    blind_confirmed_sessions INTEGER NOT NULL DEFAULT 0,
                    avg_confidence REAL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS active_learning_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    camera_id TEXT,
                    reason_code TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'info',
                    status TEXT NOT NULL DEFAULT 'pending',
                    payload_json TEXT
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
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_analytics_visit_hourly_bucket ON analytics_visit_hourly(bucket_hour, camera_id)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_alb_created ON active_learning_buffer(created_at DESC)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_alb_reason_created ON active_learning_buffer(reason_code, created_at DESC)"
            )
            con.commit()

    def save_session_runtime(self, summary: dict[str, Any]) -> int:
        camera_id = str(summary.get("triggered_camera") or "").strip() or None
        blind = bool(summary.get("yolo_blind_confirmed"))
        with self._connect() as con:
            cur = self._execute_with_retry(
                con,
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
            cur = self._execute_with_retry(
                con,
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

    def append_active_learning_buffer(
        self,
        *,
        reason_code: str,
        camera_id: str | None = None,
        severity: str = "info",
        status: str = "pending",
        payload: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as con:
            cur = self._execute_with_retry(
                con,
                """
                INSERT INTO active_learning_buffer(
                    created_at, camera_id, reason_code, severity, status, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now_iso(),
                    (str(camera_id or "").strip() or None),
                    str(reason_code or "").strip() or "unknown",
                    str(severity or "info").strip() or "info",
                    str(status or "pending").strip() or "pending",
                    json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")),
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
                self._execute_with_retry(
                    con,
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

    def latest_health_event(
        self,
        *,
        event_type: str,
        camera_id: str | None,
    ) -> sqlite3.Row | None:
        cam = (str(camera_id or "").strip() or None)
        where = "event_type = ?"
        params: list[Any] = [str(event_type).strip()]
        if cam is not None:
            where += " AND camera_id = ?"
            params.append(cam)
        with self._connect() as con:
            row = self._execute_with_retry(
                con,
                f"""
                SELECT *
                FROM detector_health_events
                WHERE {where}
                ORDER BY id DESC
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()
        return row

    def is_blind_confirmed(
        self,
        *,
        camera_id: str | None,
        min_recent_sessions: int = 3,
        min_yolo_frames: int = 1,
        min_frigate_only_frames: int = 1,
        min_duration_seconds: float = 0.0,
        min_effective_fps: float = 1.0,
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
            duration_floor = float(max(0.0, min_duration_seconds))
            fps_floor = float(max(0.1, min_effective_fps))
            duration_based_min_frames = int(max(1, round(duration_floor * fps_floor)))
            required_frames = int(max(1, min(int(max(1, min_yolo_frames)), duration_based_min_frames)))
            if (
                yolo_ran < required_frames
                or raw_total > 0
                or ext < int(max(1, min_frigate_only_frames))
                or duration_s < duration_floor
            ):
                return False
        return True

    def run_retention_and_compaction(
        self,
        *,
        runtime_retention_days: int,
        health_retention_days: int,
        do_analyze: bool = True,
        do_vacuum: bool = False,
    ) -> dict[str, int]:
        runtime_days = max(1, int(runtime_retention_days))
        health_days = max(1, int(health_retention_days))
        runtime_cutoff_sql = (
            f"datetime('now', '-{runtime_days} days')",
            f"datetime('now', '-{health_days} days')",
        )
        with self._connect() as con:
            self._execute_with_retry(
                con,
                """
                INSERT INTO analytics_visit_hourly(
                    bucket_hour, camera_id, detections, yolo_rows, frigate_rows,
                    blind_confirmed_sessions, avg_confidence, updated_at
                )
                SELECT
                    strftime('%Y-%m-%dT%H:00:00Z', created_at) AS bucket_hour,
                    camera_id,
                    COUNT(*) AS detections,
                    SUM(CASE WHEN yolo_raw_boxes_total > 0 THEN 1 ELSE 0 END) AS yolo_rows,
                    SUM(CASE WHEN session_extended_by_frigate_only > 0 THEN 1 ELSE 0 END) AS frigate_rows,
                    SUM(CASE WHEN yolo_blind_confirmed = 1 THEN 1 ELSE 0 END) AS blind_confirmed_sessions,
                    AVG(CASE WHEN yolo_accepted_boxes_total > 0 THEN 1.0 ELSE 0.0 END) AS avg_confidence,
                    ?
                FROM session_runtime_metrics
                WHERE datetime(created_at) >= datetime('now', '-2 days')
                GROUP BY 1, 2
                ON CONFLICT(bucket_hour, camera_id) DO UPDATE SET
                    detections=excluded.detections,
                    yolo_rows=excluded.yolo_rows,
                    frigate_rows=excluded.frigate_rows,
                    blind_confirmed_sessions=excluded.blind_confirmed_sessions,
                    avg_confidence=excluded.avg_confidence,
                    updated_at=excluded.updated_at
                """,
                (_utc_now_iso(),),
            )
            cur1 = self._execute_with_retry(
                con,
                f"""
                DELETE FROM session_runtime_metrics
                WHERE datetime(created_at) < {runtime_cutoff_sql[0]}
                """,
            )
            cur2 = self._execute_with_retry(
                con,
                f"""
                DELETE FROM detector_health_events
                WHERE datetime(created_at) < {runtime_cutoff_sql[1]}
                """,
            )
            deleted_runtime = int(cur1.rowcount or 0)
            deleted_health = int(cur2.rowcount or 0)
            if do_analyze:
                self._execute_with_retry(con, "ANALYZE session_runtime_metrics")
                self._execute_with_retry(con, "ANALYZE detector_health_events")
            if do_vacuum:
                self._execute_with_retry(con, "VACUUM")
            con.commit()
        return {
            "deleted_runtime_rows": deleted_runtime,
            "deleted_health_rows": deleted_health,
            "did_analyze": 1 if do_analyze else 0,
            "did_vacuum": 1 if do_vacuum else 0,
        }

    def run_maintenance_if_due(self, *, app_config_obj) -> dict[str, int] | None:
        interval_min = int(app_config_obj.get("retention.runtime_metrics_maintenance_interval_minutes") or 60)
        runtime_days = int(app_config_obj.get("retention.runtime_metrics_days") or 14)
        health_days = int(app_config_obj.get("retention.detector_health_days") or 30)
        vacuum_hours = int(app_config_obj.get("retention.runtime_metrics_vacuum_interval_hours") or 12)
        analyze_enabled = bool(app_config_obj.get("retention.runtime_metrics_analyze_enabled", True))
        now = time.time()
        with self._maintenance_lock:
            due = (now - float(self._last_maintenance_epoch_s)) >= max(60.0, float(interval_min) * 60.0)
            if not due:
                return None
            do_vacuum = (now - float(self._last_vacuum_epoch_s)) >= max(300.0, float(vacuum_hours) * 3600.0)
            res = self.run_retention_and_compaction(
                runtime_retention_days=runtime_days,
                health_retention_days=health_days,
                do_analyze=analyze_enabled,
                do_vacuum=do_vacuum,
            )
            self._last_maintenance_epoch_s = now
            if do_vacuum:
                self._last_vacuum_epoch_s = now
            return res
