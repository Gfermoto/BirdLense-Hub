#!/usr/bin/env python3
"""Verify Playwright anti-flake policy contract (#539)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
E2E_DIR = REPO / "app" / "e2e"
TESTS_DIR = E2E_DIR / "tests"
CONFIG_FILE = E2E_DIR / "playwright.config.ts"


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


def _test_files() -> list[Path]:
    return sorted(TESTS_DIR.glob("*.ts"))


def _policy_violations(max_sleep_ms: int) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    timeout_re = re.compile(r"waitForTimeout\((\d+)\)")
    for path in _test_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            if "test.only(" in line or ".only(" in line:
                violations.append(
                    {
                        "file": str(path.relative_to(REPO)),
                        "line": idx,
                        "rule": "no-only",
                        "detail": "forbidden .only() in committed tests",
                    }
                )
            if "waitForTimeout(" not in line:
                continue
            m = timeout_re.search(line)
            if m is None:
                violations.append(
                    {
                        "file": str(path.relative_to(REPO)),
                        "line": idx,
                        "rule": "no-dynamic-hard-wait",
                        "detail": "waitForTimeout uses non-literal timeout",
                    }
                )
                continue
            value = int(m.group(1))
            if value > int(max_sleep_ms):
                violations.append(
                    {
                        "file": str(path.relative_to(REPO)),
                        "line": idx,
                        "rule": "max-hard-wait-ms",
                        "detail": f"waitForTimeout({value}) > {max_sleep_ms}",
                    }
                )
    return violations


def _check_config_contract() -> dict[str, bool]:
    text = CONFIG_FILE.read_text(encoding="utf-8")
    return {
        "ci_workers_single": "workers: process.env.CI ? 1" in text,
        "ci_retries_limited": "retries: process.env.CI ? 2 : 0" in text,
        "trace_on_retry": "trace: 'on-first-retry'" in text,
    }


def _quarantine_ok(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    rows = payload.get("tests") or []
    if not isinstance(rows, list):
        return False, ["tests must be an array"]
    problems: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            problems.append(f"row {idx}: must be object")
            continue
        for field in ("name", "reason", "owner", "expires_at"):
            if not str(row.get(field) or "").strip():
                problems.append(f"row {idx}: missing {field}")
    return len(problems) == 0, problems


def _flaky_rate(rows: list[dict[str, Any]]) -> tuple[float, int, int]:
    tests_total = 0
    flaky_total = 0
    for row in rows:
        try:
            tests_total += int(row.get("tests_total") or 0)
            flaky_total += int(row.get("flaky_total") or 0)
        except (TypeError, ValueError):
            continue
    rate = (
        (float(flaky_total) / float(tests_total))
        if tests_total > 0
        else 0.0
    )
    return rate, tests_total, flaky_total


def evaluate_antiflake(
    *,
    max_sleep_ms: int,
    max_flaky_rate: float,
    quarantine_payload: dict[str, Any],
    flaky_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    violations = _policy_violations(max_sleep_ms=max_sleep_ms)
    cfg = _check_config_contract()
    quarantine_ok, quarantine_issues = _quarantine_ok(quarantine_payload)
    rate, tests_total, flaky_total = _flaky_rate(flaky_rows)
    flaky_ok = bool(rate <= float(max_flaky_rate))
    ok = bool(
        len(violations) == 0
        and all(cfg.values())
        and quarantine_ok
        and flaky_ok
    )
    return {
        "schema": "playwright_antiflake@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": {
            "max_hard_wait_ms": int(max_sleep_ms),
            "max_flaky_rate": float(max_flaky_rate),
        },
        "checks": {
            "policy_violations": violations,
            "config_contract": cfg,
            "quarantine_ok": quarantine_ok,
            "quarantine_issues": quarantine_issues,
            "flaky_rate": round(rate, 6),
            "tests_total": int(tests_total),
            "flaky_total": int(flaky_total),
            "flaky_rate_ok": flaky_ok,
        },
        "ok": ok,
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    violations = checks.get("policy_violations") or []
    lines = [
        "# Playwright Anti-Flake Report",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- flaky_rate: `{checks.get('flaky_rate')}`",
        (
            "- max_flaky_rate: "
            f"`{(report.get('policy') or {}).get('max_flaky_rate')}`"
        ),
        f"- policy_violations: `{len(violations)}`",
        f"- quarantine_ok: `{checks.get('quarantine_ok')}`",
        f"- ok: `{report.get('ok')}`",
        "",
        "## Violations",
        "",
    ]
    if not violations:
        lines.append("- none")
    else:
        for row in violations:
            lines.append(
                f"- `{row.get('file')}:{row.get('line')}` `{row.get('rule')}`"
            )
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quarantine",
        default="docs/reports/e2e_flake/quarantine_tests.json",
    )
    parser.add_argument(
        "--history",
        default="docs/reports/e2e_flake/flaky_history.jsonl",
    )
    parser.add_argument("--max-hard-wait-ms", type=int, default=500)
    parser.add_argument("--max-flaky-rate", type=float, default=0.15)
    parser.add_argument(
        "--out-json",
        default="docs/reports/e2e_flake/playwright_antiflake_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/e2e_flake/playwright_antiflake_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    quarantine = Path(args.quarantine).expanduser()
    if not quarantine.is_absolute():
        quarantine = REPO / quarantine
    history = Path(args.history).expanduser()
    if not history.is_absolute():
        history = REPO / history
    report = evaluate_antiflake(
        max_sleep_ms=int(args.max_hard_wait_ms),
        max_flaky_rate=float(args.max_flaky_rate),
        quarantine_payload=_read_json(quarantine),
        flaky_rows=_read_jsonl(history),
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
