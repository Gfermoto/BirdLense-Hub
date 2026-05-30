#!/usr/bin/env python3
"""Build reject_reason_dashboard@v1 from session_runtime_metrics payloads."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read_rows(db_path: Path, days: int, limit: int) -> list[dict[str, Any]]:
    cutoff_expr = f"-{max(1, int(days))} days"
    sql = """
        SELECT created_at, camera_id, payload_json
        FROM session_runtime_metrics
        WHERE datetime(created_at) >= datetime('now', ?)
        ORDER BY id DESC
        LIMIT ?
    """
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(str(db_path)) as con:
        con.row_factory = sqlite3.Row
        db_rows = con.execute(
            sql,
            (cutoff_expr, max(1, int(limit))),
        ).fetchall()
        for row in db_rows:
            raw_payload = row["payload_json"]
            if not raw_payload:
                continue
            try:
                payload = json.loads(str(raw_payload))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            rows.append(
                {
                    "created_at": str(row["created_at"] or ""),
                    "camera_id": (
                        str(row["camera_id"] or "").strip() or "unknown"
                    ),
                    "payload": payload,
                }
            )
    return rows


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_dashboard(
    *,
    rows: list[dict[str, Any]],
    top_n: int = 10,
) -> dict[str, Any]:
    stage_totals = {
        "detect_tracks_total": 0,
        "quality_accepted_total": 0,
        "fusion_persisted_total": 0,
        "fusion_dropped_total": 0,
        "decision_rejected_total": 0,
    }
    reason_counts: Counter[str] = Counter()
    camera_reason_counts: dict[str, Counter[str]] = {}

    for row in rows:
        payload = row["payload"]
        camera_id = row["camera_id"]
        stage_totals["detect_tracks_total"] += _as_int(
            payload.get("bytetrack_rows")
        )
        stage_totals["quality_accepted_total"] += _as_int(
            payload.get("pre_fusion_accepted_rows")
        )
        stage_totals["fusion_persisted_total"] += _as_int(
            payload.get("post_fusion_persisted")
        )
        stage_totals["fusion_dropped_total"] += _as_int(
            payload.get("fusion_dropped_rows")
        )
        stage_totals["decision_rejected_total"] += _as_int(
            payload.get("rejected_decision_rows")
        )

        reasons = payload.get("rejected_reason_counts")
        if not isinstance(reasons, dict):
            continue
        for raw_code, raw_count in reasons.items():
            code = str(raw_code or "").strip().lower() or "unknown"
            count = _as_int(raw_count)
            if count <= 0:
                continue
            reason_counts[code] += count
            camera_reason_counts.setdefault(
                camera_id,
                Counter(),
            )[code] += count

    total_rejects = max(0, stage_totals["decision_rejected_total"])
    pipeline = {
        "detect_to_quality_pass_ratio": (
            round(
                stage_totals["quality_accepted_total"]
                / float(max(1, stage_totals["detect_tracks_total"])),
                6,
            )
            if stage_totals["detect_tracks_total"] > 0
            else None
        ),
        "quality_to_persist_ratio": (
            round(
                stage_totals["fusion_persisted_total"]
                / float(max(1, stage_totals["quality_accepted_total"])),
                6,
            )
            if stage_totals["quality_accepted_total"] > 0
            else None
        ),
        "reject_share_of_quality": (
            round(
                stage_totals["decision_rejected_total"]
                / float(max(1, stage_totals["quality_accepted_total"])),
                6,
            )
            if stage_totals["quality_accepted_total"] > 0
            else None
        ),
    }

    top_reasons = [
        {
            "reason_code": code,
            "count": count,
            "share_of_rejected": round(
                count / float(max(1, total_rejects)),
                6,
            ),
        }
        for code, count in reason_counts.most_common(max(1, int(top_n)))
    ]

    focus_codes = (
        "rejected_static_pinned_track",
        "rejected_short_track",
        "low_confidence",
    )
    focus = {
        code: {
            "count": int(reason_counts.get(code, 0)),
            "share_of_rejected": round(
                int(reason_counts.get(code, 0)) / float(max(1, total_rejects)),
                6,
            ),
        }
        for code in focus_codes
    }

    by_camera = []
    for camera_id, counts in sorted(
        camera_reason_counts.items(),
        key=lambda item: sum(item[1].values()),
        reverse=True,
    ):
        top = counts.most_common(3)
        by_camera.append(
            {
                "camera_id": camera_id,
                "rejected_total": int(sum(counts.values())),
                "top_reasons": [
                    {"reason_code": code, "count": int(count)}
                    for code, count in top
                ],
            }
        )

    return {
        "schema": "reject_reason_dashboard@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_rows": int(len(rows)),
        "stage_totals": stage_totals,
        "pipeline_ratios": pipeline,
        "top_reasons": top_reasons,
        "focus_reasons": focus,
        "by_camera": by_camera,
        "ok": bool(len(rows) > 0),
    }


def _to_markdown(report: dict[str, Any]) -> str:
    totals = report.get("stage_totals") or {}
    ratios = report.get("pipeline_ratios") or {}
    top = report.get("top_reasons") or []
    focus = report.get("focus_reasons") or {}
    lines = [
        "# Reject Reason Dashboard",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- input_rows: `{report.get('input_rows')}`",
        "",
        "## Stage totals",
        "",
        f"- detect_tracks_total: `{totals.get('detect_tracks_total', 0)}`",
        (
            "- quality_accepted_total: "
            f"`{totals.get('quality_accepted_total', 0)}`"
        ),
        (
            "- fusion_persisted_total: "
            f"`{totals.get('fusion_persisted_total', 0)}`"
        ),
        (
            "- fusion_dropped_total: "
            f"`{totals.get('fusion_dropped_total', 0)}`"
        ),
        (
            "- decision_rejected_total: "
            f"`{totals.get('decision_rejected_total', 0)}`"
        ),
        "",
        "## Pipeline ratios",
        "",
        (
            "- detect_to_quality_pass_ratio: "
            f"`{ratios.get('detect_to_quality_pass_ratio')}`"
        ),
        (
            "- quality_to_persist_ratio: "
            f"`{ratios.get('quality_to_persist_ratio')}`"
        ),
        (
            "- reject_share_of_quality: "
            f"`{ratios.get('reject_share_of_quality')}`"
        ),
        "",
        "## Focus reasons",
        "",
        (
            "- rejected_static_pinned_track: "
            f"`{(focus.get('rejected_static_pinned_track') or {}).get('count', 0)}`"
        ),
        (
            "- rejected_short_track: "
            f"`{(focus.get('rejected_short_track') or {}).get('count', 0)}`"
        ),
        (
            "- low_confidence: "
            f"`{(focus.get('low_confidence') or {}).get('count', 0)}`"
        ),
        "",
        "## Top reasons",
        "",
    ]
    if top:
        for row in top:
            lines.append(
                "- "
                f"`{row.get('reason_code')}`: "
                f"`{row.get('count')}` "
                f"(share={row.get('share_of_rejected')})"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default="app/data/db/birdlense.db",
        help="Path to SQLite DB with session_runtime_metrics",
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=4000)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/reject_reason_dashboard/"
            "reject_reason_dashboard_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default=(
            "docs/reports/reject_reason_dashboard/"
            "reject_reason_dashboard_latest.md"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    repo = Path(__file__).resolve().parents[1]
    db_path = Path(args.db).expanduser()
    if not db_path.is_absolute():
        db_path = repo / db_path
    rows = _read_rows(db_path.resolve(), days=args.days, limit=args.limit)
    report = build_dashboard(rows=rows, top_n=args.top_n)

    out_json = Path(args.out_json).expanduser()
    if not out_json.is_absolute():
        out_json = repo / out_json
    out_md = Path(args.out_md).expanduser()
    if not out_md.is_absolute():
        out_md = repo / out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_to_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "rows": report.get("input_rows"),
                "json": str(out_json),
                "md": str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
