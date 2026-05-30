#!/usr/bin/env python3
"""Build DORA metrics snapshot and optional deploy event record (#544)."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from datetime import UTC, datetime, timedelta
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


def _parse_ts(text: str) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _git_commits_since(days: int) -> list[dict[str, Any]]:
    since = f"{max(1, int(days))} days ago"
    out = _git(
        [
            "git",
            "log",
            "--since",
            since,
            "--pretty=format:%H|%ct|%at",
            "HEAD",
        ]
    )
    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        sha, committed_s, authored_s = parts
        try:
            committed = datetime.fromtimestamp(int(committed_s), tz=UTC)
            authored = datetime.fromtimestamp(int(authored_s), tz=UTC)
        except (TypeError, ValueError, OSError):
            continue
        rows.append(
            {
                "sha": sha.strip(),
                "committed_at": committed,
                "authored_at": authored,
            }
        )
    return rows


def compute_dora(
    *,
    window_days: int,
    deploy_events: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
) -> dict[str, Any]:
    now = datetime.now(UTC)
    window_start = now - timedelta(days=max(1, int(window_days)))

    deployments_in_window = []
    for row in deploy_events:
        ts = _parse_ts(str(row.get("deployed_at") or ""))
        if ts is None or ts < window_start:
            continue
        deployments_in_window.append({**row, "_deployed_at": ts})

    if not deployments_in_window:
        commits = _git_commits_since(window_days)
        deployments_total = len(commits)
        lead_samples = [
            max(
                0.0,
                (item["committed_at"] - item["authored_at"]).total_seconds()
                / 3600.0,
            )
            for item in commits
        ]
        failed_total = 0
        deployment_source = "git_commit_fallback"
    else:
        deployments_total = len(deployments_in_window)
        lead_samples = []
        for row in deployments_in_window:
            created = _parse_ts(str(row.get("change_created_at") or ""))
            deployed = row.get("_deployed_at")
            if created is None or deployed is None:
                continue
            lead_samples.append(
                max(0.0, (deployed - created).total_seconds() / 3600.0)
            )
        failed_total = sum(
            1
            for row in deployments_in_window
            if str(row.get("status") or "").strip().lower() == "failed"
        )
        deployment_source = "deploy_events_log"

    deployment_frequency = round(
        deployments_total / float(max(1, int(window_days))),
        4,
    )
    lead_time_p50 = round(
        statistics.median(lead_samples) if lead_samples else 0.0,
        4,
    )
    change_failure_rate = round(
        (
            (failed_total / float(deployments_total))
            if deployments_total
            else 0.0
        ),
        4,
    )

    mttr_samples = []
    for row in incidents:
        started = _parse_ts(str(row.get("started_at") or ""))
        resolved = _parse_ts(str(row.get("resolved_at") or ""))
        if started is None or resolved is None:
            continue
        if resolved < window_start:
            continue
        mttr_samples.append(
            max(0.0, (resolved - started).total_seconds() / 3600.0)
        )
    mttr_hours = round(
        statistics.mean(mttr_samples) if mttr_samples else 0.0,
        4,
    )

    return {
        "schema": "dora_metrics@v1",
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_days": int(window_days),
        "deployment_source": deployment_source,
        "metrics": {
            "deployment_frequency_per_day": deployment_frequency,
            "lead_time_for_changes_hours_p50": lead_time_p50,
            "change_failure_rate": change_failure_rate,
            "time_to_restore_service_hours_mean": mttr_hours,
        },
        "samples": {
            "deployments_total": int(deployments_total),
            "failed_deployments_total": int(failed_total),
            "lead_time_samples": int(len(lead_samples)),
            "incidents_resolved_samples": int(len(mttr_samples)),
        },
        "ok": True,
    }


def _to_md(report: dict[str, Any]) -> str:
    metrics = report.get("metrics") or {}
    samples = report.get("samples") or {}
    return "\n".join(
        [
            "# DORA Metrics Snapshot",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- window_days: `{report.get('window_days')}`",
            f"- deployment_source: `{report.get('deployment_source')}`",
            "",
            "## Metrics",
            "",
            (
                "- deployment_frequency_per_day: "
                f"`{metrics.get('deployment_frequency_per_day')}`"
            ),
            (
                "- lead_time_for_changes_hours_p50: "
                f"`{metrics.get('lead_time_for_changes_hours_p50')}`"
            ),
            f"- change_failure_rate: `{metrics.get('change_failure_rate')}`",
            (
                "- time_to_restore_service_hours_mean: "
                f"`{metrics.get('time_to_restore_service_hours_mean')}`"
            ),
            "",
            "## Samples",
            "",
            f"- deployments_total: `{samples.get('deployments_total')}`",
            (
                "- failed_deployments_total: "
                f"`{samples.get('failed_deployments_total')}`"
            ),
            f"- lead_time_samples: `{samples.get('lead_time_samples')}`",
            (
                "- incidents_resolved_samples: "
                f"`{samples.get('incidents_resolved_samples')}`"
            ),
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-days", type=int, default=28)
    parser.add_argument(
        "--deploy-events",
        default="docs/reports/dora/deploy_events.jsonl",
    )
    parser.add_argument(
        "--incidents",
        default="docs/reports/dora/incidents.jsonl",
    )
    parser.add_argument("--record-deploy", action="store_true")
    parser.add_argument(
        "--deploy-status",
        choices=("success", "failed"),
        default="success",
    )
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument(
        "--out-json",
        default="docs/reports/dora/dora_metrics_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/dora/dora_metrics_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    deploy_events = Path(args.deploy_events)
    if not deploy_events.is_absolute():
        deploy_events = REPO / deploy_events
    incidents = Path(args.incidents)
    if not incidents.is_absolute():
        incidents = REPO / incidents
    if args.record_deploy:
        _append_jsonl(
            deploy_events,
            {
                "deployed_at": datetime.now(UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "status": str(args.deploy_status),
                "git_commit": _git(["git", "rev-parse", "HEAD"]),
                "change_created_at": "",
            },
        )
    if args.skip_report:
        print(json.dumps({"ok": True, "recorded": bool(args.record_deploy)}))
        return 0

    report = compute_dora(
        window_days=max(1, int(args.window_days)),
        deploy_events=_read_jsonl(deploy_events),
        incidents=_read_jsonl(incidents),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
