#!/usr/bin/env python3
"""Verify CLI contract standardization for critical tools (#550)."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _run_probe(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO),
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return int(proc.returncode), out


def collect_cli_probes(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = registry.get("tools") or []
    if not isinstance(rows, list):
        rows = []
    probes: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        rel_path = str(row.get("path") or "").strip()
        runner = str(row.get("runner") or "python3").strip()
        owner = str(row.get("owner") or "").strip()
        tool_file = REPO / rel_path if rel_path else None
        exists = bool(tool_file and tool_file.is_file())
        help_code = -1
        invalid_code = -1
        help_has_usage = False
        structured_json_output = False
        if exists and tool_file:
            source = tool_file.read_text(encoding="utf-8")
            structured_json_output = "json.dumps(" in source
            help_cmd = [runner, str(tool_file), "--help"]
            help_code, help_out = _run_probe(help_cmd)
            help_has_usage = "usage" in help_out.lower()
            invalid_cmd = [runner, str(tool_file), "--contract-invalid-arg"]
            invalid_code, _ = _run_probe(invalid_cmd)
        probes.append(
            {
                "id": cid,
                "path": rel_path,
                "owner": owner,
                "exists": exists,
                "help_code": help_code,
                "help_has_usage": help_has_usage,
                "invalid_code": invalid_code,
                "structured_json_output": structured_json_output,
            }
        )
    return probes


def _coerce_int(value: Any, default: int = -1) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def evaluate_cli_contract(
    *,
    registry: dict[str, Any],
    probes: list[dict[str, Any]],
) -> dict[str, Any]:
    required_ids = {
        str(item).strip()
        for item in (registry.get("required_cli_ids") or [])
        if str(item).strip()
    }
    min_cli_total = int(registry.get("min_cli_total") or 0)
    require_help_exit_zero = bool(registry.get("require_help_exit_zero", True))
    require_invalid_arg_nonzero = bool(
        registry.get("require_invalid_arg_nonzero", True)
    )
    require_structured_json_output = bool(
        registry.get("require_structured_json_output", True)
    )

    seen: set[str] = set()
    missing_tools: list[str] = []
    help_failures: list[str] = []
    invalid_arg_failures: list[str] = []
    missing_usage_banner: list[str] = []
    structured_output_failures: list[str] = []
    missing_owner: list[str] = []
    rows: list[dict[str, Any]] = []

    for row in probes:
        cid = str(row.get("id") or "").strip()
        seen.add(cid)
        exists = bool(row.get("exists"))
        help_code = _coerce_int(row.get("help_code"), default=-1)
        invalid_code = _coerce_int(row.get("invalid_code"), default=-1)
        has_usage = bool(row.get("help_has_usage"))
        has_json = bool(row.get("structured_json_output"))
        owner = str(row.get("owner") or "").strip()
        if not exists:
            missing_tools.append(cid or str(row.get("path") or "unknown"))
        if require_help_exit_zero and help_code != 0:
            help_failures.append(cid or "unknown")
        if require_invalid_arg_nonzero and invalid_code == 0:
            invalid_arg_failures.append(cid or "unknown")
        if not has_usage:
            missing_usage_banner.append(cid or "unknown")
        if require_structured_json_output and not has_json:
            structured_output_failures.append(cid or "unknown")
        if not owner:
            missing_owner.append(cid or "unknown")
        rows.append(
            {
                "id": cid,
                "exists": exists,
                "help_code": help_code,
                "invalid_code": invalid_code,
                "help_has_usage": has_usage,
                "structured_json_output": has_json,
                "owner_present": bool(owner),
            }
        )

    missing_required_ids = sorted(
        item for item in required_ids if item not in seen
    )

    checks = {
        "min_cli_total_ok": len(rows) >= min_cli_total,
        "required_cli_ids_ok": len(missing_required_ids) == 0,
        "tools_exist_ok": len(missing_tools) == 0,
        "help_exit_ok": len(help_failures) == 0,
        "invalid_arg_exit_ok": len(invalid_arg_failures) == 0,
        "usage_banner_ok": len(missing_usage_banner) == 0,
        "structured_output_ok": len(structured_output_failures) == 0,
        "owner_coverage_ok": len(missing_owner) == 0,
    }
    return {
        "schema": "cli_contract_standardization_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "cli_total": len(rows),
            "min_cli_total": min_cli_total,
            "required_cli_total": len(required_ids),
        },
        "drift": {
            "missing_required_ids": missing_required_ids,
            "missing_tools": missing_tools,
            "help_failures": help_failures,
            "invalid_arg_failures": invalid_arg_failures,
            "missing_usage_banner": missing_usage_banner,
            "structured_output_failures": structured_output_failures,
            "missing_owner": missing_owner,
        },
        "tools": rows,
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    checks = report.get("checks") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# CLI Contract Standardization Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- cli_total: `{summary.get('cli_total')}`",
            f"- required_cli_total: `{summary.get('required_cli_total')}`",
            (
                "- missing_required_ids: "
                f"`{len(drift.get('missing_required_ids') or [])}`"
            ),
            f"- help_failures: `{len(drift.get('help_failures') or [])}`",
            (
                "- invalid_arg_failures: "
                f"`{len(drift.get('invalid_arg_failures') or [])}`"
            ),
            (
                "- structured_output_failures: "
                f"`{len(drift.get('structured_output_failures') or [])}`"
            ),
            f"- help_exit_ok: `{checks.get('help_exit_ok')}`",
            (
                "- invalid_arg_exit_ok: "
                f"`{checks.get('invalid_arg_exit_ok')}`"
            ),
            f"- structured_output_ok: `{checks.get('structured_output_ok')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default="docs/reports/tooling/cli_contract_registry.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/tooling/cli_contract_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/tooling/cli_contract_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    registry_file = Path(args.registry).expanduser()
    if not registry_file.is_absolute():
        registry_file = REPO / registry_file
    registry = _read_json(registry_file)
    probes = collect_cli_probes(registry)
    report = evaluate_cli_contract(registry=registry, probes=probes)
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
