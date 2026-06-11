#!/usr/bin/env python3
"""Compute outcome quality metrics from session_runtime_metrics."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
try:
    from datetime import UTC
except ImportError:  # Python < 3.11
    from datetime import timezone

    UTC = timezone.utc  # type: ignore[misc,assignment]
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

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


def _session_fp_empty_recording(payload: Mapping[str, Any]) -> bool:
    """True when trigger_graph marks init_source as fp_empty_recording (#I9).

    Those sessions legitimately have zero tracks; they must not deflate tracks_coverage.
    """
    tg = payload.get("trigger_graph")
    if not isinstance(tg, dict):
        return False
    init_source = str(
        tg.get("init_source") or payload.get("trigger_source") or ""
    ).strip()
    if not init_source:
        return False
    metrics_by_source = tg.get("metrics_by_source")
    if not isinstance(metrics_by_source, dict):
        return False
    source_metrics = metrics_by_source.get(init_source)
    if not isinstance(source_metrics, dict):
        return False
    return _safe_int(source_metrics.get("fp_empty_recording")) > 0


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
                  yolo_raw_boxes_total,
                  session_extended_by_frigate_only,
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


def _load_ingest_gate_rows(
    db_path: Path,
    lookback_hours: int,
) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='activity_log' LIMIT 1"
        ).fetchone()
        if table is None:
            return []
        return list(
            conn.execute(
                """
                SELECT created_at, data
                FROM activity_log
                WHERE type = 'ingest_gate'
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
                """,
                (f"-{max(1, int(lookback_hours))} hours",),
            )
        )
    finally:
        conn.close()


def _load_trigger_moratorium_rows(
    db_path: Path,
    lookback_hours: int,
) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='activity_log' LIMIT 1"
        ).fetchone()
        if table is None:
            return []
        return list(
            conn.execute(
                """
                SELECT created_at, data
                FROM activity_log
                WHERE type = 'trigger_moratorium'
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
                """,
                (f"-{max(1, int(lookback_hours))} hours",),
            )
        )
    finally:
        conn.close()


def evaluate(
    rows: list[sqlite3.Row],
    thresholds: dict[str, float],
    *,
    data_source: str = "local",
    ingest_gate_rows: list[sqlite3.Row] | None = None,
    ingest_gate_rows_7d: list[sqlite3.Row] | None = None,
    trigger_moratorium_rows: list[sqlite3.Row] | None = None,
    trigger_moratorium_rows_7d: list[sqlite3.Row] | None = None,
    rows_7d: list[sqlite3.Row] | None = None,
) -> dict[str, Any]:
    sessions_total = len(rows)
    sessions_with_yolo = 0
    sessions_with_tracks = 0
    sessions_fp_empty_recording = 0
    blind_confirmed = 0
    yolo_frames_with_tracks_sum = 0
    empty_bbox_rejections = 0
    rejected_rows_total = 0
    latency_samples: list[float] = []
    finalize_duration_samples: list[float] = []
    ingest_pruned_events = 0
    ingest_empty_contract_events = 0
    ingest_pruned_rows_total = 0
    ingest_pruned_frames_total = 0
    trigger_moratorium_events = 0
    trigger_moratorium_events_7d = 0
    trigger_moratorium_by_source: dict[str, int] = {}
    frigate_catches_missed_birds_sessions = 0
    frigate_catches_missed_birds_by_trigger_source: dict[str, int] = {}

    for row in rows:
        yolo_ran = _safe_int(row["yolo_frames_ran"])
        yolo_tracks = _safe_int(row["yolo_frames_with_tracks"])
        yolo_raw_total = _safe_int(row["yolo_raw_boxes_total"])
        frigate_only = _safe_int(row["session_extended_by_frigate_only"])
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
        is_fp_empty = _session_fp_empty_recording(payload)
        if is_fp_empty:
            sessions_fp_empty_recording += 1
        if frigate_only > 0 and yolo_raw_total == 0:
            frigate_catches_missed_birds_sessions += 1
            source = str(payload.get("trigger_source") or "unknown").strip()
            source_key = source.lower() if source else "unknown"
            frigate_catches_missed_birds_by_trigger_source[source_key] = (
                int(
                    frigate_catches_missed_birds_by_trigger_source.get(
                        source_key
                    )
                    or 0
                )
                + 1
            )

        reason_counts = payload.get("rejected_reason_counts")
        if isinstance(reason_counts, dict):
            empty_bbox_rejections += _safe_int(
                reason_counts.get("empty_bbox_frames")
            )

        if not is_fp_empty:
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

    frigate_catches_missed_birds_sessions_7d = 0
    sessions_total_7d = 0
    for row in rows_7d or []:
        sessions_total_7d += 1
        yolo_raw_total = _safe_int(row["yolo_raw_boxes_total"])
        frigate_only = _safe_int(row["session_extended_by_frigate_only"])
        if frigate_only > 0 and yolo_raw_total == 0:
            frigate_catches_missed_birds_sessions_7d += 1

    for row in ingest_gate_rows or []:
        payload = {}
        raw_data = row["data"]
        if isinstance(raw_data, str) and raw_data.strip():
            try:
                parsed = json.loads(raw_data)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {}
        reason = str(payload.get("reason") or "").strip().lower()
        if reason == "video_bbox_track_contract_pruned":
            ingest_pruned_events += 1
            ingest_pruned_rows_total += _safe_int(
                payload.get("dropped_missing_frames")
            ) + _safe_int(payload.get("dropped_empty_bbox"))
            ingest_pruned_frames_total += _safe_int(
                payload.get("pruned_invalid_bbox_frames")
            )
        elif reason == "video_bbox_track_contract_empty":
            ingest_empty_contract_events += 1

    ingest_pruned_rows_total_7d = 0
    for row in ingest_gate_rows_7d or []:
        payload = {}
        raw_data = row["data"]
        if isinstance(raw_data, str) and raw_data.strip():
            try:
                parsed = json.loads(raw_data)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {}
        reason = str(payload.get("reason") or "").strip().lower()
        if reason != "video_bbox_track_contract_pruned":
            continue
        ingest_pruned_rows_total_7d += _safe_int(
            payload.get("dropped_missing_frames")
        ) + _safe_int(payload.get("dropped_empty_bbox"))
    for row in trigger_moratorium_rows or []:
        trigger_moratorium_events += 1
        payload = {}
        raw_data = row["data"]
        if isinstance(raw_data, str) and raw_data.strip():
            try:
                parsed = json.loads(raw_data)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {}
        source = str(payload.get("trigger_source") or "unknown").strip()
        source_key = source.lower() if source else "unknown"
        trigger_moratorium_by_source[source_key] = (
            int(trigger_moratorium_by_source.get(source_key) or 0)
            + 1
        )
    trigger_moratorium_events_7d = len(trigger_moratorium_rows_7d or [])

    blind_rate = (
        (blind_confirmed / sessions_total) if sessions_total > 0 else 1.0
    )
    tracks_eligible_sessions = max(
        0, int(sessions_with_yolo) - int(sessions_fp_empty_recording)
    )
    if tracks_eligible_sessions > 0:
        tracks_coverage = sessions_with_tracks / tracks_eligible_sessions
    elif sessions_with_yolo > 0:
        tracks_coverage = 1.0
    else:
        tracks_coverage = 0.0
    tracks_missing_rate = (
        (1.0 - tracks_coverage) if sessions_with_yolo > 0 else 1.0
    )
    empty_bbox_rate = (
        empty_bbox_rejections / rejected_rows_total
        if rejected_rows_total > 0
        else 0.0
    )
    bbox_quality_score = max(
        0.0,
        min(1.0, tracks_coverage * (1.0 - empty_bbox_rate)),
    )
    latency_p95 = _percentile(latency_samples, 95.0)
    finalize_duration_p95_ms = _percentile(finalize_duration_samples, 95.0)
    frigate_catches_missed_birds_rate = (
        (frigate_catches_missed_birds_sessions / sessions_total)
        if sessions_total > 0
        else 0.0
    )
    frigate_catches_missed_birds_rate_7d_baseline = (
        (
            frigate_catches_missed_birds_sessions_7d
            / max(1, sessions_total_7d)
        )
        if sessions_total_7d > 0
        else 0.0
    )
    frigate_catches_missed_birds_rate_delta_vs_7d = (
        frigate_catches_missed_birds_rate
        - frigate_catches_missed_birds_rate_7d_baseline
    )
    lookback_hours = int(thresholds["lookback_hours"])
    current_pruned_rows_per_hour = (
        float(ingest_pruned_rows_total) / float(max(1, lookback_hours))
    )
    baseline_pruned_rows_per_hour_7d = (
        float(ingest_pruned_rows_total_7d) / float(24 * 7)
    )
    ingest_pruned_rows_per_hour_delta_vs_7d = (
        current_pruned_rows_per_hour - baseline_pruned_rows_per_hour_7d
    )
    current_moratorium_events_per_hour = (
        float(trigger_moratorium_events) / float(max(1, lookback_hours))
    )
    baseline_moratorium_events_per_hour_7d = (
        float(trigger_moratorium_events_7d) / float(24 * 7)
    )
    trigger_moratorium_events_per_hour_delta_vs_7d = (
        current_moratorium_events_per_hour
        - baseline_moratorium_events_per_hour_7d
    )
    max_frigate_rate_delta = thresholds[
        "max_frigate_catches_missed_birds_rate_delta_vs_7d"
    ]

    errors: list[str] = []
    if sessions_total <= 0:
        errors.append("no session_runtime_metrics rows in lookback window")
    if sessions_total > 0 and sessions_with_yolo <= 0:
        errors.append("no yolo runtime rows in lookback window")
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
    if (
        ingest_pruned_rows_per_hour_delta_vs_7d
        > thresholds["max_ingest_pruned_rows_per_hour_delta_vs_7d"]
    ):
        errors.append(
            "ingest_pruned_rows_per_hour_delta_vs_7d="
            f"{ingest_pruned_rows_per_hour_delta_vs_7d:.6f} > "
            "max_ingest_pruned_rows_per_hour_delta_vs_7d="
            f"{thresholds['max_ingest_pruned_rows_per_hour_delta_vs_7d']:.6f}"
        )
    if (
        frigate_catches_missed_birds_rate
        > thresholds["max_frigate_catches_missed_birds_rate"]
    ):
        errors.append(
            "frigate_catches_missed_birds_rate="
            f"{frigate_catches_missed_birds_rate:.6f} > "
            "max_frigate_catches_missed_birds_rate="
            f"{thresholds['max_frigate_catches_missed_birds_rate']:.6f}"
        )
    if (
        frigate_catches_missed_birds_rate_delta_vs_7d
        > max_frigate_rate_delta
    ):
        errors.append(
            "frigate_catches_missed_birds_rate_delta_vs_7d="
            f"{frigate_catches_missed_birds_rate_delta_vs_7d:.6f} > "
            "max_frigate_catches_missed_birds_rate_delta_vs_7d="
            f"{max_frigate_rate_delta:.6f}"
        )

    return {
        "schema": "quality_outcome_metrics@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_source": str(data_source or "local"),
        "window_hours": lookback_hours,
        "metrics": {
            "sessions_total": int(sessions_total),
            "sessions_with_yolo": int(sessions_with_yolo),
            "sessions_with_tracks": int(sessions_with_tracks),
            "sessions_fp_empty_recording": int(sessions_fp_empty_recording),
            "tracks_eligible_sessions": int(tracks_eligible_sessions),
            "blind_rate": float(round(blind_rate, 6)),
            "yolo_frames_with_tracks": int(yolo_frames_with_tracks_sum),
            "empty_bbox_rate": float(round(empty_bbox_rate, 6)),
            "tracks_coverage": float(round(tracks_coverage, 6)),
            "tracks_missing_rate": float(round(tracks_missing_rate, 6)),
            "bbox_quality_score": float(round(bbox_quality_score, 6)),
            "trigger_to_first_bbox_latency_p95_s": (
                None if latency_p95 is None else float(round(latency_p95, 6))
            ),
            "finalize_duration_p95_ms": (
                None
                if finalize_duration_p95_ms is None
                else float(round(finalize_duration_p95_ms, 6))
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
                None
                if sessions_total <= 0
                else float(round(ingest_pruned_rows_total / sessions_total, 6))
            ),
            "ingest_bbox_contract_pruned_rows_per_hour": float(
                round(current_pruned_rows_per_hour, 6)
            ),
            "ingest_bbox_contract_pruned_rows_per_hour_7d_baseline": float(
                round(baseline_pruned_rows_per_hour_7d, 6)
            ),
            "ingest_bbox_contract_pruned_rows_per_hour_delta_vs_7d": float(
                round(ingest_pruned_rows_per_hour_delta_vs_7d, 6)
            ),
            "trigger_moratorium_events": int(trigger_moratorium_events),
            "trigger_moratorium_by_source": {
                k: int(v)
                for k, v in sorted(
                    trigger_moratorium_by_source.items()
                )
            },
            "trigger_moratorium_events_per_hour": float(
                round(current_moratorium_events_per_hour, 6)
            ),
            "trigger_moratorium_events_per_hour_7d_baseline": float(
                round(baseline_moratorium_events_per_hour_7d, 6)
            ),
            "trigger_moratorium_events_per_hour_delta_vs_7d": float(
                round(
                    trigger_moratorium_events_per_hour_delta_vs_7d,
                    6,
                )
            ),
            "frigate_catches_missed_birds_sessions": int(
                frigate_catches_missed_birds_sessions
            ),
            "frigate_catches_missed_birds_rate": float(
                round(frigate_catches_missed_birds_rate, 6)
            ),
            "frigate_catches_missed_birds_by_trigger_source": {
                k: int(v)
                for k, v in sorted(
                    frigate_catches_missed_birds_by_trigger_source.items()
                )
            },
            "frigate_catches_missed_birds_by_trigger_source_rate": {
                k: float(
                    round(
                        float(v)
                        / float(
                            max(1, frigate_catches_missed_birds_sessions)
                        ),
                        6,
                    )
                )
                for k, v in sorted(
                    frigate_catches_missed_birds_by_trigger_source.items()
                )
            },
            "frigate_catches_missed_birds_rate_7d_baseline": float(
                round(frigate_catches_missed_birds_rate_7d_baseline, 6)
            ),
            "frigate_catches_missed_birds_rate_delta_vs_7d": float(
                round(frigate_catches_missed_birds_rate_delta_vs_7d, 6)
            ),
        },
        "thresholds": {
            "max_blind_rate": float(thresholds["max_blind_rate"]),
            "min_tracks_coverage": float(thresholds["min_tracks_coverage"]),
            "max_empty_bbox_rate": float(thresholds["max_empty_bbox_rate"]),
            "min_yolo_frames_with_tracks": int(
                thresholds["min_yolo_frames_with_tracks"]
            ),
            "max_ingest_pruned_rows_per_hour_delta_vs_7d": float(
                thresholds["max_ingest_pruned_rows_per_hour_delta_vs_7d"]
            ),
            "max_frigate_catches_missed_birds_rate": float(
                thresholds["max_frigate_catches_missed_birds_rate"]
            ),
            "max_frigate_catches_missed_birds_rate_delta_vs_7d": float(
                thresholds[
                    "max_frigate_catches_missed_birds_rate_delta_vs_7d"
                ]
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
    max_frigate_miss_rate = thresholds.get(
        "max_frigate_catches_missed_birds_rate"
    )
    max_frigate_miss_rate_delta = thresholds.get(
        "max_frigate_catches_missed_birds_rate_delta_vs_7d"
    )
    ingest_rows_per_hour_7d = metrics.get(
        "ingest_bbox_contract_pruned_rows_per_hour_7d_baseline"
    )
    ingest_rows_per_hour_delta = metrics.get(
        "ingest_bbox_contract_pruned_rows_per_hour_delta_vs_7d"
    )
    moratorium_by_source = metrics.get("trigger_moratorium_by_source")
    moratorium_per_hour_7d = metrics.get(
        "trigger_moratorium_events_per_hour_7d_baseline"
    )
    moratorium_per_hour_delta = metrics.get(
        "trigger_moratorium_events_per_hour_delta_vs_7d"
    )
    frigate_by_source_rate = metrics.get(
        "frigate_catches_missed_birds_by_trigger_source_rate"
    )
    lines = [
        "# Quality Outcome Metrics",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- data_source: `{report.get('data_source')}`",
        f"- gate_ok: `{gate.get('ok')}`",
        f"- sessions_total: `{metrics.get('sessions_total')}`",
        "",
        "## Metrics",
        "",
        f"- blind_rate: `{metrics.get('blind_rate')}`",
        "- yolo_frames_with_tracks: "
        f"`{metrics.get('yolo_frames_with_tracks')}`",
        f"- empty_bbox_rate: `{metrics.get('empty_bbox_rate')}`",
        "- sessions_fp_empty_recording: "
        f"`{metrics.get('sessions_fp_empty_recording')}`",
        "- tracks_eligible_sessions: "
        f"`{metrics.get('tracks_eligible_sessions')}`",
        f"- tracks_coverage: `{metrics.get('tracks_coverage')}`",
        "- tracks_missing_rate: "
        f"`{metrics.get('tracks_missing_rate')}`",
        f"- bbox_quality_score: `{metrics.get('bbox_quality_score')}`",
        "- trigger_to_first_bbox_latency_p95_s: "
        f"`{metrics.get('trigger_to_first_bbox_latency_p95_s')}`",
        "- finalize_duration_p95_ms: "
        f"`{metrics.get('finalize_duration_p95_ms')}`",
        "- ingest_bbox_contract_pruned_events: "
        f"`{metrics.get('ingest_bbox_contract_pruned_events')}`",
        "- ingest_bbox_contract_empty_events: "
        f"`{metrics.get('ingest_bbox_contract_empty_events')}`",
        "- ingest_bbox_contract_pruned_rows_total: "
        f"`{metrics.get('ingest_bbox_contract_pruned_rows_total')}`",
        "- ingest_bbox_contract_pruned_frames_total: "
        f"`{metrics.get('ingest_bbox_contract_pruned_frames_total')}`",
        "- ingest_bbox_contract_pruned_rows_per_session: "
        f"`{metrics.get('ingest_bbox_contract_pruned_rows_per_session')}`",
        "- ingest_bbox_contract_pruned_rows_per_hour: "
        f"`{metrics.get('ingest_bbox_contract_pruned_rows_per_hour')}`",
        "- ingest_bbox_contract_pruned_rows_per_hour_7d_baseline: "
        f"`{ingest_rows_per_hour_7d}`",
        "- ingest_bbox_contract_pruned_rows_per_hour_delta_vs_7d: "
        f"`{ingest_rows_per_hour_delta}`",
        "- trigger_moratorium_events: "
        f"`{metrics.get('trigger_moratorium_events')}`",
        "- trigger_moratorium_by_source: "
        f"`{moratorium_by_source}`",
        "- trigger_moratorium_events_per_hour: "
        f"`{metrics.get('trigger_moratorium_events_per_hour')}`",
        "- trigger_moratorium_events_per_hour_7d_baseline: "
        f"`{moratorium_per_hour_7d}`",
        "- trigger_moratorium_events_per_hour_delta_vs_7d: "
        f"`{moratorium_per_hour_delta}`",
        "- frigate_catches_missed_birds_sessions: "
        f"`{metrics.get('frigate_catches_missed_birds_sessions')}`",
        "- frigate_catches_missed_birds_rate: "
        f"`{metrics.get('frigate_catches_missed_birds_rate')}`",
        "- frigate_catches_missed_birds_by_trigger_source: "
        f"`{metrics.get('frigate_catches_missed_birds_by_trigger_source')}`",
        "- frigate_catches_missed_birds_by_trigger_source_rate: "
        f"`{frigate_by_source_rate}`",
        "- frigate_catches_missed_birds_rate_7d_baseline: "
        f"`{metrics.get('frigate_catches_missed_birds_rate_7d_baseline')}`",
        "- frigate_catches_missed_birds_rate_delta_vs_7d: "
        f"`{metrics.get('frigate_catches_missed_birds_rate_delta_vs_7d')}`",
        "",
        "## Thresholds",
        "",
        f"- max_blind_rate: `{thresholds.get('max_blind_rate')}`",
        f"- min_tracks_coverage: `{thresholds.get('min_tracks_coverage')}`",
        f"- max_empty_bbox_rate: `{thresholds.get('max_empty_bbox_rate')}`",
        "- min_yolo_frames_with_tracks: "
        f"`{thresholds.get('min_yolo_frames_with_tracks')}`",
        "- max_ingest_pruned_rows_per_hour_delta_vs_7d: "
        f"`{thresholds.get('max_ingest_pruned_rows_per_hour_delta_vs_7d')}`",
        "- max_frigate_catches_missed_birds_rate: "
        f"`{max_frigate_miss_rate}`",
        "- max_frigate_catches_missed_birds_rate_delta_vs_7d: "
        f"`{max_frigate_miss_rate_delta}`",
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
        "--max-ingest-pruned-rows-per-hour-delta-vs-7d",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--max-frigate-catches-missed-birds-rate",
        type=float,
        default=0.10,
    )
    parser.add_argument(
        "--max-frigate-catches-missed-birds-rate-delta-vs-7d",
        type=float,
        default=0.08,
    )
    parser.add_argument(
        "--data-source",
        default="local",
    )
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
        "max_ingest_pruned_rows_per_hour_delta_vs_7d": float(
            max(0.0, args.max_ingest_pruned_rows_per_hour_delta_vs_7d)
        ),
        "max_frigate_catches_missed_birds_rate": float(
            max(0.0, args.max_frigate_catches_missed_birds_rate)
        ),
        "max_frigate_catches_missed_birds_rate_delta_vs_7d": float(
            max(
                0.0,
                args.max_frigate_catches_missed_birds_rate_delta_vs_7d,
            )
        ),
    }
    rows = _load_rows(db_path, int(thresholds["lookback_hours"]))
    rows_7d = _load_rows(db_path, 24 * 7)
    ingest_gate_rows = _load_ingest_gate_rows(
        db_path,
        int(thresholds["lookback_hours"]),
    )
    ingest_gate_rows_7d = _load_ingest_gate_rows(db_path, 24 * 7)
    trigger_moratorium_rows = _load_trigger_moratorium_rows(
        db_path,
        int(thresholds["lookback_hours"]),
    )
    trigger_moratorium_rows_7d = _load_trigger_moratorium_rows(
        db_path,
        24 * 7,
    )
    report = evaluate(
        rows,
        thresholds,
        data_source=str(args.data_source or "local"),
        ingest_gate_rows=ingest_gate_rows,
        ingest_gate_rows_7d=ingest_gate_rows_7d,
        trigger_moratorium_rows=trigger_moratorium_rows,
        trigger_moratorium_rows_7d=trigger_moratorium_rows_7d,
        rows_7d=rows_7d,
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
