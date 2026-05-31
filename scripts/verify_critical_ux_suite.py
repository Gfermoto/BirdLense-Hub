#!/usr/bin/env python3
"""Verify critical UX flow reliability suite contract (#540)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SMOKE_SPEC = REPO / "app" / "e2e" / "tests" / "smoke.spec.ts"


def _read_json(path: Path) -> dict[str, Any]:
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
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _smoke_tests() -> list[str]:
    text = SMOKE_SPEC.read_text(encoding="utf-8")
    return re.findall(r"test\('([^']+)'", text)


def _suite_pass_rate(rows: list[dict[str, Any]]) -> tuple[float, int, int]:
    total = 0
    passed = 0
    for row in rows:
        if str(row.get("suite") or "").strip() != "smoke":
            continue
        try:
            total += int(row.get("total") or 0)
            passed += int(row.get("passed") or 0)
        except (TypeError, ValueError):
            continue
    rate = (float(passed) / float(total)) if total > 0 else 0.0
    return rate, total, passed


def evaluate_suite(
    *,
    contract: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    tests = _smoke_tests()
    rows: list[dict[str, Any]] = []
    missing = 0
    for flow in contract.get("flows") or []:
        if not isinstance(flow, dict):
            continue
        patt = str(flow.get("test_name_pattern") or "").strip()
        matched = any(patt.lower() in test_name.lower() for test_name in tests)
        if not matched:
            missing += 1
        rows.append(
            {
                "id": str(flow.get("id") or ""),
                "path": str(flow.get("path") or ""),
                "test_name_pattern": patt,
                "covered": matched,
            }
        )
    min_pass_rate = float(contract.get("min_pass_rate") or 0.95)
    pass_rate, total, passed = _suite_pass_rate(history)
    coverage_ok = bool(missing == 0 and len(rows) > 0)
    pass_rate_ok = bool(pass_rate >= min_pass_rate)
    ok = bool(coverage_ok and pass_rate_ok)
    return {
        "schema": "critical_ux_suite_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": {
            "flows_total": len(rows),
            "flows_covered": int(sum(1 for row in rows if row.get("covered"))),
            "missing_total": int(missing),
            "ok": coverage_ok,
        },
        "reliability": {
            "suite_pass_rate": round(pass_rate, 6),
            "suite_total": int(total),
            "suite_passed": int(passed),
            "min_pass_rate": min_pass_rate,
            "ok": pass_rate_ok,
        },
        "flows": rows,
        "ok": ok,
    }


def _to_md(report: dict[str, Any]) -> str:
    cov = report.get("coverage") or {}
    rel = report.get("reliability") or {}
    return "\n".join(
        [
            "# Critical UX Suite Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            (
                f"- coverage: "
                f"`{cov.get('flows_covered')}/{cov.get('flows_total')}`"
            ),
            f"- missing_total: `{cov.get('missing_total')}`",
            f"- suite_pass_rate: `{rel.get('suite_pass_rate')}`",
            f"- min_pass_rate: `{rel.get('min_pass_rate')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/e2e_critical/critical_flows.json",
    )
    parser.add_argument(
        "--history",
        default="docs/reports/e2e_critical/smoke_history.jsonl",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/e2e_critical/critical_ux_suite_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/e2e_critical/critical_ux_suite_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract = Path(args.contract).expanduser()
    if not contract.is_absolute():
        contract = REPO / contract
    history = Path(args.history).expanduser()
    if not history.is_absolute():
        history = REPO / history
    report = evaluate_suite(
        contract=_read_json(contract),
        history=_read_jsonl(history),
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
                "json": str(out_json),
                "md": str(out_md),
            }
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
