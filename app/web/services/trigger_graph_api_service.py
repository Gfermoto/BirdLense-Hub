"""Analytics: aggregated trigger graph and source-specific FP/FN metrics."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

from models import db

_PROC_SRC = Path(__file__).resolve().parents[2] / "processor" / "src"
if str(_PROC_SRC) not in sys.path:
    sys.path.insert(0, str(_PROC_SRC))

from trigger_graph import TRIGGER_NODES, aggregate_trigger_metrics  # noqa: E402


def _load_sessions_from_db(*, hours: int, camera_id: str | None, limit: int) -> list[dict[str, Any]]:
    h = max(1, min(int(hours), 168))
    lim = max(1, min(int(limit), 2000))
    params: dict[str, Any] = {"window": f"-{h} hours", "lim": lim}
    where = "datetime(created_at) >= datetime('now', :window)"
    if camera_id:
        where += " AND camera_id = :camera_id"
        params["camera_id"] = str(camera_id).strip()
    rows = db.session.execute(
        text(
            f"""
            SELECT camera_id, payload_json, created_at
            FROM session_runtime_metrics
            WHERE {where}
            ORDER BY id DESC
            LIMIT :lim
            """
        ),
        params,
    ).mappings()
    sessions: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(str(row.get("payload_json") or "{}"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        payload.setdefault("triggered_camera", row.get("camera_id"))
        payload["_created_at"] = row.get("created_at")
        sessions.append(payload)
    return sessions


def _recent_session_rows(sessions: list[dict[str, Any]], *, max_rows: int = 12) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for payload in sessions[:max_rows]:
        tg = payload.get("trigger_graph") if isinstance(payload.get("trigger_graph"), dict) else {}
        metrics = tg.get("metrics_by_source") if isinstance(tg.get("metrics_by_source"), dict) else {}
        out.append(
            {
                "created_at": payload.get("_created_at"),
                "camera_id": tg.get("camera_id") or payload.get("triggered_camera"),
                "init_source": tg.get("init_source"),
                "trigger_display": tg.get("trigger_display"),
                "post_fusion_persisted": int(payload.get("post_fusion_persisted") or 0),
                "fp_empty_recording": sum(
                    int((metrics.get(n) or {}).get("fp_empty_recording") or 0) for n in TRIGGER_NODES
                ),
                "fn_detector_silent": sum(
                    int((metrics.get(n) or {}).get("fn_detector_silent") or 0) for n in TRIGGER_NODES
                ),
                "species_persisted": sum(
                    int((metrics.get(n) or {}).get("species_persisted") or 0) for n in TRIGGER_NODES
                ),
            }
        )
    return out


def fetch_trigger_graph_metrics(
    *,
    hours: int = 24,
    camera_id: str | None = None,
    limit: int = 800,
) -> dict[str, Any]:
    sessions = _load_sessions_from_db(hours=hours, camera_id=camera_id, limit=limit)
    agg = aggregate_trigger_metrics(sessions)
    return {
        "window_hours": max(1, min(int(hours), 168)),
        "camera_filter": camera_id,
        "nodes": list(TRIGGER_NODES),
        **agg,
        "recent_sessions": _recent_session_rows(sessions),
    }
