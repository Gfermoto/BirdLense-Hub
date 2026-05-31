#!/usr/bin/env python3
"""Verify policy-as-code release governance contract (#554)."""

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


def evaluate_release_policy(
    *,
    contract: dict[str, Any],
    audit_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    required_policies = {
        str(item).strip()
        for item in (contract.get("required_policies") or [])
        if str(item).strip()
    }
    min_release_events = int(contract.get("min_release_events") or 0)
    min_policy_coverage_ratio = float(
        contract.get("min_policy_coverage_ratio") or 1.0
    )
    max_manual_override_ratio = float(
        contract.get("max_manual_override_ratio") or 0.0
    )
    require_override_audit_trail = bool(
        contract.get("require_override_audit_trail", True)
    )

    policies_seen: set[str] = set()
    release_ids_seen: set[str] = set()
    overrides_total = 0
    overrides_missing_audit: list[str] = []
    gate_not_enforced: list[str] = []
    rows: list[dict[str, Any]] = []

    for row in audit_rows:
        release_id = str(row.get("release_id") or "").strip()
        policy_id = str(row.get("policy_id") or "").strip()
        gate_enforced = bool(row.get("gate_enforced"))
        manual_override = bool(row.get("manual_override"))
        if release_id:
            release_ids_seen.add(release_id)
        if policy_id:
            policies_seen.add(policy_id)
        if not gate_enforced:
            gate_not_enforced.append(f"{release_id}:{policy_id}")
        if manual_override:
            overrides_total += 1
            if require_override_audit_trail:
                reason = str(row.get("override_reason") or "").strip()
                approved_by = str(
                    row.get("override_approved_by") or ""
                ).strip()
                ticket = str(row.get("override_ticket") or "").strip()
                if not reason or not approved_by or not ticket:
                    overrides_missing_audit.append(
                        f"{release_id}:{policy_id}"
                    )
        rows.append(
            {
                "release_id": release_id,
                "policy_id": policy_id,
                "gate_enforced": gate_enforced,
                "manual_override": manual_override,
            }
        )

    missing_policies = sorted(
        item for item in required_policies if item not in policies_seen
    )
    policy_coverage_ratio = (
        float(len(required_policies - set(missing_policies)))
        / float(len(required_policies))
        if required_policies
        else 1.0
    )
    manual_override_ratio = (
        float(overrides_total) / float(len(rows))
        if rows
        else 0.0
    )

    checks = {
        "min_release_events_ok": len(rows) >= min_release_events,
        "required_policies_ok": len(missing_policies) == 0,
        "policy_coverage_ok": (
            policy_coverage_ratio >= min_policy_coverage_ratio
        ),
        "gate_enforced_ok": len(gate_not_enforced) == 0,
        "manual_override_ratio_ok": (
            manual_override_ratio <= max_manual_override_ratio
        ),
        "override_audit_ok": len(overrides_missing_audit) == 0,
    }
    return {
        "schema": "release_policy_as_code_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "audit_rows_total": len(rows),
            "release_ids_total": len(release_ids_seen),
            "required_policies_total": len(required_policies),
            "policy_coverage_ratio": round(policy_coverage_ratio, 6),
            "policy_coverage_target": min_policy_coverage_ratio,
            "manual_override_ratio": round(manual_override_ratio, 6),
            "manual_override_limit": max_manual_override_ratio,
        },
        "drift": {
            "missing_policies": missing_policies,
            "gate_not_enforced": gate_not_enforced,
            "overrides_missing_audit": overrides_missing_audit,
        },
        "audit_rows": rows,
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    summary = report.get("summary") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# Release Policy-as-Code Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- audit_rows_total: `{summary.get('audit_rows_total')}`",
            (
                "- policy_coverage_ratio: "
                f"`{summary.get('policy_coverage_ratio')}` "
                f"(target `{summary.get('policy_coverage_target')}`)"
            ),
            (
                "- manual_override_ratio: "
                f"`{summary.get('manual_override_ratio')}` "
                f"(limit `{summary.get('manual_override_limit')}`)"
            ),
            (
                "- missing_policies: "
                f"`{len(drift.get('missing_policies') or [])}`"
            ),
            (
                "- overrides_missing_audit: "
                f"`{len(drift.get('overrides_missing_audit') or [])}`"
            ),
            f"- policy_coverage_ok: `{checks.get('policy_coverage_ok')}`",
            (
                "- manual_override_ratio_ok: "
                f"`{checks.get('manual_override_ratio_ok')}`"
            ),
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/governance/release_policy_contract.json",
    )
    parser.add_argument(
        "--audit",
        default="docs/reports/governance/release_policy_audit.jsonl",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/governance/release_policy_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/governance/release_policy_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract_file = Path(args.contract).expanduser()
    if not contract_file.is_absolute():
        contract_file = REPO / contract_file
    audit_file = Path(args.audit).expanduser()
    if not audit_file.is_absolute():
        audit_file = REPO / audit_file
    report = evaluate_release_policy(
        contract=_read_json(contract_file),
        audit_rows=_read_jsonl(audit_file),
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
