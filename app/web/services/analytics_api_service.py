"""Analytics API data builders for trajectories, heatmap and visits timeseries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from models import db


def _parse_iso(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _as_utc_iso(dt: datetime) -> str:
    if isinstance(dt, str):
        parsed = _parse_iso(dt)
        if parsed is None:
            return dt
        dt = parsed
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _session_runtime_has_column(column_name: str) -> bool:
    try:
        rows = db.session.execute(
            text("PRAGMA table_info(session_runtime_metrics)")
        ).mappings()
        return any(str(r.get("name") or "") == column_name for r in rows)
    except Exception:
        return False


def fetch_trajectories(*, start_iso: str | None, end_iso: str | None, limit: int = 250) -> dict[str, Any]:
    start_dt = _parse_iso(start_iso)
    end_dt = _parse_iso(end_iso)
    params: dict[str, Any] = {"limit": max(1, min(int(limit), 1000))}
    where = ["vs.source = 'video'"]
    if start_dt is not None:
        where.append("v.start_time >= :start_time")
        params["start_time"] = start_dt
    if end_dt is not None:
        where.append("v.end_time <= :end_time")
        params["end_time"] = end_dt
    rows = db.session.execute(
        text(
            f"""
            SELECT
              vs.id AS video_species_id,
              vs.video_id,
              vs.track_id,
              vs.confidence,
              COALESCE(vs.detection_provider, 'legacy') AS detection_provider,
              v.start_time AS video_start_time,
              v.end_time AS video_end_time,
              s.name AS species_name,
              vs.frames
            FROM video_species vs
            JOIN video v ON v.id = vs.video_id
            LEFT JOIN species s ON s.id = vs.species_id
            WHERE {' AND '.join(where)}
            ORDER BY v.start_time DESC, vs.id DESC
            LIMIT :limit
            """  # nosec B608
        ),
        params,
    ).mappings()
    items = []
    for row in rows:
        frames = []
        try:
            parsed = json.loads(str(row["frames"] or "[]"))
            if isinstance(parsed, list):
                frames = parsed
        except Exception:
            frames = []
        points = []
        for fr in frames:
            if not isinstance(fr, dict):
                continue
            bbox = fr.get("bbox")
            t_rel = fr.get("t")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            try:
                x1, y1, x2, y2 = [float(v) for v in bbox]
                t_rel_f = float(t_rel or 0.0)
            except (TypeError, ValueError):
                continue
            points.append(
                {
                    "t_rel_s": round(t_rel_f, 3),
                    "cx": round((x1 + x2) / 2.0, 6),
                    "cy": round((y1 + y2) / 2.0, 6),
                    "bbox": [round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)],
                }
            )
        items.append(
            {
                "video_species_id": int(row["video_species_id"]),
                "video_id": int(row["video_id"]),
                "track_id": row["track_id"],
                "species_name": row["species_name"],
                "confidence": float(row["confidence"] or 0.0),
                "detection_provider": row["detection_provider"],
                "video_start_time": _as_utc_iso(row["video_start_time"]),
                "video_end_time": _as_utc_iso(row["video_end_time"]),
                "points": points,
            }
        )
    return {"items": items, "count": len(items)}


def fetch_heatmap(*, start_iso: str | None, end_iso: str | None, grid: int = 12) -> dict[str, Any]:
    data = fetch_trajectories(start_iso=start_iso, end_iso=end_iso, limit=1200)
    g = max(4, min(int(grid), 64))
    cells = [[0 for _ in range(g)] for _ in range(g)]
    for item in data["items"]:
        for p in item.get("points", []):
            try:
                cx = max(0.0, min(0.999999, float(p["cx"])))
                cy = max(0.0, min(0.999999, float(p["cy"])))
            except (TypeError, ValueError, KeyError):
                continue
            x = int(cx * g)
            y = int(cy * g)
            cells[y][x] += 1
    flat = [v for row in cells for v in row]
    return {
        "grid_size": g,
        "max_hits": max(flat) if flat else 0,
        "total_hits": sum(flat),
        "cells": cells,
    }


def fetch_visits_timeseries(*, start_iso: str | None, end_iso: str | None, bucket: str = "hour") -> dict[str, Any]:
    start_dt = _parse_iso(start_iso)
    end_dt = _parse_iso(end_iso)
    bucket_norm = "day" if str(bucket).strip().lower() == "day" else "hour"
    trunc_expr = "strftime('%Y-%m-%dT%H:00:00Z', v.start_time)" if bucket_norm == "hour" else "date(v.start_time)"
    params: dict[str, Any] = {}
    where = ["vs.source = 'video'"]
    if start_dt is not None:
        where.append("v.start_time >= :start_time")
        params["start_time"] = start_dt
    if end_dt is not None:
        where.append("v.end_time <= :end_time")
        params["end_time"] = end_dt

    rows = db.session.execute(
        text(
            f"""
            SELECT
              {trunc_expr} AS bucket_ts,
              COUNT(*) AS detections,
              SUM(CASE WHEN COALESCE(vs.detection_provider, '') = 'yolo' THEN 1 ELSE 0 END) AS yolo_rows,
              SUM(CASE WHEN COALESCE(vs.detection_provider, '') = 'frigate' THEN 1 ELSE 0 END) AS frigate_rows,
              AVG(vs.confidence) AS avg_confidence
            FROM video_species vs
            JOIN video v ON v.id = vs.video_id
            WHERE {' AND '.join(where)}
            GROUP BY bucket_ts
            ORDER BY bucket_ts ASC
            """  # nosec B608
        ),
        params,
    ).mappings()
    items = []
    for row in rows:
        detections = int(row["detections"] or 0)
        frigate_rows = int(row["frigate_rows"] or 0)
        items.append(
            {
                "bucket": str(row["bucket_ts"]),
                "detections": detections,
                "yolo_rows": int(row["yolo_rows"] or 0),
                "frigate_rows": frigate_rows,
                "avg_confidence": round(float(row["avg_confidence"] or 0.0), 4),
                "frigate_ratio": round(float(frigate_rows) / float(detections), 4) if detections > 0 else 0.0,
            }
        )
    return {"bucket": bucket_norm, "items": items, "count": len(items)}


def fetch_quality_health(*, hours: int = 24, events_limit: int = 30) -> dict[str, Any]:
    h = max(1, min(int(hours), 168))
    lim = max(1, min(int(events_limit), 200))
    latency_col_expr = (
        "trigger_to_first_bbox_latency_s"
        if _session_runtime_has_column("trigger_to_first_bbox_latency_s")
        else "NULL AS trigger_to_first_bbox_latency_s"
    )
    finalize_duration_col_expr = (
        "finalize_duration_ms"
        if _session_runtime_has_column("finalize_duration_ms")
        else "NULL AS finalize_duration_ms"
    )
    runtime_rows = db.session.execute(
        text(
            f"""
            SELECT
              created_at,
              yolo_raw_boxes_total,
              session_extended_by_frigate_only,
              {latency_col_expr},
              {finalize_duration_col_expr},
              payload_json
            FROM session_runtime_metrics
            WHERE datetime(created_at) >= datetime('now', :window)
            ORDER BY id DESC
            LIMIT 600
            """  # nosec B608
        ),
        {"window": f"-{h} hours"},
    ).mappings()
    blind_scores: list[float] = []
    first_bbox_latencies: list[float] = []
    finalize_durations_ms: list[float] = []
    ingest_pruned_events = 0
    ingest_empty_contract_events = 0
    ingest_pruned_rows_total = 0
    ingest_pruned_frames_total = 0
    ingest_pruned_rows_total_7d = 0
    frigate_catches_missed_birds_sessions = 0
    fallback_sessions = 0
    total_sessions = 0
    for row in runtime_rows:
        total_sessions += 1
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except Exception:
            payload = {}
        latency_s = row.get("trigger_to_first_bbox_latency_s")
        latency_added = False
        try:
            if latency_s is not None:
                parsed_latency = float(latency_s)
                if parsed_latency > 0:
                    first_bbox_latencies.append(parsed_latency)
                    latency_added = True
        except (TypeError, ValueError):
            pass
        if not latency_added:
            fallback_latency = payload.get("trigger_to_first_bbox_latency_s")
            try:
                if fallback_latency is not None:
                    parsed_latency = float(fallback_latency)
                    if parsed_latency > 0:
                        first_bbox_latencies.append(parsed_latency)
            except (TypeError, ValueError):
                pass
        finalize_duration = row.get("finalize_duration_ms")
        finalize_added = False
        try:
            if finalize_duration is not None:
                parsed_finalize = float(finalize_duration)
                if parsed_finalize > 0:
                    finalize_durations_ms.append(parsed_finalize)
                    finalize_added = True
        except (TypeError, ValueError):
            pass
        if not finalize_added and payload.get("finalize_duration_ms") is not None:
            try:
                payload_finalize = float(payload.get("finalize_duration_ms"))
                if payload_finalize > 0:
                    finalize_durations_ms.append(payload_finalize)
            except (TypeError, ValueError):
                pass
        score = payload.get("yolo_blind_score")
        try:
            if score is not None:
                blind_scores.append(float(score))
        except (TypeError, ValueError):
            pass
        if int(payload.get("session_extended_by_frigate_only") or 0) > 0:
            fallback_sessions += 1
        yolo_raw_total = int(row.get("yolo_raw_boxes_total") or 0)
        frigate_only_total = int(row.get("session_extended_by_frigate_only") or 0)
        if frigate_only_total > 0 and yolo_raw_total == 0:
            frigate_catches_missed_birds_sessions += 1
    try:
        runtime_rows_7d = db.session.execute(
            text(
                """
                SELECT
                  yolo_raw_boxes_total,
                  session_extended_by_frigate_only
                FROM session_runtime_metrics
                WHERE datetime(created_at) >= datetime('now', '-168 hours')
                ORDER BY id DESC
                LIMIT 3000
                """
            ),
        ).mappings()
    except Exception:
        runtime_rows_7d = []
    total_sessions_7d = 0
    frigate_catches_missed_birds_sessions_7d = 0
    for row in runtime_rows_7d:
        total_sessions_7d += 1
        yolo_raw_total = int(row.get("yolo_raw_boxes_total") or 0)
        frigate_only_total = int(
            row.get("session_extended_by_frigate_only") or 0
        )
        if frigate_only_total > 0 and yolo_raw_total == 0:
            frigate_catches_missed_birds_sessions_7d += 1

    try:
        ingest_rows = db.session.execute(
            text(
                """
                SELECT data
                FROM activity_log
                WHERE type = 'ingest_gate'
                  AND datetime(created_at) >= datetime('now', :window)
                ORDER BY id DESC
                LIMIT 1000
                """
            ),
            {"window": f"-{h} hours"},
        ).mappings()
    except Exception:
        ingest_rows = []
    for row in ingest_rows:
        try:
            payload = json.loads(str(row.get("data") or "{}"))
        except Exception:
            payload = {}
        reason = str(payload.get("reason") or "").strip().lower()
        if reason == "video_bbox_track_contract_pruned":
            ingest_pruned_events += 1
            ingest_pruned_rows_total += int(
                payload.get("dropped_missing_frames") or 0
            )
            ingest_pruned_rows_total += int(
                payload.get("dropped_empty_bbox") or 0
            )
            ingest_pruned_frames_total += int(
                payload.get("pruned_invalid_bbox_frames") or 0
            )
        elif reason == "video_bbox_track_contract_empty":
            ingest_empty_contract_events += 1
    try:
        ingest_rows_7d = db.session.execute(
            text(
                """
                SELECT data
                FROM activity_log
                WHERE type = 'ingest_gate'
                  AND datetime(created_at) >= datetime('now', '-168 hours')
                ORDER BY id DESC
                LIMIT 2000
                """
            ),
        ).mappings()
    except Exception:
        ingest_rows_7d = []
    for row in ingest_rows_7d:
        try:
            payload = json.loads(str(row.get("data") or "{}"))
        except Exception:
            payload = {}
        reason = str(payload.get("reason") or "").strip().lower()
        if reason != "video_bbox_track_contract_pruned":
            continue
        ingest_pruned_rows_total_7d += int(
            payload.get("dropped_missing_frames") or 0
        )
        ingest_pruned_rows_total_7d += int(
            payload.get("dropped_empty_bbox") or 0
        )

    heal_rows = db.session.execute(
        text(
            """
            SELECT created_at, event_type, severity, details_json
            FROM detector_health_events
            WHERE datetime(created_at) >= datetime('now', :window)
              AND (
                event_type='yolo_self_heal_action'
                OR event_type='yolo_blind_confirmed'
                OR event_type='yolo_blind_recovered'
              )
            ORDER BY id DESC
            LIMIT :lim
            """
        ),
        {"window": f"-{h} hours", "lim": lim},
    ).mappings()
    events = []
    action_counts = {"soft_clear": 0, "reinit": 0, "restart": 0, "alert": 0}
    infer_p95_samples: list[float] = []
    for row in heal_rows:
        details_raw = str(row.get("details_json") or "{}")
        try:
            details = json.loads(details_raw)
        except Exception:
            details = {}
        action = str(details.get("action") or "").strip()
        if action in action_counts:
            action_counts[action] += 1
        try:
            p95 = (
                details.get("runtime_stats", {})
                .get("latency_ms", {})
                .get("frame_processor_detect_p95")
            )
            if p95 is not None:
                infer_p95_samples.append(float(p95))
        except (TypeError, ValueError, AttributeError):
            pass
        events.append(
            {
                "created_at": _as_utc_iso(row["created_at"]),
                "event_type": row["event_type"],
                "severity": row["severity"],
                "action": action or None,
                "dump_refs": details.get("dump_refs"),
            }
        )

    blind_score_current = blind_scores[0] if blind_scores else 0.0
    blind_score_avg = (
        (sum(blind_scores) / float(len(blind_scores)))
        if blind_scores
        else 0.0
    )
    fallback_ratio = (
        (float(fallback_sessions) / float(total_sessions))
        if total_sessions > 0
        else 0.0
    )
    infer_p95_avg = (
        (sum(infer_p95_samples) / float(len(infer_p95_samples)))
        if infer_p95_samples
        else None
    )
    first_bbox_latency_p95_s = (
        sorted(first_bbox_latencies)[
            max(0, int(len(first_bbox_latencies) * 0.95) - 1)
        ]
        if first_bbox_latencies
        else None
    )
    finalize_duration_p95_ms = (
        sorted(finalize_durations_ms)[
            max(0, int(len(finalize_durations_ms) * 0.95) - 1)
        ]
        if finalize_durations_ms
        else None
    )
    ingest_pruned_rows_per_hour = (
        float(ingest_pruned_rows_total) / float(max(1, h))
    )
    ingest_pruned_rows_per_hour_7d_baseline = (
        float(ingest_pruned_rows_total_7d) / float(24 * 7)
    )
    ingest_pruned_rows_per_hour_delta_vs_7d = (
        ingest_pruned_rows_per_hour - ingest_pruned_rows_per_hour_7d_baseline
    )
    frigate_catches_missed_birds_rate = (
        (
            float(frigate_catches_missed_birds_sessions)
            / float(total_sessions)
        )
        if total_sessions > 0
        else 0.0
    )
    frigate_catches_missed_birds_rate_7d_baseline = (
        (
            float(frigate_catches_missed_birds_sessions_7d)
            / float(total_sessions_7d)
        )
        if total_sessions_7d > 0
        else 0.0
    )
    frigate_catches_missed_birds_rate_delta_vs_7d = (
        frigate_catches_missed_birds_rate
        - frigate_catches_missed_birds_rate_7d_baseline
    )
    return {
        "window_hours": h,
        "health_kpis": {
            "blind_score_current": round(blind_score_current, 4),
            "blind_score_avg": round(blind_score_avg, 4),
            "fallback_ratio": round(fallback_ratio, 4),
            "self_heal_action_counts": action_counts,
            "inference_latency_p95_ms_avg": (
                round(infer_p95_avg, 2)
                if infer_p95_avg is not None
                else None
            ),
            "trigger_to_first_bbox_latency_p95_s": (
                round(float(first_bbox_latency_p95_s), 4)
                if first_bbox_latency_p95_s is not None
                else None
            ),
            "finalize_duration_p95_ms": (
                round(float(finalize_duration_p95_ms), 4)
                if finalize_duration_p95_ms is not None
                else None
            ),
            "ingest_bbox_contract_pruned_events": int(ingest_pruned_events),
            "ingest_bbox_contract_empty_events": int(
                ingest_empty_contract_events
            ),
            "ingest_bbox_contract_pruned_rows_total": int(
                ingest_pruned_rows_total
            ),
            "ingest_bbox_contract_pruned_frames_total": int(
                ingest_pruned_frames_total
            ),
            "ingest_bbox_contract_pruned_rows_per_session": (
                round(
                    float(ingest_pruned_rows_total) / float(total_sessions),
                    4,
                )
                if total_sessions > 0
                else None
            ),
            "ingest_bbox_contract_pruned_rows_per_hour": round(
                ingest_pruned_rows_per_hour,
                4,
            ),
            "ingest_bbox_contract_pruned_rows_per_hour_7d_baseline": round(
                ingest_pruned_rows_per_hour_7d_baseline,
                4,
            ),
            "ingest_bbox_contract_pruned_rows_per_hour_delta_vs_7d": round(
                ingest_pruned_rows_per_hour_delta_vs_7d,
                4,
            ),
            "frigate_catches_missed_birds_sessions": int(
                frigate_catches_missed_birds_sessions
            ),
            "frigate_catches_missed_birds_rate": round(
                frigate_catches_missed_birds_rate,
                4,
            ),
            "frigate_catches_missed_birds_rate_7d_baseline": round(
                frigate_catches_missed_birds_rate_7d_baseline,
                4,
            ),
            "frigate_catches_missed_birds_rate_delta_vs_7d": round(
                frigate_catches_missed_birds_rate_delta_vs_7d,
                4,
            ),
        },
        "recent_events": events,
    }
