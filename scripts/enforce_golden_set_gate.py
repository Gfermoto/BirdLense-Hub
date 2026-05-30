#!/usr/bin/env python3
"""Mandatory golden-set gate for model/config changes (#534)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

GATE_PATTERNS = (
    "app/processor/models/**",
    "app/processor/src/detection_*.py",
    "app/processor/src/decision_maker.py",
    "app/processor/src/detection_quality.py",
    "app/processor/src/detection_fusion.py",
    "app/app_config/default_config.yaml",
    "app/app_config/user_config*.yaml",
)

GATE_COMMANDS = (
    "make validate-pipeline-golden",
    "python3 scripts/stress_test_offline.py --no-yolo",
)


def _git_changed_files(base_ref: str, head_ref: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def requires_golden_gate(changed_files: list[str]) -> tuple[bool, list[str]]:
    matched: list[str] = []
    for file_path in changed_files:
        norm = str(file_path).strip().replace("\\", "/")
        if not norm:
            continue
        if any(fnmatch(norm, pattern) for pattern in GATE_PATTERNS):
            matched.append(norm)
    return bool(matched), sorted(set(matched))


def _run_command(command: str) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=REPO,
        shell=True,
        text=True,
        capture_output=True,
    )
    elapsed = round(time.time() - started, 3)
    return {
        "command": command,
        "exit_code": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "elapsed_sec": elapsed,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
    }


def build_report(
    *,
    changed_files: list[str],
    trigger_files: list[str],
    runs: list[dict[str, Any]],
    skipped: bool,
    base_ref: str,
    head_ref: str,
) -> dict[str, Any]:
    return {
        "schema": "golden_set_mandatory_gate@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "changed_files_count": int(len(changed_files)),
        "changed_files": sorted(changed_files),
        "gate_required": bool(not skipped),
        "gate_trigger_files": sorted(trigger_files),
        "runs": runs,
        "ok": bool(skipped or all(bool(item.get("ok")) for item in runs)),
    }


def _to_md(report: dict[str, Any]) -> str:
    lines = [
        "# Golden Set Mandatory Gate",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- base_ref: `{report.get('base_ref')}`",
        f"- head_ref: `{report.get('head_ref')}`",
        f"- gate_required: `{report.get('gate_required')}`",
        f"- ok: `{report.get('ok')}`",
        "",
        "## Trigger files",
        "",
    ]
    triggers = report.get("gate_trigger_files") or []
    if triggers:
        lines.extend(f"- `{path}`" for path in triggers)
    else:
        lines.append("- none")
    lines.extend(["", "## Runs", ""])
    runs = report.get("runs") or []
    if runs:
        for row in runs:
            lines.append(
                "- "
                f"`{row.get('command')}` -> ok=`{row.get('ok')}` "
                f"(exit={row.get('exit_code')}, {row.get('elapsed_sec')}s)"
            )
    else:
        lines.append("- skipped")
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="HEAD~1")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Explicit changed file path (repeatable).",
    )
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/golden_set_gate/"
            "golden_set_gate_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default=(
            "docs/reports/golden_set_gate/"
            "golden_set_gate_latest.md"
        ),
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Execute golden commands when gate is required.",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    explicit_files = [
        str(item).strip()
        for item in (args.changed_file or [])
        if str(item).strip()
    ]
    changed = explicit_files or _git_changed_files(args.base_ref, args.head_ref)
    required, trigger_files = requires_golden_gate(changed)
    runs: list[dict[str, Any]] = []
    if required and args.enforce:
        for command in GATE_COMMANDS:
            result = _run_command(command)
            runs.append(result)
            if not bool(result.get("ok")):
                break
    report = build_report(
        changed_files=changed,
        trigger_files=trigger_files,
        runs=runs,
        skipped=bool(not required),
        base_ref=args.base_ref,
        head_ref=args.head_ref,
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
                "gate_required": bool(report.get("gate_required")),
                "trigger_files": report.get("gate_trigger_files", []),
                "json": str(out_json),
                "md": str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
