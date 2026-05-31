#!/usr/bin/env python3
"""Verify burst/reconnect resilience contract for integrations (#548)."""

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


def _safe_ratio(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return float(num) / float(den)


def evaluate_resilience(
    *,
    contract: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    required = {
        str(item).strip()
        for item in (contract.get("required_scenarios") or [])
        if str(item).strip()
    }
    min_rows = int(contract.get("min_history_rows") or 0)
    min_pass_rate = float(contract.get("min_pass_rate") or 0.95)
    max_event_loss_rate = float(contract.get("max_event_loss_rate") or 0.02)
    max_recovery_p95 = float(
        contract.get("max_reconnect_recovery_ms_p95") or 5000
    )

    scenario_seen: set[str] = set()
    rows_total = 0
    runs_total = 0
    runs_passed = 0
    weighted_loss_num = 0.0
    weighted_recovery_num = 0.0
    by_scenario: dict[str, dict[str, float]] = {}

    for row in history:
        scenario = str(row.get("scenario") or "").strip()
        if not scenario:
            continue
        scenario_seen.add(scenario)
        rows_total += 1
        total = int(row.get("runs_total") or 0)
        passed = int(row.get("runs_passed") or 0)
        loss = float(row.get("event_loss_rate") or 0.0)
        recovery = float(row.get("reconnect_recovery_ms_p95") or 0.0)

        runs_total += max(0, total)
        runs_passed += max(0, min(total, passed))
        weighted_loss_num += loss * max(0, total)
        weighted_recovery_num += recovery * max(0, total)

        slot = by_scenario.setdefault(
            scenario,
            {
                "rows": 0.0,
                "runs_total": 0.0,
                "runs_passed": 0.0,
                "weighted_loss_num": 0.0,
                "weighted_recovery_num": 0.0,
            },
        )
        slot["rows"] += 1
        slot["runs_total"] += max(0, total)
        slot["runs_passed"] += max(0, min(total, passed))
        slot["weighted_loss_num"] += loss * max(0, total)
        slot["weighted_recovery_num"] += recovery * max(0, total)

    missing_scenarios = sorted(
        item for item in required if item not in scenario_seen
    )
    global_pass_rate = _safe_ratio(runs_passed, runs_total)
    global_event_loss_rate = _safe_ratio(weighted_loss_num, runs_total)
    global_recovery_p95 = _safe_ratio(weighted_recovery_num, runs_total)

    scenario_rows: list[dict[str, Any]] = []
    for scenario in sorted(required | scenario_seen):
        slot = by_scenario.get(scenario, {})
        s_runs_total = float(slot.get("runs_total") or 0.0)
        s_runs_passed = float(slot.get("runs_passed") or 0.0)
        s_loss = _safe_ratio(
            float(slot.get("weighted_loss_num") or 0.0),
            s_runs_total,
        )
        s_recovery = _safe_ratio(
            float(slot.get("weighted_recovery_num") or 0.0),
            s_runs_total,
        )
        scenario_rows.append(
            {
                "scenario": scenario,
                "rows": int(slot.get("rows") or 0),
                "runs_total": int(s_runs_total),
                "runs_passed": int(s_runs_passed),
                "pass_rate": round(
                    _safe_ratio(s_runs_passed, s_runs_total),
                    6,
                ),
                "event_loss_rate": round(s_loss, 6),
                "reconnect_recovery_ms_p95": round(s_recovery, 2),
                "required": scenario in required,
            }
        )

    checks = {
        "history_rows_ok": rows_total >= min_rows,
        "required_scenarios_ok": len(missing_scenarios) == 0,
        "pass_rate_ok": global_pass_rate >= min_pass_rate,
        "event_loss_ok": global_event_loss_rate <= max_event_loss_rate,
        "recovery_p95_ok": global_recovery_p95 <= max_recovery_p95,
    }
    return {
        "schema": "event_burst_reconnect_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thresholds": {
            "min_history_rows": min_rows,
            "min_pass_rate": min_pass_rate,
            "max_event_loss_rate": max_event_loss_rate,
            "max_reconnect_recovery_ms_p95": max_recovery_p95,
        },
        "checks": checks,
        "summary": {
            "history_rows": rows_total,
            "required_scenarios": len(required),
            "covered_scenarios": len(required - set(missing_scenarios)),
            "runs_total": runs_total,
            "runs_passed": runs_passed,
            "pass_rate": round(global_pass_rate, 6),
            "event_loss_rate": round(global_event_loss_rate, 6),
            "reconnect_recovery_ms_p95": round(global_recovery_p95, 2),
        },
        "drift": {
            "missing_required_scenarios": missing_scenarios,
        },
        "scenarios": scenario_rows,
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    summary = report.get("summary") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# Event Burst & Reconnect Resilience Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- history_rows: `{summary.get('history_rows')}`",
            f"- pass_rate: `{summary.get('pass_rate')}`",
            f"- event_loss_rate: `{summary.get('event_loss_rate')}`",
            (
                "- reconnect_recovery_ms_p95: "
                f"`{summary.get('reconnect_recovery_ms_p95')}`"
            ),
            (
                "- missing_required_scenarios: "
                f"`{len(drift.get('missing_required_scenarios') or [])}`"
            ),
            f"- pass_rate_ok: `{checks.get('pass_rate_ok')}`",
            f"- event_loss_ok: `{checks.get('event_loss_ok')}`",
            f"- recovery_p95_ok: `{checks.get('recovery_p95_ok')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default=(
            "docs/reports/integrations/"
            "event_burst_reconnect_contract.json"
        ),
    )
    parser.add_argument(
        "--history",
        default=(
            "docs/reports/integrations/"
            "event_burst_reconnect_history.jsonl"
        ),
    )
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/integrations/"
            "event_burst_reconnect_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default=(
            "docs/reports/integrations/"
            "event_burst_reconnect_latest.md"
        ),
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
    report = evaluate_resilience(
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
