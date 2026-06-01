#!/usr/bin/env python3
"""Compute outcome quality metrics from session_runtime_metrics."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    idx = max(0, min(len(v) - 1, int(math.ceil((pct / 100.0) * len(v)) - 1)))
    return float(v[idx])


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


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
        latency_col = (
            "trigger_to_first_bbox_latency_s"
            if "trigger_to_first_bbox_latency_s" in cols
            else "NULL AS trigger_to_first_bbox_latency_s"
        )
        track_col = (
            "first_track_latency_s"
            if "first_track_latency_s" in cols
            else "NULL AS first_track_latency_s"
        )
        finalize_col = (
            "finalize_duration_ms"
            if "finalize_duration_ms" in cols
            else "NULL AS finalize_duration_ms"
        )
        return list(
            conn.execute(
                f"""
                SELECT
                  created_at,
                  yolo_blind_confirmed,
                  yolo_frames_ran,
                  yolo_frames_with_tracks,
                  rejected_decision_rows,
                  {latency_col},
                  {track_col},
                  {finalize_col},
                  payload_json
                FROM session_runtime_metrics
                WHERE created_at >= datetime('now', ?)
                ORDER BY created_at DESC
                """,  # nosec B608
                (f"-{max(1, int(lookback_hours))} hours",),
            )
        )
    finally:
        conn.close()


def evaluate(
    rows: list[sqlite3.Row], thresholds: dict[str, float]
) -> dict[str, Any]:
    sessions_total = len(rows)
    sessions_with_yolo = 0
    sessions_with_tracks = 0
    blind_confirmed = 0
    yolo_frames_with_tracks_sum = 0
    empty_bbox_rejections = 0
    rejected_rows_total = 0
    latency_samples: list[float] = []
    finalize_duration_samples: list[float] = []

    for row in rows:
        yolo_ran = _safe_int(row["yolo_frames_ran"])
        yolo_tracks = _safe_int(row["yolo_frames_with_tracks"])
        sessions_with_yolo += 1 if yolo_ran > 0 else 0
        sessions_with_tracks += 1 if yolo_tracks > 0 else 0
        blind_confirmed += (
            1 if _safe_int(row["yolo_blind_confirmed"]) > 0 else 0
        )
        yolo_frames_with_tracks_sum += yolo_tracks
        rejected_rows_total += _safe_int(row["rejected_decision_rows"])

        payload = {}
        raw_payload = row["payload_json"]
        if isinstance(raw_payload, str) and raw_payload.strip():
            try:
                parsed = json.loads(raw_payload)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {}

        reason_counts = payload.get("rejected_reason_counts")
        if isinstance(reason_counts, dict):
            empty_bbox_rejections += _safe_int(
                reason_counts.get("empty_bbox_frames")
            )

        latency_from_columns = _safe_float(
            row["trigger_to_first_bbox_latency_s"]
        )
        if latency_from_columns > 0:
            latency_samples.append(latency_from_columns)
        else:
            for key in (
                "trigger_to_first_bbox_latency_s",
                "first_bbox_latency_s",
                "first_track_latency_s",
            ):
                if key in payload:
                    latency = _safe_float(payload.get(key))
                    if latency > 0:
                        latency_samples.append(latency)
                    break
        finalize_duration_ms = _safe_float(row["finalize_duration_ms"])
        if finalize_duration_ms > 0:
            finalize_duration_samples.append(finalize_duration_ms)
        elif payload:
            payload_finalize_ms = _safe_float(
                payload.get("finalize_duration_ms")
            )
            if payload_finalize_ms > 0:
                finalize_duration_samples.append(payload_finalize_ms)

    blind_rate = (
        (blind_confirmed / sessions_total) if sessions_total > 0 else 1.0
    )
    tracks_coverage = (
        sessions_with_tracks / sessions_with_yolo
        if sessions_with_yolo > 0
        else 0.0
    )
    empty_bbox_rate = (
        empty_bbox_rejections / rejected_rows_total
        if rejected_rows_total > 0
        else 0.0
    )
    latency_p95 = _percentile(latency_samples, 95.0)
    finalize_duration_p95_ms = _percentile(finalize_duration_samples, 95.0)

    errors: list[str] = []
    if sessions_total <= 0:
        errors.append("no session_runtime_metrics rows in lookback window")
    if blind_rate > thresholds["max_blind_rate"]:
        errors.append(
            "blind_rate="
            f"{blind_rate:.4f} > max_blind_rate="
            f"{thresholds['max_blind_rate']:.4f}"
        )
    if tracks_coverage < thresholds["min_tracks_coverage"]:
        errors.append(
            "tracks_coverage="
            f"{tracks_coverage:.4f} < min_tracks_coverage="
            f"{thresholds['min_tracks_coverage']:.4f}"
        )
    if empty_bbox_rate > thresholds["max_empty_bbox_rate"]:
        errors.append(
            "empty_bbox_rate="
            f"{empty_bbox_rate:.4f} > max_empty_bbox_rate="
            f"{thresholds['max_empty_bbox_rate']:.4f}"
        )
    if (
        yolo_frames_with_tracks_sum
        < int(thresholds["min_yolo_frames_with_tracks"])
    ):
        errors.append(
            "yolo_frames_with_tracks_sum="
            f"{yolo_frames_with_tracks_sum} < "
            "min_yolo_frames_with_tracks="
            f"{int(thresholds['min_yolo_frames_with_tracks'])}"
        )

    return {
        "schema": "quality_outcome_metrics@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": int(thresholds["lookback_hours"]),
        "metrics": {
            "sessions_total": int(sessions_total),
            "sessions_with_yolo": int(sessions_with_yolo),
            "sessions_with_tracks": int(sessions_with_tracks),
            "blind_rate": float(round(blind_rate, 6)),
            "yolo_frames_with_tracks": int(yolo_frames_with_tracks_sum),
            "empty_bbox_rate": float(round(empty_bbox_rate, 6)),
            "tracks_coverage": float(round(tracks_coverage, 6)),
            "trigger_to_first_bbox_latency_p95_s": (
                None if latency_p95 is None else float(round(latency_p95, 6))
            ),
            "finalize_duration_p95_ms": (
                None
                if finalize_duration_p95_ms is None
                else float(round(finalize_duration_p95_ms, 6))
            ),
        },
        "thresholds": {
            "max_blind_rate": float(thresholds["max_blind_rate"]),
            "min_tracks_coverage": float(thresholds["min_tracks_coverage"]),
            "max_empty_bbox_rate": float(thresholds["max_empty_bbox_rate"]),
            "min_yolo_frames_with_tracks": int(
                thresholds["min_yolo_frames_with_tracks"]
            ),
        },
        "gate": {
            "ok": len(errors) == 0,
            "errors": errors,
        },
    }


def _to_md(report: dict[str, Any]) -> str:
    metrics = report.get("metrics") or {}
    gate = report.get("gate") or {}
    thresholds = report.get("thresholds") or {}
    lines = [
        "# Quality Outcome Metrics",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- gate_ok: `{gate.get('ok')}`",
        f"- sessions_total: `{metrics.get('sessions_total')}`",
        "",
        "## Metrics",
        "",
        f"- blind_rate: `{metrics.get('blind_rate')}`",
        "- yolo_frames_with_tracks: "
        f"`{metrics.get('yolo_frames_with_tracks')}`",
        f"- empty_bbox_rate: `{metrics.get('empty_bbox_rate')}`",
        f"- tracks_coverage: `{metrics.get('tracks_coverage')}`",
        "- trigger_to_first_bbox_latency_p95_s: "
        f"`{metrics.get('trigger_to_first_bbox_latency_p95_s')}`",
        "- finalize_duration_p95_ms: "
        f"`{metrics.get('finalize_duration_p95_ms')}`",
        "",
        "## Thresholds",
        "",
        f"- max_blind_rate: `{thresholds.get('max_blind_rate')}`",
        f"- min_tracks_coverage: `{thresholds.get('min_tracks_coverage')}`",
        f"- max_empty_bbox_rate: `{thresholds.get('max_empty_bbox_rate')}`",
        "- min_yolo_frames_with_tracks: "
        f"`{thresholds.get('min_yolo_frames_with_tracks')}`",
    ]
    errors = list((gate.get("errors") or []))
    if errors:
        lines.append("")
        lines.append("## Errors")
        lines.append("")
        for err in errors:
            lines.append(f"- {err}")
    return "\n".join(lines) + "\n"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        default="app/data/db/birdlense.db",
    )
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--max-blind-rate", type=float, default=0.30)
    parser.add_argument("--min-tracks-coverage", type=float, default=0.50)
    parser.add_argument("--max-empty-bbox-rate", type=float, default=0.20)
    parser.add_argument("--min-yolo-frames-with-tracks", type=int, default=1)
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/quality_outcome/"
            "quality_outcome_metrics_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default=(
            "docs/reports/quality_outcome/"
            "quality_outcome_metrics_latest.md"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    db_path = Path(args.db_path).expanduser()
    if not db_path.is_absolute():
        db_path = REPO / db_path
    if not db_path.exists():
        raise SystemExit(f"db file not found: {db_path}")

    thresholds = {
        "lookback_hours": int(max(1, args.lookback_hours)),
        "max_blind_rate": float(max(0.0, args.max_blind_rate)),
        "min_tracks_coverage": float(
            max(0.0, min(1.0, args.min_tracks_coverage))
        ),
        "max_empty_bbox_rate": float(max(0.0, args.max_empty_bbox_rate)),
        "min_yolo_frames_with_tracks": float(
            max(0, args.min_yolo_frames_with_tracks)
        ),
    }
    rows = _load_rows(db_path, int(thresholds["lookback_hours"]))
    report = evaluate(rows, thresholds)

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
                "ok": bool((report.get("gate") or {}).get("ok")),
                "json": str(out_json),
                "md": str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool((report.get("gate") or {}).get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
