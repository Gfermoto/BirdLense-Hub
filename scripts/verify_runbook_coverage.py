#!/usr/bin/env python3
"""Verify incident runbook coverage and weekly validation cadence (#543)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _parse_ts(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def evaluate_coverage(
    *,
    catalog: dict[str, Any],
    validation_history: list[dict[str, Any]],
    min_cycles_per_week: int,
) -> dict[str, Any]:
    incidents = catalog.get("incidents") or []
    if not isinstance(incidents, list):
        incidents = []
    missing_runbooks: list[str] = []
    rows: list[dict[str, Any]] = []
    for item in incidents:
        if not isinstance(item, dict):
            continue
        iid = str(item.get("id") or "").strip()
        runbook_rel = str(item.get("runbook") or "").strip()
        runbook_path = REPO / runbook_rel
        exists = bool(runbook_rel and runbook_path.is_file())
        if not exists:
            missing_runbooks.append(iid or runbook_rel or "unknown")
        rows.append(
            {
                "id": iid,
                "title": str(item.get("title") or ""),
                "runbook": runbook_rel,
                "exists": exists,
            }
        )
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=7)
    weekly_cycles = 0
    for row in validation_history:
        ts = _parse_ts(row.get("checked_at"))
        if ts is not None and ts >= cutoff:
            weekly_cycles += 1
    coverage_ok = bool(not missing_runbooks and len(rows) > 0)
    cadence_ok = bool(weekly_cycles >= max(1, int(min_cycles_per_week)))
    ok = bool(coverage_ok and cadence_ok)
    return {
        "schema": "runbook_coverage_report@v1",
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": {
            "covered": int(sum(1 for row in rows if row.get("exists"))),
            "total": int(len(rows)),
            "missing_runbooks": missing_runbooks,
            "ok": coverage_ok,
        },
        "validation_cadence": {
            "cycles_last_7d": int(weekly_cycles),
            "required_min_cycles": int(max(1, int(min_cycles_per_week))),
            "ok": cadence_ok,
        },
        "incidents": rows,
        "ok": ok,
    }


def _to_md(report: dict[str, Any], catalog_file: Path) -> str:
    coverage = report.get("coverage") or {}
    cadence = report.get("validation_cadence") or {}
    lines = [
        "# Runbook Coverage Report",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- catalog_file: `{catalog_file}`",
        f"- covered: `{coverage.get('covered')}/{coverage.get('total')}`",
        f"- missing_runbooks: `{len(coverage.get('missing_runbooks') or [])}`",
        (
            "- validation_cycles_last_7d: "
            f"`{cadence.get('cycles_last_7d')}`"
        ),
        (
            "- validation_required_min: "
            f"`{cadence.get('required_min_cycles')}`"
        ),
        f"- ok: `{report.get('ok')}`",
        "",
        "## Missing Runbooks",
        "",
    ]
    missing = coverage.get("missing_runbooks") or []
    if missing:
        for item in missing:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog",
        default="docs/reports/runbook_coverage/incident_catalog.json",
    )
    parser.add_argument(
        "--history",
        default="docs/reports/runbook_coverage/validation_history.jsonl",
    )
    parser.add_argument("--record-validation", action="store_true")
    parser.add_argument("--min-cycles-per-week", type=int, default=1)
    parser.add_argument(
        "--out-json",
        default="docs/reports/runbook_coverage/runbook_coverage_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/runbook_coverage/runbook_coverage_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    catalog_file = Path(args.catalog).expanduser()
    if not catalog_file.is_absolute():
        catalog_file = REPO / catalog_file
    history_file = Path(args.history).expanduser()
    if not history_file.is_absolute():
        history_file = REPO / history_file
    if args.record_validation:
        _append_jsonl(
            history_file,
            {
                "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": "verify_runbook_coverage",
            },
        )
    report = evaluate_coverage(
        catalog=_load_json(catalog_file),
        validation_history=_read_jsonl(history_file),
        min_cycles_per_week=max(1, int(args.min_cycles_per_week)),
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
    out_md.write_text(_to_md(report, catalog_file), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "json": str(out_json),
                "md": str(out_md),
            }
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
