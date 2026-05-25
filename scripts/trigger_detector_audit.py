#!/usr/bin/env python3
"""Аудит цепочки «триггер → запись → детектор → ingest» по SQLite activity_log.

Классификация пропущенных событий (кто виноват):
  - trigger: сессий мало / триггер opencv не сработал (нет decision_trace)
  - detector_empty: запись есть, yolo_raw_boxes=0 или accepted=0
  - detector_blind: yolo_blind_phase confirmed/suspected
  - frigate_only: продление только Frigate, Hub YOLO пустой
  - ingest: ingest_gate / битый mp4
  - ok: есть accepted боксы

Примеры::

  python3 scripts/trigger_detector_audit.py --days 3
  python3 scripts/trigger_detector_audit.py --db-path app/data/db/birdlense.db --cameras BirdBox,Forest --json-out /tmp/audit.json

На VPS::

  docker exec birdlense python3 /app/scripts/trigger_detector_audit.py --days 2 \\
    --db-path /app/data/db/birdlense.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _load_json_rows(
    conn: sqlite3.Connection,
    log_type: str,
    cutoff_iso: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT data, created_at
        FROM activity_log
        WHERE type = ? AND created_at >= ?
        ORDER BY created_at DESC
        """,
        (log_type, cutoff_iso),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for raw_data, created_at in rows:
        try:
            payload = json.loads(raw_data or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            payload["_created_at"] = created_at
            out.append(payload)
    return out


def _classify_session(trace: dict[str, Any]) -> str:
    rc = trace.get("recording_context") or {}
    runtime = rc.get("runtime_signals") or {}
    raw = _safe_int(runtime.get("yolo_raw_boxes_total"))
    accepted = _safe_int(runtime.get("yolo_accepted_boxes_total"))
    tracks = _safe_int(runtime.get("yolo_frames_with_tracks"))
    frigate_only = _safe_int(runtime.get("session_extended_by_frigate_only"))
    blind = str(runtime.get("yolo_blind_phase") or "").strip().lower()

    if blind in {"confirmed", "suspected"}:
        return "detector_blind"
    if raw <= 0 and tracks <= 0:
        return "detector_empty"
    if accepted <= 0:
        if frigate_only > 0:
            return "frigate_only"
        return "detector_empty"
    return "ok"


def build_audit(
    *,
    db_path: Path,
    days: int,
    cameras: list[str],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, int(days)))
    cutoff_iso = cutoff.isoformat()
    target = {c.strip() for c in cameras if c.strip()}

    conn = sqlite3.connect(str(db_path))
    try:
        traces = _load_json_rows(conn, "decision_trace", cutoff_iso)
        ingest_gates = _load_json_rows(conn, "ingest_gate", cutoff_iso)
        no_det = _load_json_rows(conn, "no_detection", cutoff_iso)
        opencv_rows = _load_json_rows(conn, "opencv_live", cutoff_iso)
    finally:
        conn.close()

    by_camera: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "sessions": 0,
            "verdict_counts": Counter(),
            "trigger_counts": Counter(),
            "yolo_raw_total": 0,
            "yolo_accepted_total": 0,
            "opencv_reject_top": Counter(),
            "samples": [],
        }
    )

    for trace in traces:
        rc = trace.get("recording_context") or {}
        cam = str(trace.get("camera_id") or rc.get("triggered_camera") or "").strip() or "unknown"
        if target and cam not in target:
            continue
        bucket = by_camera[cam]
        bucket["sessions"] += 1
        trigger = str(rc.get("triggered_by") or "unknown").strip().lower() or "unknown"
        bucket["trigger_counts"][trigger] += 1
        verdict = _classify_session(trace)
        bucket["verdict_counts"][verdict] += 1
        runtime = rc.get("runtime_signals") or {}
        bucket["yolo_raw_total"] += _safe_int(runtime.get("yolo_raw_boxes_total"))
        bucket["yolo_accepted_total"] += _safe_int(runtime.get("yolo_accepted_boxes_total"))
        opencv_diag = runtime.get("opencv_trigger_diagnostics") or {}
        if isinstance(opencv_diag, dict):
            rejects = opencv_diag.get("reject_reasons") or {}
            if isinstance(rejects, dict):
                for k, v in rejects.items():
                    bucket["opencv_reject_top"][str(k)] += _safe_int(v)
        if len(bucket["samples"]) < 5:
            bucket["samples"].append(
                {
                    "verdict": verdict,
                    "trigger": trigger,
                    "yolo_raw": _safe_int(runtime.get("yolo_raw_boxes_total")),
                    "yolo_accepted": _safe_int(runtime.get("yolo_accepted_boxes_total")),
                    "yolo_tracks": _safe_int(runtime.get("yolo_frames_with_tracks")),
                    "blind": runtime.get("yolo_blind_phase"),
                    "at": trace.get("_created_at"),
                }
            )

    ingest_by_cam = Counter()
    for row in ingest_gates:
        ingest_by_cam["all"] += 1

    report_cameras: dict[str, Any] = {}
    for cam, data in sorted(by_camera.items()):
        sessions = int(data["sessions"])
        verdicts = dict(data["verdict_counts"])
        miss = sessions - int(verdicts.get("ok", 0))
        dominant_miss = "none"
        if miss > 0:
            non_ok = {k: v for k, v in verdicts.items() if k != "ok"}
            if non_ok:
                dominant_miss = max(non_ok.items(), key=lambda x: x[1])[0]
        report_cameras[cam] = {
            "sessions": sessions,
            "verdict_counts": verdicts,
            "missed_sessions": miss,
            "dominant_miss_reason": dominant_miss,
            "trigger_counts": dict(data["trigger_counts"]),
            "yolo_raw_boxes_total": data["yolo_raw_total"],
            "yolo_accepted_boxes_total": data["yolo_accepted_total"],
            "opencv_reject_reasons_top": dict(
                data["opencv_reject_top"].most_common(8)
            ),
            "sample_sessions": data["samples"],
            "who_is_likely_at_fault": _fault_hint(dominant_miss, verdicts),
        }

    opencv_live_ok = len(opencv_rows) > 0
    return {
        "schema": "trigger_detector_audit@v1",
        "generated_at": now.isoformat(),
        "window_days": max(1, int(days)),
        "source_db": str(db_path.resolve()),
        "ingest_gate_events": int(ingest_by_cam["all"]),
        "no_detection_events": len(no_det),
        "opencv_live_rows_in_window": len(opencv_rows),
        "opencv_live_telemetry_ok": opencv_live_ok,
        "cameras": report_cameras,
        "how_to_read": {
            "ok": "Триггер записал, YOLO принял боксы — цепочка сработала.",
            "detector_empty": "Запись была, YOLO не дал принятых детекций — смотреть детектор/пороги/зону.",
            "detector_blind": "YOLO blind phase — детектор слеп на клипе.",
            "frigate_only": "Frigate продлил сессию, Hub YOLO пустой.",
            "trigger": "Мало сессий — триггер OpenCV/расписание/cooldown.",
            "ingest": "Смотреть ingest_gate в activity_log.",
        },
        "test_cycle": [
            "1) make trigger-detector-audit DAYS=3",
            "2) Live: MJPEG (процессор), шестерёнка → боксы триггера при движении",
            "3) Сравнить dominant_miss_reason с opencv_reject_reasons_top",
            "4) При detector_* — scripts/diag_video_detect.py по video_id из sample",
        ],
    }


def _fault_hint(dominant: str, verdicts: dict[str, int]) -> str:
    if dominant == "none":
        return "trigger_or_schedule"
    if dominant in {"detector_empty", "detector_blind"}:
        return "detector"
    if dominant == "frigate_only":
        return "detector_plus_frigate_mqtt"
    if dominant == "ok":
        return "none"
    return dominant


def _default_db() -> Path:
    p = Path(__file__).resolve().parents[1] / "app" / "data" / "db" / "birdlense.db"
    if p.is_file():
        return p
    return Path("/app/data/db/birdlense.db")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--db-path", type=Path, default=_default_db())
    parser.add_argument("--cameras", default="BirdBox,Forest")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    cams = [x.strip() for x in str(args.cameras).split(",") if x.strip()]
    report = build_audit(db_path=args.db_path, days=args.days, cameras=cams)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
