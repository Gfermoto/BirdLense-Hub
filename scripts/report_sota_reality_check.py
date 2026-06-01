#!/usr/bin/env python3
"""Generate weekly SOTA reality-check report."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
CRITICAL_ISSUES = [517, 555, 556, 557]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _gh_issue_state(issue: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(issue),
                "--json",
                "number,title,state,url,labels",
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return {"number": issue, "state": "unknown", "error": str(exc)}
    if proc.returncode != 0:
        return {
            "number": issue,
            "state": "unknown",
            "error": proc.stderr.strip() or f"gh_exit_{proc.returncode}",
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "number": issue,
            "state": "unknown",
            "error": "invalid_gh_json",
        }
    if not isinstance(payload, dict):
        return {
            "number": issue,
            "state": "unknown",
            "error": "invalid_gh_payload",
        }
    return payload


def evaluate(
    *,
    error_budget: dict[str, Any],
    golden_set: dict[str, Any],
    outcome: dict[str, Any],
    issue_states: list[dict[str, Any]],
) -> dict[str, Any]:
    gate = {
        "error_budget_ok": bool((error_budget.get("gate") or {}).get("ok")),
        "golden_set_ok": bool(golden_set.get("ok")),
        "outcome_ok": bool((outcome.get("gate") or {}).get("ok")),
    }
    issues_open = [
        i
        for i in issue_states
        if str(i.get("state") or "").strip().upper() != "CLOSED"
    ]
    acceptance_blocked = bool(issues_open) or not all(gate.values())
    decision = "hold" if acceptance_blocked else "go"
    return {
        "schema": "sota_reality_check@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "critical_path": {
            "issues": issue_states,
            "issues_open": issues_open,
        },
        "gates": gate,
        "outcome_metrics": outcome.get("metrics") or {},
        "acceptance_blocked": acceptance_blocked,
        "decision": decision,
    }


def _to_md(report: dict[str, Any]) -> str:
    gates = report.get("gates") or {}
    metrics = report.get("outcome_metrics") or {}
    critical = report.get("critical_path") or {}
    issues = list(critical.get("issues") or [])
    lines = [
        "# SOTA Reality Check (weekly)",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- decision: `{report.get('decision')}`",
        f"- acceptance_blocked: `{report.get('acceptance_blocked')}`",
        "",
        "## Gates",
        "",
        f"- error_budget_ok: `{gates.get('error_budget_ok')}`",
        f"- golden_set_ok: `{gates.get('golden_set_ok')}`",
        f"- outcome_ok: `{gates.get('outcome_ok')}`",
        "",
        "## Outcome metrics",
        "",
        f"- blind_rate: `{metrics.get('blind_rate')}`",
        "- yolo_frames_with_tracks: "
        f"`{metrics.get('yolo_frames_with_tracks')}`",
        f"- empty_bbox_rate: `{metrics.get('empty_bbox_rate')}`",
        f"- tracks_coverage: `{metrics.get('tracks_coverage')}`",
        "- trigger_to_first_bbox_latency_p95_s: "
        f"`{metrics.get('trigger_to_first_bbox_latency_p95_s')}`",
        "- finalize_duration_p95_ms: "
        f"`{metrics.get('finalize_duration_p95_ms')}`",
        "- ingest_bbox_contract_pruned_events: "
        f"`{metrics.get('ingest_bbox_contract_pruned_events')}`",
        "- ingest_bbox_contract_empty_events: "
        f"`{metrics.get('ingest_bbox_contract_empty_events')}`",
        "- ingest_bbox_contract_pruned_rows_per_session: "
        f"`{metrics.get('ingest_bbox_contract_pruned_rows_per_session')}`",
        "",
        "## Critical issues",
        "",
    ]
    for issue in issues:
        number = issue.get("number")
        title = issue.get("title") or issue.get("error") or "n/a"
        state = issue.get("state") or "unknown"
        url = issue.get("url")
        if url:
            lines.append(f"- #{number} [{title}]({url}) — `{state}`")
        else:
            lines.append(f"- #{number} {title} — `{state}`")
    return "\n".join(lines) + "\n"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--error-budget-json",
        default="docs/reports/error_budget_gate/error_budget_gate_latest.json",
    )
    parser.add_argument(
        "--golden-set-json",
        default="docs/reports/golden_set_gate/golden_set_gate_latest.json",
    )
    parser.add_argument(
        "--outcome-json",
        default=(
            "docs/reports/quality_outcome/"
            "quality_outcome_metrics_latest.json"
        ),
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/sota_reality/sota_reality_check_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/sota_reality/sota_reality_check_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    error_budget = _read_json((REPO / args.error_budget_json).resolve())
    golden_set = _read_json((REPO / args.golden_set_json).resolve())
    outcome = _read_json((REPO / args.outcome_json).resolve())
    issue_states = [_gh_issue_state(i) for i in CRITICAL_ISSUES]
    report = evaluate(
        error_budget=error_budget,
        golden_set=golden_set,
        outcome=outcome,
        issue_states=issue_states,
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
                "decision": report.get("decision"),
                "acceptance_blocked": report.get("acceptance_blocked"),
                "json": str(out_json),
                "md": str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
