"""Persist funnel summary from session_runtime_metrics (readiness + System API)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app_config.app_config import app_config
from models import SessionRuntimeMetrics


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _extract_payload(raw_payload: str | None) -> dict[str, Any]:
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        return {}
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _classify_failure_mode(
    *,
    yolo_raw_boxes_total: int,
    yolo_accepted_boxes_total: int,
    yolo_frames_with_tracks: int,
    post_fusion_persisted: int,
) -> str:
    if yolo_raw_boxes_total <= 0:
        return "detector_silent_raw0"
    if yolo_accepted_boxes_total <= 0:
        return "confidence_gate_collapse_raw_gt_0_accepted_0"
    if yolo_frames_with_tracks <= 0:
        return "quality_filter_collapse_raw_gt_0_tracks_0"
    if post_fusion_persisted <= 0:
        return "decision_fusion_drop_tracks_gt_0_persisted_0"
    return "healthy_persisted_gt_0"


def _funnel_thresholds() -> tuple[int, float, float, float]:
    lookback = int(app_config.get("readiness.funnel_lookback_hours") or 24)
    lookback = max(1, min(168, lookback))
    try:
        max_fp = float(app_config.get("readiness.max_fp_empty_opencv_rate") or 0.35)
    except (TypeError, ValueError):
        max_fp = 0.35
    try:
        max_drop = float(app_config.get("readiness.max_fusion_drop_session_rate") or 0.35)
    except (TypeError, ValueError):
        max_drop = 0.35
    try:
        min_healthy = float(app_config.get("readiness.min_healthy_persist_rate") or 0.30)
    except (TypeError, ValueError):
        min_healthy = 0.30
    return lookback, max_fp, max_drop, min_healthy


def build_persist_funnel_summary(session) -> dict[str, Any]:
    """Aggregate failure-mode funnel for readiness and GET /api/ui/system/pipeline-funnel."""
    lookback_h, max_fp_opencv, max_fusion_drop, min_healthy = _funnel_thresholds()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_h)
    rows = (
        session.query(SessionRuntimeMetrics)
        .filter(SessionRuntimeMetrics.created_at >= cutoff)
        .order_by(SessionRuntimeMetrics.created_at.desc())
        .all()
    )

    global_counts: Counter[str] = Counter()
    by_camera: dict[str, Counter[str]] = defaultdict(Counter)
    fp_empty_opencv = 0
    fusion_drop = 0

    for row in rows:
        payload = _extract_payload(row.payload_json)
        post_fusion = _safe_int(row.post_fusion_persisted or payload.get("post_fusion_persisted"))
        mode = _classify_failure_mode(
            yolo_raw_boxes_total=_safe_int(row.yolo_raw_boxes_total),
            yolo_accepted_boxes_total=_safe_int(row.yolo_accepted_boxes_total),
            yolo_frames_with_tracks=_safe_int(row.yolo_frames_with_tracks),
            post_fusion_persisted=post_fusion,
        )
        camera_id = str(row.camera_id or "unknown")
        global_counts[mode] += 1
        by_camera[camera_id][mode] += 1
        if mode == "decision_fusion_drop_tracks_gt_0_persisted_0":
            fusion_drop += 1
        trigger_graph = payload.get("trigger_graph")
        if isinstance(trigger_graph, dict):
            metrics_by_source = trigger_graph.get("metrics_by_source")
            if isinstance(metrics_by_source, dict):
                opencv = metrics_by_source.get("opencv")
                if isinstance(opencv, dict) and _safe_int(opencv.get("fp_empty_recording")) > 0:
                    fp_empty_opencv += 1

    total = len(rows)
    healthy = int(global_counts.get("healthy_persisted_gt_0", 0))
    healthy_rate = (healthy / float(total)) if total else None
    fusion_drop_rate = (fusion_drop / float(total)) if total else None
    fp_opencv_rate = (fp_empty_opencv / float(total)) if total else None

    alerts: list[str] = []
    if total > 0:
        if fp_opencv_rate is not None and fp_opencv_rate > max_fp_opencv:
            alerts.append(
                f"fp_empty_recording opencv rate {fp_opencv_rate:.1%} > {max_fp_opencv:.1%}"
            )
        if fusion_drop_rate is not None and fusion_drop_rate > max_fusion_drop:
            alerts.append(
                f"fusion_drop rate {fusion_drop_rate:.1%} > {max_fusion_drop:.1%}"
            )
        if healthy_rate is not None and healthy_rate < min_healthy:
            alerts.append(
                f"healthy_persist rate {healthy_rate:.1%} < {min_healthy:.1%}"
            )

    top_causes = [mode for mode, _ in global_counts.most_common(5)]
    status = "ok"
    if not total:
        status = "ok"
    elif alerts:
        status = "degraded"

    return {
        "schema": "persist_funnel_summary@v1",
        "window_hours": lookback_h,
        "sessions_total": total,
        "healthy_persist_count": healthy,
        "healthy_persist_rate": round(healthy_rate, 4) if healthy_rate is not None else None,
        "fusion_drop_sessions": fusion_drop,
        "fusion_drop_rate": round(fusion_drop_rate, 4) if fusion_drop_rate is not None else None,
        "fp_empty_opencv_sessions": fp_empty_opencv,
        "fp_empty_opencv_rate": round(fp_opencv_rate, 4) if fp_opencv_rate is not None else None,
        "global_funnel": dict(global_counts.most_common()),
        "by_camera": {cam: dict(cnt.most_common()) for cam, cnt in sorted(by_camera.items())},
        "top_root_causes": top_causes,
        "alerts": alerts,
        "status": status,
    }
