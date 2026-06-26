"""Persist funnel summary from session_runtime_metrics (readiness + System API)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app_config.app_config import app_config
from models import SessionRuntimeMetrics

PERSIST_SUBSTAGE_PAYLOAD_KEYS: tuple[str, ...] = (
    "persist_duration_ms",
    "scales_duration_ms",
    "create_video_duration_ms",
    "dataset_crops_duration_ms",
    "reid_enrich_duration_ms",
)
)

CREATE_VIDEO_INGEST_SUBSTAGE_KEYS: tuple[str, ...] = (
    "visit_processor_ms",
    "commit_ms",
    "weather_ms",
)


def _safe_float(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if num >= 0 else None


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    idx = int((len(ordered) - 1) * max(0.0, min(100.0, pct)) / 100.0)
    return round(float(ordered[idx]), 3)


def _latency_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "n": len(values),
        "p50_ms": _percentile(values, 50.0),
        "p95_ms": _percentile(values, 95.0),
        "max_ms": round(max(values), 3),
    }


def _collect_persist_substage_samples(
    rows: list[Any],
) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    """Extract per-session persist substage latencies from payload_json."""
    flat: dict[str, list[float]] = {key: [] for key in PERSIST_SUBSTAGE_PAYLOAD_KEYS}
    ingest: dict[str, list[float]] = {key: [] for key in CREATE_VIDEO_INGEST_SUBSTAGE_KEYS}

    for row in rows:
        payload = _extract_payload(getattr(row, "payload_json", None))
        grouped = payload.get("persist_substage_ms")
        if isinstance(grouped, dict):
            mapping = {
                "persist_duration_ms": payload.get("persist_duration_ms"),
                "scales_duration_ms": grouped.get("scales_ms"),
                "create_video_duration_ms": grouped.get("create_video_ms"),
                "dataset_crops_duration_ms": grouped.get("dataset_crops_ms"),
                "reid_enrich_duration_ms": grouped.get("reid_enrich_ms"),
            }
            ingest_group = grouped.get("create_video_ingest_ms")
        else:
            mapping = {key: payload.get(key) for key in PERSIST_SUBSTAGE_PAYLOAD_KEYS}
            ingest_group = payload.get("create_video_ingest_timing_ms")

        for key, raw in mapping.items():
            val = _safe_float(raw)
            if val is not None and val > 0:
                flat[key].append(val)

        if isinstance(ingest_group, dict):
            for ingest_key in CREATE_VIDEO_INGEST_SUBSTAGE_KEYS:
                val = _safe_float(ingest_group.get(ingest_key))
                if val is not None and val > 0:
                    ingest[ingest_key].append(val)

    return flat, ingest


def build_persist_substage_breakdown(session) -> dict[str, Any]:
    """Aggregate persist-tail p50/p95 from recent session_runtime_metrics rows."""
    lookback_h, _, _, _ = _funnel_thresholds()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_h)
    rows = (
        session.query(SessionRuntimeMetrics)
        .filter(SessionRuntimeMetrics.created_at >= cutoff)
        .order_by(SessionRuntimeMetrics.created_at.desc())
        .all()
    )
    flat, ingest = _collect_persist_substage_samples(rows)
    substages: dict[str, Any] = {}
    for key, samples in flat.items():
        short = key.removesuffix("_duration_ms").removesuffix("_ms")
        substages[short] = _latency_summary(samples)
    ingest_summary = {key.removesuffix("_ms"): _latency_summary(samples) for key, samples in ingest.items()}
    if any(summary.get("n", 0) > 0 for summary in ingest_summary.values()):
        substages["create_video_ingest"] = ingest_summary

    dominant = None
    dominant_p95 = 0.0
    for name, summary in substages.items():
        if name == "create_video_ingest":
            continue
        p95 = summary.get("p95_ms")
        if p95 is not None and float(p95) > dominant_p95:
            dominant_p95 = float(p95)
            dominant = name

    return {
        "schema": "persist_substage_breakdown@v1",
        "window_hours": lookback_h,
        "sessions_sampled": len(rows),
        "substages": substages,
        "dominant_substage_p95": dominant,
    }


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
            alerts.append(f"fp_empty_recording opencv rate {fp_opencv_rate:.1%} > {max_fp_opencv:.1%}")
        if fusion_drop_rate is not None and fusion_drop_rate > max_fusion_drop:
            alerts.append(f"fusion_drop rate {fusion_drop_rate:.1%} > {max_fusion_drop:.1%}")
        if healthy_rate is not None and healthy_rate < min_healthy:
            alerts.append(f"healthy_persist rate {healthy_rate:.1%} < {min_healthy:.1%}")

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
        "persist_substage_breakdown": build_persist_substage_breakdown(session),
    }
