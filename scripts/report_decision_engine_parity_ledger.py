#!/usr/bin/env python3
"""Build decision_engine_parity_ledger@v1 from session runtime payloads."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_rows(db_path: Path, days: int, limit: int) -> list[dict[str, Any]]:
    sql = """
        SELECT created_at, payload_json
        FROM session_runtime_metrics
        WHERE datetime(created_at) >= datetime('now', ?)
        ORDER BY id DESC
        LIMIT ?
    """
    out: list[dict[str, Any]] = []
    with sqlite3.connect(str(db_path)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            sql,
            (f"-{max(1, int(days))} days", max(1, int(limit))),
        ).fetchall()
    for row in rows:
        raw_payload = row["payload_json"]
        if not raw_payload:
            continue
        try:
            payload = json.loads(str(raw_payload))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        out.append(
            {
                "created_at": str(row["created_at"] or ""),
                "payload": payload,
            }
        )
    return out


def build_ledger(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_day: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "sessions_total": 0,
            "frigate_window_sessions": 0,
            "persisted_sessions": 0,
            "fusion_no_accepted_sessions": 0,
            "fusion_no_accepted_static_pinned": 0,
            "fusion_no_accepted_short_track": 0,
            "fusion_no_accepted_low_confidence": 0,
        }
    )

    for row in rows:
        created = str(row["created_at"] or "")
        day = created[:10] if len(created) >= 10 else "unknown"
        payload = row["payload"]
        d = by_day[day]
        d["sessions_total"] += 1
        d["frigate_window_sessions"] += (
            1
            if _as_int(
                payload.get("session_extended_by_frigate_only")
            ) > 0
            else 0
        )
        d["persisted_sessions"] += (
            1
            if _as_int(payload.get("post_fusion_persisted")) > 0
            else 0
        )

        pre_fusion = _as_int(payload.get("pre_fusion_accepted_rows"))
        post_fusion = _as_int(payload.get("post_fusion_persisted"))
        no_accepted = pre_fusion > 0 and post_fusion == 0
        if no_accepted:
            d["fusion_no_accepted_sessions"] += 1
        reasons = payload.get("rejected_reason_counts")
        if not no_accepted or not isinstance(reasons, dict):
            continue
        d["fusion_no_accepted_static_pinned"] += _as_int(
            reasons.get("rejected_static_pinned_track")
        )
        d["fusion_no_accepted_short_track"] += _as_int(
            reasons.get("rejected_short_track")
        )
        d["fusion_no_accepted_low_confidence"] += _as_int(
            reasons.get("low_confidence")
        )

    rows_out = []
    for day in sorted(by_day.keys()):
        item = dict(by_day[day])
        item["day"] = day
        frigate_sessions = max(1, item["frigate_window_sessions"])
        item["fusion_no_accepted_share_vs_frigate"] = round(
            item["fusion_no_accepted_sessions"] / float(frigate_sessions),
            6,
        )
        rows_out.append(item)

    return {
        "schema": "decision_engine_parity_ledger@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "row_count": int(len(rows_out)),
        "rows": rows_out,
        "ok": bool(len(rows_out) > 0),
    }


def _to_md(report: dict[str, Any]) -> str:
    lines = [
        "# Decision Engine Parity Ledger",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- row_count: `{report.get('row_count')}`",
        "",
        (
            "| day | sessions | frigate_window | persisted | "
            "FUSION_NO_ACCEPTED | share_vs_frigate | "
            "static_pinned | short_track | low_confidence |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("rows") or []:
        lines.append(
            "| "
            f"{row.get('day')} | "
            f"{row.get('sessions_total', 0)} | "
            f"{row.get('frigate_window_sessions', 0)} | "
            f"{row.get('persisted_sessions', 0)} | "
            f"{row.get('fusion_no_accepted_sessions', 0)} | "
            f"{row.get('fusion_no_accepted_share_vs_frigate', 0)} | "
            f"{row.get('fusion_no_accepted_static_pinned', 0)} | "
            f"{row.get('fusion_no_accepted_short_track', 0)} | "
            f"{row.get('fusion_no_accepted_low_confidence', 0)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="app/data/db/birdlense.db")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/decision_engine_parity_ledger/"
            "decision_engine_parity_ledger_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default=(
            "docs/reports/decision_engine_parity_ledger/"
            "decision_engine_parity_ledger_latest.md"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    repo = Path(__file__).resolve().parents[1]
    db_path = Path(args.db).expanduser()
    if not db_path.is_absolute():
        db_path = repo / db_path
    rows = _load_rows(db_path.resolve(), days=args.days, limit=args.limit)
    report = build_ledger(rows)

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
    out_md.write_text(_to_md(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "rows": report.get("row_count"),
                "json": str(out_json),
                "md": str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
