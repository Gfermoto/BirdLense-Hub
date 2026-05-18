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
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


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
            """
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
            """
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
