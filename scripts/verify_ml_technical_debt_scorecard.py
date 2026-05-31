#!/usr/bin/env python3
"""Verify ML technical debt scorecard contract (#537)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def evaluate_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    rows = scorecard.get("checks") or []
    if not isinstance(rows, list):
        rows = []
    min_checks_total = int(scorecard.get("min_checks_total") or 28)
    max_high_risk_open = int(scorecard.get("max_high_risk_open") or 0)
    allowed_status = {
        str(item).strip().lower()
        for item in (scorecard.get("allowed_status") or [])
        if str(item).strip()
    }
    allowed_risk = {
        str(item).strip().lower()
        for item in (scorecard.get("allowed_risk") or [])
        if str(item).strip()
    }

    seen: set[str] = set()
    duplicates: list[str] = []
    missing_owner: list[str] = []
    invalid_status: list[str] = []
    invalid_risk: list[str] = []
    high_risk_open = 0
    status_counts = {"closed": 0, "in_progress": 0, "open": 0}
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    rows_out: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        owner = str(row.get("owner") or "").strip()
        status = str(row.get("status") or "").strip().lower()
        risk = str(row.get("risk") or "").strip().lower()
        if cid in seen:
            duplicates.append(cid)
        seen.add(cid)
        if not owner:
            missing_owner.append(cid or "unknown")
        if status not in allowed_status:
            invalid_status.append(cid or status or "unknown")
        if risk not in allowed_risk:
            invalid_risk.append(cid or risk or "unknown")
        if status in status_counts:
            status_counts[status] += 1
        if risk in risk_counts:
            risk_counts[risk] += 1
        if risk == "high" and status == "open":
            high_risk_open += 1
        rows_out.append(
            {
                "id": cid,
                "owner_present": bool(owner),
                "status": status,
                "risk": risk,
            }
        )

    checks = {
        "min_checks_total_ok": len(rows_out) >= min_checks_total,
        "duplicates_ok": len(duplicates) == 0,
        "owner_coverage_ok": len(missing_owner) == 0,
        "status_values_ok": len(invalid_status) == 0,
        "risk_values_ok": len(invalid_risk) == 0,
        "high_risk_open_ok": high_risk_open <= max_high_risk_open,
    }
    return {
        "schema": "ml_technical_debt_scorecard_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "checks_total": len(rows_out),
            "min_checks_total": min_checks_total,
            "high_risk_open": high_risk_open,
            "max_high_risk_open": max_high_risk_open,
            "status_counts": status_counts,
            "risk_counts": risk_counts,
        },
        "drift": {
            "duplicate_ids": duplicates,
            "missing_owner": missing_owner,
            "invalid_status": invalid_status,
            "invalid_risk": invalid_risk,
        },
        "scorecard": rows_out,
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    drift = report.get("drift") or {}
    checks = report.get("checks") or {}
    return "\n".join(
        [
            "# ML Technical Debt Scorecard Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- checks_total: `{summary.get('checks_total')}`",
            (
                "- high_risk_open: "
                f"`{summary.get('high_risk_open')}` "
                f"(limit `{summary.get('max_high_risk_open')}`)"
            ),
            f"- missing_owner: `{len(drift.get('missing_owner') or [])}`",
            f"- duplicate_ids: `{len(drift.get('duplicate_ids') or [])}`",
            f"- invalid_status: `{len(drift.get('invalid_status') or [])}`",
            f"- invalid_risk: `{len(drift.get('invalid_risk') or [])}`",
            f"- high_risk_open_ok: `{checks.get('high_risk_open_ok')}`",
            f"- owner_coverage_ok: `{checks.get('owner_coverage_ok')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scorecard",
        default="docs/reports/ml_debt/ml_technical_debt_scorecard.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/ml_debt/ml_technical_debt_scorecard_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/ml_debt/ml_technical_debt_scorecard_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    scorecard_file = Path(args.scorecard).expanduser()
    if not scorecard_file.is_absolute():
        scorecard_file = REPO / scorecard_file
    report = evaluate_scorecard(_read_json(scorecard_file))
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
                "json": str(out_json),
                "md": str(out_md),
            }
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
