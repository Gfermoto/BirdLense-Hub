#!/usr/bin/env python3
"""Verify reliability/security/ML review board governance contract (#553)."""

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


def evaluate_review_board(
    *,
    contract: dict[str, Any],
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    required_domains = {
        str(item).strip().lower()
        for item in (contract.get("required_domains") or [])
        if str(item).strip()
    }
    min_sessions_total = int(contract.get("min_sessions_total") or 0)
    max_untriaged_p0_p1 = int(contract.get("max_untriaged_p0_p1") or 0)
    min_cadence_adherence_ratio = float(
        contract.get("min_cadence_adherence_ratio") or 1.0
    )

    domain_seen: set[str] = set()
    conducted_total = 0
    session_rows: list[dict[str, Any]] = []
    untriaged_critical: list[str] = []

    for row in sessions:
        domain = str(row.get("domain") or "").strip().lower()
        conducted = bool(row.get("conducted"))
        findings = row.get("findings") or []
        if not isinstance(findings, list):
            findings = []
        if domain:
            domain_seen.add(domain)
        if conducted:
            conducted_total += 1

        for finding in findings:
            if not isinstance(finding, dict):
                continue
            sev = str(finding.get("severity") or "").strip().lower()
            owner = str(finding.get("owner") or "").strip()
            decision = str(finding.get("decision") or "").strip()
            if sev in {"p0", "p1"} and (not owner or not decision):
                untriaged_critical.append(
                    str(finding.get("id") or "unknown-critical-finding")
                )

        session_rows.append(
            {
                "session_id": str(row.get("session_id") or ""),
                "domain": domain,
                "conducted": conducted,
                "findings_total": len(findings),
            }
        )

    missing_domains = sorted(
        item for item in required_domains if item not in domain_seen
    )
    cadence_adherence_ratio = (
        float(conducted_total) / float(len(session_rows))
        if session_rows
        else 0.0
    )

    checks = {
        "min_sessions_total_ok": len(session_rows) >= min_sessions_total,
        "required_domains_ok": len(missing_domains) == 0,
        "cadence_adherence_ok": (
            cadence_adherence_ratio >= min_cadence_adherence_ratio
        ),
        "untriaged_critical_ok": (
            len(untriaged_critical) <= max_untriaged_p0_p1
        ),
    }
    return {
        "schema": "review_board_governance_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "sessions_total": len(session_rows),
            "conducted_total": conducted_total,
            "cadence_adherence_ratio": round(cadence_adherence_ratio, 6),
            "cadence_adherence_target": min_cadence_adherence_ratio,
            "untriaged_critical_total": len(untriaged_critical),
            "untriaged_critical_limit": max_untriaged_p0_p1,
        },
        "drift": {
            "missing_domains": missing_domains,
            "untriaged_critical_findings": untriaged_critical,
        },
        "sessions": session_rows,
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    checks = report.get("checks") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# Review Board Governance Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- sessions_total: `{summary.get('sessions_total')}`",
            (
                "- cadence_adherence_ratio: "
                f"`{summary.get('cadence_adherence_ratio')}` "
                f"(target `{summary.get('cadence_adherence_target')}`)"
            ),
            (
                "- untriaged_critical_total: "
                f"`{summary.get('untriaged_critical_total')}` "
                f"(limit `{summary.get('untriaged_critical_limit')}`)"
            ),
            f"- missing_domains: `{len(drift.get('missing_domains') or [])}`",
            (
                "- untriaged_critical_findings: "
                f"`{len(drift.get('untriaged_critical_findings') or [])}`"
            ),
            f"- cadence_adherence_ok: `{checks.get('cadence_adherence_ok')}`",
            (
                "- untriaged_critical_ok: "
                f"`{checks.get('untriaged_critical_ok')}`"
            ),
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/governance/review_board_contract.json",
    )
    parser.add_argument(
        "--sessions",
        default="docs/reports/governance/review_board_sessions.jsonl",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/governance/review_board_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/governance/review_board_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract_file = Path(args.contract).expanduser()
    if not contract_file.is_absolute():
        contract_file = REPO / contract_file
    sessions_file = Path(args.sessions).expanduser()
    if not sessions_file.is_absolute():
        sessions_file = REPO / sessions_file
    report = evaluate_review_board(
        contract=_read_json(contract_file),
        sessions=_read_jsonl(sessions_file),
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
