#!/usr/bin/env python3
"""Verify secrets detection and vulnerability response workflow (#552)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _file_contains(path: Path, needle: str) -> bool:
    if not path.is_file():
        return False
    return needle in path.read_text(encoding="utf-8")


def evaluate_workflow(
    *,
    vuln_register: dict[str, Any],
    gitleaks_present: bool,
    ci_has_bandit: bool,
    ci_has_pip_audit: bool,
    ci_has_gitleaks: bool,
    runbook_present: bool,
) -> dict[str, Any]:
    items = vuln_register.get("items") or []
    if not isinstance(items, list):
        items = []
    p0_p1_missing_sla = 0
    for row in items:
        if not isinstance(row, dict):
            continue
        sev = str(row.get("severity") or "").strip().upper()
        if sev not in ("P0", "P1"):
            continue
        owner_ok = bool(str(row.get("owner") or "").strip())
        eta_ok = bool(str(row.get("eta") or "").strip())
        status = str(row.get("status") or "").strip().lower()
        if status in ("resolved", "mitigated"):
            continue
        if not (owner_ok and eta_ok):
            p0_p1_missing_sla += 1

    gates = {
        "gitleaks_config_present": bool(gitleaks_present),
        "ci_bandit_enabled": bool(ci_has_bandit),
        "ci_pip_audit_enabled": bool(ci_has_pip_audit),
        "ci_gitleaks_target_present": bool(ci_has_gitleaks),
        "vuln_response_runbook_present": bool(runbook_present),
        "p0_p1_vuln_sla_ok": bool(p0_p1_missing_sla == 0),
    }
    ok = all(gates.values())
    return {
        "schema": "secrets_vuln_response_gate@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gates": gates,
        "vulnerability_register": {
            "total_items": int(len(items)),
            "p0_p1_missing_sla": int(p0_p1_missing_sla),
        },
        "ok": bool(ok),
    }


def _to_md(report: dict[str, Any], register_file: Path) -> str:
    gates = report.get("gates") or {}
    vr = report.get("vulnerability_register") or {}
    return "\n".join(
        [
            "# Secrets & Vulnerability Response",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- register_file: `{register_file}`",
            f"- ok: `{report.get('ok')}`",
            "",
            "## Gates",
            "",
            (
                "- gitleaks_config_present: "
                f"`{gates.get('gitleaks_config_present')}`"
            ),
            f"- ci_bandit_enabled: `{gates.get('ci_bandit_enabled')}`",
            f"- ci_pip_audit_enabled: `{gates.get('ci_pip_audit_enabled')}`",
            (
                "- ci_gitleaks_target_present: "
                f"`{gates.get('ci_gitleaks_target_present')}`"
            ),
            (
                "- vuln_response_runbook_present: "
                f"`{gates.get('vuln_response_runbook_present')}`"
            ),
            f"- p0_p1_vuln_sla_ok: `{gates.get('p0_p1_vuln_sla_ok')}`",
            "",
            "## Register Stats",
            "",
            f"- total_items: `{vr.get('total_items')}`",
            f"- p0_p1_missing_sla: `{vr.get('p0_p1_missing_sla')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vuln-register",
        default="docs/reports/security/vulnerability_register.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/security/sec_vuln_response_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/security/sec_vuln_response_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    register_file = Path(args.vuln_register)
    if not register_file.is_absolute():
        register_file = REPO / register_file
    ci_file = REPO / ".github" / "workflows" / "ci-pr.yml"
    runbook = REPO / "docs" / "runbooks" / "sec-vuln-response.md"
    report = evaluate_workflow(
        vuln_register=_load_json(register_file),
        gitleaks_present=(REPO / ".gitleaks.toml").is_file(),
        ci_has_bandit=_file_contains(ci_file, "Bandit"),
        ci_has_pip_audit=_file_contains(ci_file, "pip-audit"),
        ci_has_gitleaks=_file_contains(REPO / "Makefile", "security-gitleaks"),
        runbook_present=runbook.is_file(),
    )
    out_json = Path(args.out_json)
    if not out_json.is_absolute():
        out_json = REPO / out_json
    out_md = Path(args.out_md)
    if not out_md.is_absolute():
        out_md = REPO / out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_to_md(report, register_file), encoding="utf-8")
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
