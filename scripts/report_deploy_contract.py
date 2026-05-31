#!/usr/bin/env python3
"""Build deploy idempotency and rollback-readiness contract report (#545)."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _git(cmd: list[str]) -> str:
    try:
        out = subprocess.run(
            cmd,
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    return out.stdout.strip()


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


def _file_contains(path: Path, needle: str) -> bool:
    if not path.is_file():
        return False
    return needle in path.read_text(encoding="utf-8")


def evaluate_contract(runs: list[dict[str, Any]]) -> dict[str, Any]:
    repeated = 0
    repeated_success = 0
    for prev, cur in zip(runs, runs[1:]):
        prev_commit = str(prev.get("git_commit") or "").strip()
        cur_commit = str(cur.get("git_commit") or "").strip()
        if not prev_commit or not cur_commit or prev_commit != cur_commit:
            continue
        repeated += 1
        if str(cur.get("status") or "").strip().lower() == "success":
            repeated_success += 1
    idempotency_rate = (
        float(repeated_success) / float(repeated) if repeated > 0 else 1.0
    )
    rollback_checks = {
        "restore_script_present": (
            REPO / "scripts" / "restore-config.sh"
        ).is_file(),
        "rollback_runbook_present": (
            REPO / "docs" / "runbooks" / "deploy-rollback-contract.md"
        ).is_file(),
        "deploy_has_backup_step": _file_contains(
            REPO / "scripts" / "public" / "deploy.sh",
            ".bak.deploy-",
        ),
        "deploy_mentions_restore": _file_contains(
            REPO / "scripts" / "public" / "deploy.sh",
            "restore-config",
        ),
    }
    rollback_ready = all(rollback_checks.values())
    return {
        "schema": "deploy_contract@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "idempotency": {
            "repeated_deploy_samples": int(repeated),
            "repeated_success_samples": int(repeated_success),
            "pass_rate": round(idempotency_rate, 6),
            "ok": bool(idempotency_rate >= 1.0),
        },
        "rollback_readiness": {
            **rollback_checks,
            "ok": bool(rollback_ready),
        },
        "ok": bool(idempotency_rate >= 1.0 and rollback_ready),
    }


def _to_md(report: dict[str, Any]) -> str:
    idem = report.get("idempotency") or {}
    rb = report.get("rollback_readiness") or {}
    return "\n".join(
        [
            "# Deploy Contract Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- idempotency_pass_rate: `{idem.get('pass_rate')}`",
            (
                "- repeated_deploy_samples: "
                f"`{idem.get('repeated_deploy_samples')}`"
            ),
            f"- rollback_ready: `{rb.get('ok')}`",
            f"- ok: `{report.get('ok')}`",
            "",
            "## Rollback Checks",
            "",
            (
                "- restore_script_present: "
                f"`{rb.get('restore_script_present')}`"
            ),
            (
                "- rollback_runbook_present: "
                f"`{rb.get('rollback_runbook_present')}`"
            ),
            (
                "- deploy_has_backup_step: "
                f"`{rb.get('deploy_has_backup_step')}`"
            ),
            (
                "- deploy_mentions_restore: "
                f"`{rb.get('deploy_mentions_restore')}`"
            ),
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        default="docs/reports/deploy_contract/deploy_runs.jsonl",
    )
    parser.add_argument("--record-run", action="store_true")
    parser.add_argument(
        "--status",
        choices=("success", "failed"),
        default="success",
    )
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument(
        "--out-json",
        default="docs/reports/deploy_contract/deploy_contract_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/deploy_contract/deploy_contract_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    history = Path(args.history).expanduser()
    if not history.is_absolute():
        history = REPO / history
    if args.record_run:
        _append_jsonl(
            history,
            {
                "deployed_at": datetime.now(UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "git_commit": _git(["git", "rev-parse", "HEAD"]),
                "status": str(args.status),
            },
        )
    if args.skip_report:
        print(json.dumps({"ok": True, "recorded": bool(args.record_run)}))
        return 0
    report = evaluate_contract(_read_jsonl(history))
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
