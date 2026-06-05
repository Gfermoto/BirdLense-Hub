#!/usr/bin/env python3
"""Build per-camera failure-mode funnel from session_runtime_metrics."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
try:
    from datetime import UTC
except ImportError:  # Python 3.9
    UTC = timezone.utc  # type: ignore[misc, assignment]
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_rows(db_path: Path, lookback_hours: int) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cols = {
            str(r["name"])
            for r in conn.execute(
                "PRAGMA table_info(session_runtime_metrics)"
            ).fetchall()
        }
        slot_col = (
            "camera_slot"
            if "camera_slot" in cols
            else "NULL AS camera_slot"
        )
        return list(
            conn.execute(
                f"""
                SELECT
                  created_at,
                  camera_id,
                  yolo_frames_ran,
                  yolo_frames_with_tracks,
                  yolo_raw_boxes_total,
                  yolo_accepted_boxes_total,
                  payload_json,
                  {slot_col}
                FROM session_runtime_metrics
                WHERE datetime(created_at) >= datetime('now', ?)
                ORDER BY created_at DESC
                """,  # nosec B608
                (f"-{max(1, int(lookback_hours))} hours",),
            )
        )
    finally:
        conn.close()


def _extract_payload(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        return {}
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _infer_slot(row: sqlite3.Row, payload: dict[str, Any]) -> str:
    slot = row["camera_slot"] if "camera_slot" in row.keys() else None
    if slot is not None:
        return str(slot)
    payload_slot = payload.get("camera_slot")
    if payload_slot is not None:
        return str(payload_slot)
    return "legacy:no-slot"


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


def _merge_reason_counts(
    target: Counter[str],
    payload: dict[str, Any],
) -> None:
    trigger_graph = payload.get("trigger_graph")
    if not isinstance(trigger_graph, dict):
        return
    raw_counts = trigger_graph.get("decision_reason_counts")
    if not isinstance(raw_counts, dict):
        return
    for reason, count in raw_counts.items():
        target[str(reason or "unknown")] += _safe_int(count)


def build_failure_mode_funnel(
    rows: list[sqlite3.Row],
    *,
    lookback_hours: int,
    max_fp_empty_opencv_rate: float = 0.35,
    max_acceptance_gap_sessions: int = 8,
) -> dict[str, Any]:
    global_counts: Counter[str] = Counter()
    by_camera: dict[str, Counter[str]] = defaultdict(Counter)
    by_slot: dict[str, Counter[str]] = defaultdict(Counter)
    decision_reason_counts: Counter[str] = Counter()
    decision_reason_by_camera: dict[str, Counter[str]] = defaultdict(Counter)
    risk_flags: Counter[str] = Counter()
    concurrent_started = 0
    fp_empty_by_source: Counter[str] = Counter()
    fp_empty_by_camera: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        payload = _extract_payload(row["payload_json"])
        post_fusion_persisted = _safe_int(payload.get("post_fusion_persisted"))
        raw_total = _safe_int(row["yolo_raw_boxes_total"])
        accepted_total = _safe_int(row["yolo_accepted_boxes_total"])
        if payload.get("detection_acceptance_gap") or (
            raw_total > 0 and accepted_total <= 0
        ):
            risk_flags["detection_acceptance_gap"] += 1
        cr = payload.get("concurrent_recording")
        if isinstance(cr, dict) and cr.get("started_concurrent"):
            concurrent_started += 1
        camera_id = str(row["camera_id"] or "unknown")
        trigger_graph = payload.get("trigger_graph")
        if isinstance(trigger_graph, dict):
            metrics_by_source = trigger_graph.get("metrics_by_source")
            if isinstance(metrics_by_source, dict):
                for source, metrics in metrics_by_source.items():
                    if not isinstance(metrics, dict):
                        continue
                    fp_empty = _safe_int(metrics.get("fp_empty_recording"))
                    if fp_empty > 0:
                        fp_empty_by_source[str(source)] += 1
                        fp_empty_by_camera[camera_id][str(source)] += 1
        mode = _classify_failure_mode(
            yolo_raw_boxes_total=_safe_int(row["yolo_raw_boxes_total"]),
            yolo_accepted_boxes_total=_safe_int(row["yolo_accepted_boxes_total"]),
            yolo_frames_with_tracks=_safe_int(row["yolo_frames_with_tracks"]),
            post_fusion_persisted=post_fusion_persisted,
        )
        camera_id = str(row["camera_id"] or "unknown")
        slot = _infer_slot(row, payload)
        global_counts[mode] += 1
        by_camera[camera_id][mode] += 1
        by_slot[slot][mode] += 1
        _merge_reason_counts(decision_reason_counts, payload)
        per_cam = decision_reason_by_camera[camera_id]
        if isinstance(trigger_graph, dict):
            raw_counts = trigger_graph.get("decision_reason_counts")
            if isinstance(raw_counts, dict):
                for reason, count in raw_counts.items():
                    per_cam[str(reason or "unknown")] += _safe_int(count)

    total_sessions = len(rows)

    def _to_ranked_dict(counter: Counter[str]) -> dict[str, int]:
        return {k: int(v) for k, v in counter.most_common()}

    top_root_causes = [mode for mode, _ in global_counts.most_common(5)]

    acceptance_gap_sessions = int(risk_flags.get("detection_acceptance_gap", 0))
    fp_opencv_sessions = int(fp_empty_by_source.get("opencv", 0))
    fp_frigate_sessions = int(fp_empty_by_source.get("frigate", 0))
    alerts: list[str] = []
    if total_sessions > 0:
        fp_opencv_rate = fp_opencv_sessions / float(total_sessions)
        if fp_opencv_rate > float(max_fp_empty_opencv_rate):
            alerts.append(
                f"fp_empty_recording opencv rate {fp_opencv_rate:.1%} > "
                f"{float(max_fp_empty_opencv_rate):.1%} (#I9)"
            )
    if acceptance_gap_sessions > int(max_acceptance_gap_sessions):
        alerts.append(
            f"detection_acceptance_gap sessions {acceptance_gap_sessions} > "
            f"{int(max_acceptance_gap_sessions)} (#587)"
        )

    return {
        "schema": "failure_mode_funnel@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": int(max(1, lookback_hours)),
        "sessions_total": int(total_sessions),
        "global_funnel": _to_ranked_dict(global_counts),
        "by_camera": {
            camera: _to_ranked_dict(counter)
            for camera, counter in sorted(by_camera.items())
        },
        "by_slot": {
            slot: _to_ranked_dict(counter)
            for slot, counter in sorted(by_slot.items())
        },
        "top_root_causes": top_root_causes,
        "decision_reason_counts": _to_ranked_dict(decision_reason_counts),
        "decision_reason_by_camera": {
            camera: _to_ranked_dict(counter)
            for camera, counter in sorted(decision_reason_by_camera.items())
        },
        "risk_flags": {
            "detection_acceptance_gap_sessions": acceptance_gap_sessions,
            "concurrent_recording_started_sessions": int(concurrent_started),
            "static_pinned_rejects_total": int(
                decision_reason_counts.get("rejected_static_pinned_track", 0)
            ),
            "fp_empty_recording_opencv_sessions": fp_opencv_sessions,
            "fp_empty_recording_frigate_sessions": fp_frigate_sessions,
        },
        "trigger_graph_fp_by_source": _to_ranked_dict(fp_empty_by_source),
        "trigger_graph_fp_by_camera": {
            camera: _to_ranked_dict(counter)
            for camera, counter in sorted(fp_empty_by_camera.items())
        },
        "alerts": alerts,
        "ok": total_sessions > 0 and len(top_root_causes) > 0,
        "acceptance_ok": not alerts,
    }


def _to_md(report: dict[str, Any]) -> str:
    lines = [
        "# Failure Mode Funnel",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- sessions_total: `{report.get('sessions_total')}`",
        f"- ok: `{report.get('ok')}`",
        "",
        "## Top root causes",
        "",
    ]
    for cause in list(report.get("top_root_causes") or []):
        lines.append(f"- {cause}")
    lines.append("")
    lines.append("## Global funnel")
    lines.append("")
    lines.append(f"`{report.get('global_funnel')}`")
    lines.append("")
    lines.append("## By camera")
    lines.append("")
    lines.append(f"`{report.get('by_camera')}`")
    lines.append("")
    lines.append("## By slot")
    lines.append("")
    lines.append(f"`{report.get('by_slot')}`")
    lines.append("")
    lines.append("## Decision reason counts")
    lines.append("")
    lines.append(f"`{report.get('decision_reason_counts')}`")
    lines.append("")
    lines.append("## Decision reasons by camera")
    lines.append("")
    lines.append(f"`{report.get('decision_reason_by_camera')}`")
    lines.append("")
    lines.append("## Risk flags")
    lines.append("")
    lines.append(f"`{report.get('risk_flags')}`")
    lines.append("")
    lines.append("## Trigger-graph FP (empty recording)")
    lines.append("")
    lines.append(f"`{report.get('trigger_graph_fp_by_source')}`")
    lines.append("")
    lines.append("## Alerts")
    lines.append("")
    for item in report.get("alerts") or []:
        lines.append(f"- {item}")
    if not (report.get("alerts") or []):
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default="app/data/db/birdlense.db")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument(
        "--out-json",
        default="docs/reports/quality_outcome/failure_mode_funnel_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/quality_outcome/failure_mode_funnel_latest.md",
    )
    parser.add_argument(
        "--max-fp-empty-opencv-rate",
        type=float,
        default=None,
        help="Alert when opencv fp_empty_recording session rate exceeds threshold",
    )
    parser.add_argument(
        "--max-acceptance-gap-sessions",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--fail-on-alerts",
        action="store_true",
    )
    return parser.parse_args()


def main() -> int:
    import os

    args = _args()
    db_path = Path(args.db_path).expanduser()
    if not db_path.is_absolute():
        db_path = REPO / db_path
    if not db_path.exists():
        raise SystemExit(f"db file not found: {db_path}")
    rows = _load_rows(db_path, int(max(1, args.lookback_hours)))
    max_fp_rate = args.max_fp_empty_opencv_rate
    if max_fp_rate is None:
        max_fp_rate = float(os.environ.get("FUNNEL_MAX_FP_EMPTY_OPENCV_RATE", "0.35"))
    max_gap = args.max_acceptance_gap_sessions
    if max_gap is None:
        max_gap = int(os.environ.get("FUNNEL_MAX_ACCEPTANCE_GAP_SESSIONS", "8"))
    report = build_failure_mode_funnel(
        rows,
        lookback_hours=int(max(1, args.lookback_hours)),
        max_fp_empty_opencv_rate=float(max_fp_rate),
        max_acceptance_gap_sessions=int(max_gap),
    )
    out_json = Path(args.out_json).expanduser()
    if not out_json.is_absolute():
        out_json = REPO / out_json
    out_md = Path(args.out_md).expanduser()
    if not out_md.is_absolute():
        out_md = REPO / out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_to_md(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "acceptance_ok": bool(report.get("acceptance_ok")),
                "alerts": list(report.get("alerts") or []),
                "json": str(out_json),
                "md": str(out_md),
            }
        )
    )
    if args.fail_on_alerts and (report.get("alerts") or []):
        return 1
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
