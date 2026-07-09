#!/usr/bin/env python3
"""Verify OpenAPI governance with Spectral lint contract (#532)."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        out = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return int(exc.returncode), str(exc.stdout or "")
    return int(out.returncode), str(out.stdout or "")


def _error_count_from_spectral(stdout: str) -> int:
    raw = stdout.strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, list):
        return 0
    count = 0
    for row in payload:
        if not isinstance(row, dict):
            continue
        sev = str(row.get("severity") or "").strip().lower()
        if sev == "0" or sev == "error":
            count += 1
    return int(count)


def evaluate_governance(
    *,
    ruleset_present: bool,
    spectral_ran: bool,
    error_count: int,
    max_errors: int,
) -> dict[str, Any]:
    ok = bool(ruleset_present and spectral_ran and int(error_count) <= int(max_errors))
    return {
        "schema": "openapi_governance@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": {
            "spectral_ruleset_present": bool(ruleset_present),
            "spectral_ran": bool(spectral_ran),
            "spectral_error_count": int(error_count),
            "max_allowed_errors": int(max_errors),
        },
        "ok": ok,
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    return "\n".join(
        [
            "# OpenAPI Governance Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            (
                "- spectral_ruleset_present: "
                f"`{checks.get('spectral_ruleset_present')}`"
            ),
            f"- spectral_ran: `{checks.get('spectral_ran')}`",
            f"- spectral_error_count: `{checks.get('spectral_error_count')}`",
            f"- max_allowed_errors: `{checks.get('max_allowed_errors')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/openapi_governance/"
            "openapi_governance_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/openapi_governance/openapi_governance_latest.md",
    )
    parser.add_argument("--max-errors", type=int, default=80)
    return parser.parse_args()


def main() -> int:
    args = _args()
    ruleset = REPO / ".spectral.yaml"
    rc, stdout = _run(
        [
            "npx",
            "--yes",
            "@stoplight/spectral-cli",
            "lint",
            "app/web/openapi.yaml",
            "--ruleset",
            str(ruleset),
            "--format",
            "json",
        ]
    )
    error_count = _error_count_from_spectral(stdout)
    report = evaluate_governance(
        ruleset_present=ruleset.is_file(),
        spectral_ran=bool(rc in (0, 1)),
        error_count=error_count,
        max_errors=int(args.max_errors),
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
