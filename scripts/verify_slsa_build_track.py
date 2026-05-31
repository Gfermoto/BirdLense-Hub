#!/usr/bin/env python3
"""Verify SLSA build-track progression contract (#546)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
CI_FILE = REPO / ".github" / "workflows" / "ci-pr.yml"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _control_results(ci_text: str) -> dict[str, bool]:
    return {
        "workflow_dispatch": "workflow_dispatch:" in ci_text,
        "concurrency": (
            "concurrency:" in ci_text and "cancel-in-progress: true" in ci_text
        ),
        "bandit_scan": "bandit -r web/ processor/src" in ci_text,
        "pip_audit_scan": "pip-audit -r web/requirements.txt" in ci_text,
        "no_self_hosted_runner": "runs-on: self-hosted" not in ci_text,
    }


def evaluate_slsa_track(
    *,
    plan: dict[str, Any],
    ci_text: str,
    workflow_exists: bool,
) -> dict[str, Any]:
    controls = _control_results(ci_text)
    required = [
        str(item).strip()
        for item in (plan.get("required_controls") or [])
        if str(item).strip()
    ]
    adopted = 0
    rows: list[dict[str, Any]] = []
    for item in required:
        ok = bool(controls.get(item))
        if ok:
            adopted += 1
        rows.append({"id": item, "ok": ok})
    adoption_pct = (
        round((adopted / len(required)) * 100.0, 2)
        if required
        else 0.0
    )
    min_adoption_pct = float(plan.get("min_control_adoption_pct") or 100.0)
    checks = {
        "workflow_exists": bool(workflow_exists),
        "required_controls_present": bool(adoption_pct >= min_adoption_pct),
    }
    ok = bool(all(checks.values()))
    return {
        "schema": "slsa_build_track_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "track": {
            "current_level": str(plan.get("current_level") or ""),
            "target_level": str(plan.get("target_level") or ""),
        },
        "checks": checks,
        "controls": {
            "required_total": int(len(required)),
            "adopted_total": int(adopted),
            "adoption_pct": adoption_pct,
            "min_adoption_pct": min_adoption_pct,
            "items": rows,
        },
        "ok": ok,
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    controls = report.get("controls") or {}
    return "\n".join(
        [
            "# SLSA Build Track Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- workflow_exists: `{checks.get('workflow_exists')}`",
            (
                "- required_controls_present: "
                f"`{checks.get('required_controls_present')}`"
            ),
            (
                "- control_adoption: "
                f"`{controls.get('adopted_total')}/"
                f"{controls.get('required_total')}`"
            ),
            f"- adoption_pct: `{controls.get('adoption_pct')}`",
            f"- target_min_adoption_pct: `{controls.get('min_adoption_pct')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        default="docs/reports/slsa/slsa_build_track.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/slsa/slsa_build_track_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/slsa/slsa_build_track_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    plan_file = Path(args.plan).expanduser()
    if not plan_file.is_absolute():
        plan_file = REPO / plan_file
    workflow_exists = CI_FILE.is_file()
    ci_text = CI_FILE.read_text(encoding="utf-8") if workflow_exists else ""
    report = evaluate_slsa_track(
        plan=_read_json(plan_file),
        ci_text=ci_text,
        workflow_exists=workflow_exists,
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
