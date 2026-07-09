#!/usr/bin/env python3
"""Verify scripts ownership and lifecycle registry (#549)."""

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


def evaluate_registry(registry: dict[str, Any]) -> dict[str, Any]:
    rows = registry.get("scripts") or []
    if not isinstance(rows, list):
        rows = []
    required_ids = {
        str(item).strip()
        for item in (registry.get("required_ids") or [])
        if str(item).strip()
    }
    allowed_lifecycle = {
        str(item).strip().lower()
        for item in (registry.get("allowed_lifecycle") or [])
        if str(item).strip()
    }
    min_coverage_ratio = float(registry.get("min_coverage_ratio") or 1.0)

    seen: set[str] = set()
    duplicates: list[str] = []
    missing_ids: list[str] = []
    missing_owner: list[str] = []
    missing_runbook: list[str] = []
    missing_script_path: list[str] = []
    invalid_lifecycle: list[str] = []
    rows_out: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or "").strip()
        path = str(row.get("path") or "").strip()
        owner = str(row.get("owner") or "").strip()
        runbook = str(row.get("runbook") or "").strip()
        lifecycle = str(row.get("lifecycle") or "").strip().lower()
        if sid in seen:
            duplicates.append(sid)
        seen.add(sid)
        if not sid:
            missing_ids.append(path or "unknown")
        if not owner:
            missing_owner.append(sid or path or "unknown")
        script_exists = bool(path and (REPO / path).is_file())
        runbook_exists = bool(runbook and (REPO / runbook).is_file())
        lifecycle_ok = lifecycle in allowed_lifecycle
        if not script_exists:
            missing_script_path.append(sid or path or "unknown")
        if not runbook_exists:
            missing_runbook.append(sid or runbook or "unknown")
        if not lifecycle_ok:
            invalid_lifecycle.append(sid or lifecycle or "unknown")
        if lifecycle == "deprecated":
            replacement = str(row.get("replacement_script") or "").strip()
            sunset = str(row.get("sunset_date") or "").strip()
            if not replacement or not sunset:
                invalid_lifecycle.append(sid or "deprecated_without_exit_plan")
        rows_out.append(
            {
                "id": sid,
                "path": path,
                "owner_present": bool(owner),
                "runbook_present": runbook_exists,
                "script_present": script_exists,
                "lifecycle": lifecycle,
                "lifecycle_ok": lifecycle_ok,
            }
        )

    missing_required = sorted(
        item for item in required_ids if item not in seen
    )
    covered = int(sum(1 for row in rows_out if row.get("owner_present")))
    coverage_ratio = (
        (float(covered) / float(len(rows_out)))
        if rows_out
        else 0.0
    )

    checks = {
        "scripts_present_ok": len(missing_script_path) == 0,
        "required_ids_ok": len(missing_required) == 0,
        "duplicates_ok": len(duplicates) == 0,
        "owner_coverage_ok": coverage_ratio >= min_coverage_ratio,
        "runbook_coverage_ok": len(missing_runbook) == 0,
        "lifecycle_ok": len(invalid_lifecycle) == 0,
    }

    return {
        "schema": "scripts_ownership_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "scripts_total": len(rows_out),
            "required_total": len(required_ids),
            "covered_owner_total": covered,
            "owner_coverage_ratio": round(coverage_ratio, 6),
            "owner_coverage_target": min_coverage_ratio,
        },
        "drift": {
            "missing_required_ids": missing_required,
            "missing_script_path": missing_script_path,
            "missing_runbook": missing_runbook,
            "missing_owner": missing_owner,
            "duplicate_ids": duplicates,
            "invalid_lifecycle": invalid_lifecycle,
            "missing_ids": missing_ids,
        },
        "scripts": rows_out,
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    summary = report.get("summary") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# Scripts Ownership & Lifecycle Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- scripts_total: `{summary.get('scripts_total')}`",
            (
                "- owner_coverage_ratio: "
                f"`{summary.get('owner_coverage_ratio')}`"
            ),
            (
                "- owner_coverage_target: "
                f"`{summary.get('owner_coverage_target')}`"
            ),
            (
                "- missing_required_ids: "
                f"`{len(drift.get('missing_required_ids') or [])}`"
            ),
            (
                "- missing_runbook: "
                f"`{len(drift.get('missing_runbook') or [])}`"
            ),
            (
                "- missing_script_path: "
                f"`{len(drift.get('missing_script_path') or [])}`"
            ),
            f"- owner_coverage_ok: `{checks.get('owner_coverage_ok')}`",
            f"- runbook_coverage_ok: `{checks.get('runbook_coverage_ok')}`",
            f"- lifecycle_ok: `{checks.get('lifecycle_ok')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default="docs/reports/tooling/scripts_ownership_registry.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/tooling/scripts_ownership_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/tooling/scripts_ownership_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    registry_file = Path(args.registry).expanduser()
    if not registry_file.is_absolute():
        registry_file = REPO / registry_file
    report = evaluate_registry(_read_json(registry_file))
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
