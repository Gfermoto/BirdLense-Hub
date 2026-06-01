#!/usr/bin/env python3
"""Build runtime pipeline profile (finalize/fusion/persist/first-bbox latencies)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


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
    return float(ordered[idx])


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "p50": None, "p95": None, "max": None, "mean": None}
    n = len(values)
    return {
        "n": int(n),
        "p50": round(float(_percentile(values, 50.0) or 0.0), 6),
        "p95": round(float(_percentile(values, 95.0) or 0.0), 6),
        "max": round(float(max(values)), 6),
        "mean": round(float(sum(values) / float(n)), 6),
    }


def _load_rows(db_path: Path, lookback_hours: int) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return list(
            conn.execute(
                """
                SELECT
                  payload_json,
                  trigger_to_first_bbox_latency_s,
                  finalize_duration_ms
                FROM session_runtime_metrics
                WHERE datetime(created_at) >= datetime('now', ?)
                ORDER BY id DESC
                """,
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


def build_profile(
    rows: list[sqlite3.Row],
    *,
    lookback_hours: int,
    first_bbox_warn_s: float,
    finalize_warn_ms: float,
) -> dict[str, Any]:
    first_bbox_s: list[float] = []
    finalize_ms: list[float] = []
    fusion_ms: list[float] = []
    persist_ms: list[float] = []
    create_video_ms: list[float] = []
    behavior_ms: list[float] = []
    scales_ms: list[float] = []
    dataset_crops_ms: list[float] = []
    by_slot_finalize: dict[str, list[float]] = {}

    pre_fusion_ms: list[float] = []
    critical_path_ms: list[float] = []

    for row in rows:
        payload = _extract_payload(row["payload_json"])
        slot = str(payload.get("camera_slot") or "legacy:no-slot").strip() or "legacy:no-slot"

        latency_s = _safe_float(row["trigger_to_first_bbox_latency_s"])
        if latency_s is None:
            latency_s = _safe_float(
                payload.get("trigger_to_first_bbox_latency_s")
                or payload.get("first_bbox_latency_s")
            )
        if latency_s is not None and latency_s > 0:
            first_bbox_s.append(latency_s)

        fin_ms = _safe_float(row["finalize_duration_ms"])
        if fin_ms is None:
            fin_ms = _safe_float(payload.get("finalize_duration_ms"))
        if fin_ms is not None and fin_ms > 0:
            finalize_ms.append(fin_ms)
            by_slot_finalize.setdefault(slot, []).append(fin_ms)

        f_ms = _safe_float(payload.get("fusion_duration_ms"))
        if f_ms is not None and f_ms > 0:
            fusion_ms.append(f_ms)

        p_ms = _safe_float(payload.get("persist_duration_ms"))
        if p_ms is not None and p_ms > 0:
            persist_ms.append(p_ms)

        for key, bucket in (
            ("create_video_duration_ms", create_video_ms),
            ("behavior_duration_ms", behavior_ms),
            ("scales_duration_ms", scales_ms),
            ("dataset_crops_duration_ms", dataset_crops_ms),
        ):
            stage_ms = _safe_float(payload.get(key))
            if stage_ms is not None and stage_ms > 0:
                bucket.append(stage_ms)

        pre_ms = _safe_float(payload.get("pre_fusion_duration_ms"))
        if pre_ms is not None and pre_ms > 0:
            pre_fusion_ms.append(pre_ms)

        crit_ms = _safe_float(payload.get("finalize_critical_path_ms"))
        if crit_ms is not None and crit_ms > 0:
            critical_path_ms.append(crit_ms)

    first_bbox_p95 = _percentile(first_bbox_s, 95.0)
    finalize_p95 = _percentile(finalize_ms, 95.0)
    fusion_p95 = _percentile(fusion_ms, 95.0)
    persist_p95 = _percentile(persist_ms, 95.0)

    bottleneck = "unknown"
    stage_p95 = {
        "finalize_duration_ms": finalize_p95 or 0.0,
        "fusion_duration_ms": fusion_p95 or 0.0,
        "persist_duration_ms": persist_p95 or 0.0,
    }
    if any(v > 0 for v in stage_p95.values()):
        bottleneck = max(stage_p95.items(), key=lambda item: float(item[1]))[0]

    warnings: list[str] = []
    if first_bbox_p95 is not None and float(first_bbox_p95) > float(first_bbox_warn_s):
        warnings.append(
            f"first_bbox_latency_p95 {float(first_bbox_p95):.3f}s > {float(first_bbox_warn_s):.3f}s"
        )
    if finalize_p95 is not None and float(finalize_p95) > float(finalize_warn_ms):
        warnings.append(
            f"finalize_duration_p95 {float(finalize_p95):.2f}ms > {float(finalize_warn_ms):.2f}ms"
        )

    by_slot = {
        slot: _summary(vals)
        for slot, vals in sorted(by_slot_finalize.items())
    }

    return {
        "schema": "runtime_pipeline_profile@v2",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": int(max(1, lookback_hours)),
        "profile": {
            "trigger_to_first_bbox_latency_s": _summary(first_bbox_s),
            "finalize_duration_ms": _summary(finalize_ms),
            "finalize_critical_path_ms": _summary(critical_path_ms),
            "pre_fusion_duration_ms": _summary(pre_fusion_ms),
            "fusion_duration_ms": _summary(fusion_ms),
            "persist_duration_ms": _summary(persist_ms),
            "create_video_duration_ms": _summary(create_video_ms),
            "behavior_duration_ms": _summary(behavior_ms),
            "scales_duration_ms": _summary(scales_ms),
            "dataset_crops_duration_ms": _summary(dataset_crops_ms),
        },
        "by_slot_finalize_duration_ms": by_slot,
        "bottleneck_stage_p95": bottleneck,
        "warnings": warnings,
        "ok": len(rows) > 0,
    }


def _to_md(report: dict[str, Any]) -> str:
    lines = [
        "# Runtime Pipeline Profile",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- window_hours: `{report.get('window_hours')}`",
        f"- bottleneck_stage_p95: `{report.get('bottleneck_stage_p95')}`",
        f"- ok: `{report.get('ok')}`",
        "",
        "## Profile",
        "",
        f"`{report.get('profile')}`",
        "",
        "## By slot (finalize_duration_ms)",
        "",
        f"`{report.get('by_slot_finalize_duration_ms')}`",
        "",
        "## Warnings",
        "",
    ]
    for item in report.get("warnings") or []:
        lines.append(f"- {item}")
    if not (report.get("warnings") or []):
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default="app/data/db/birdlense.db")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--first-bbox-warn-s", type=float, default=5.0)
    parser.add_argument("--finalize-warn-ms", type=float, default=5000.0)
    parser.add_argument(
        "--out-json",
        default="docs/reports/perf/runtime_pipeline_profile_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/perf/runtime_pipeline_profile_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    db_path = Path(args.db_path).expanduser()
    if not db_path.is_absolute():
        db_path = REPO / db_path
    if not db_path.exists():
        raise SystemExit(f"db file not found: {db_path}")

    rows = _load_rows(db_path, int(max(1, args.lookback_hours)))
    report = build_profile(
        rows,
        lookback_hours=int(max(1, args.lookback_hours)),
        first_bbox_warn_s=float(max(0.1, args.first_bbox_warn_s)),
        finalize_warn_ms=float(max(100.0, args.finalize_warn_ms)),
    )

    out_json = Path(args.out_json).expanduser()
    if not out_json.is_absolute():
        out_json = REPO / out_json
    out_md = Path(args.out_md).expanduser()
    if not out_md.is_absolute():
        out_md = REPO / out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_to_md(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "json": str(out_json),
                "md": str(out_md),
                "bottleneck_stage_p95": report.get("bottleneck_stage_p95"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
