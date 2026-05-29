#!/usr/bin/env python3
"""Build weekly_quality_cycle_playbook@v1 from backlog + status."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _i(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_playbook(
    *,
    backlog_report: dict[str, Any],
    feedback_loop_status: dict[str, Any],
) -> dict[str, Any]:
    items = (
        backlog_report.get("items")
        if isinstance(backlog_report.get("items"), list)
        else []
    )
    rows = [r for r in items if isinstance(r, dict)]
    pending = _i(feedback_loop_status.get("events_total"))
    top_actions = [
        str(r.get("action") or "")
        for r in rows[:5]
        if str(r.get("action") or "")
    ]
    checklist = [
        "mine_weekly_errors_fp_fn_idsw_species_unknown",
        "curate_hard_negatives_and_uncertain_subset",
        "export_feedback_learning_dataset",
        "run_retrain_or_recalibration_job",
        "run_shadow_ab_and_compare_core_kpis",
        "rollout_if_no_regression",
    ]
    return {
        "schema": "weekly_quality_cycle_playbook@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "backlog_schema": backlog_report.get("schema"),
            "feedback_status_schema": feedback_loop_status.get("schema"),
        },
        "backlog_items_total": len(rows),
        "feedback_events_total": pending,
        "priority_actions": top_actions,
        "weekly_checklist": checklist,
        "ok": len(rows) > 0,
    }


def build_markdown(report: dict[str, Any]) -> str:
    actions = (
        report.get("priority_actions")
        if isinstance(report.get("priority_actions"), list)
        else []
    )
    checklist = (
        report.get("weekly_checklist")
        if isinstance(report.get("weekly_checklist"), list)
        else []
    )
    lines = [
        "## Weekly Quality Cycle Playbook",
        "",
        f"- `ok`: **{bool(report.get('ok'))}**",
        f"- `backlog_items_total`: **{report.get('backlog_items_total')}**",
        (
            "- `feedback_events_total`: "
            f"**{report.get('feedback_events_total')}**"
        ),
        "",
        "### Priority Actions",
    ]
    lines.extend(f"- {a}" for a in actions)
    lines.extend(["", "### Weekly Checklist"])
    lines.extend(f"- [ ] {c}" for c in checklist)
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backlog-report", required=True)
    parser.add_argument("--feedback-loop-status", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_playbook(
        backlog_report=_load_json(args.backlog_report),
        feedback_loop_status=_load_json(args.feedback_loop_status),
    )
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.summary_out:
        summary = Path(args.summary_out).expanduser().resolve()
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(build_markdown(report), encoding="utf-8")
    return 0 if bool(report.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
