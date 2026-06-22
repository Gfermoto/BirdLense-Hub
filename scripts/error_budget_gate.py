#!/usr/bin/env python3
"""Error budget policy gate based on domain-health SLO signals (#529)."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _headers(api_key: str, mcp_token: str) -> dict[str, str]:
    if api_key:
        return {"X-Birdlense-Api-Key": api_key}
    if mcp_token:
        return {"Authorization": f"Bearer {mcp_token}"}
    return {}


def _fetch_domain_health(
    *,
    base_url: str,
    timeout_sec: int,
    headers: dict[str, str],
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/ui/system/domain-health"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=max(1, int(timeout_sec))) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"http_{exc.code}: {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"url_error:{exc.reason}: {url}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_json: {url}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("domain-health payload is not a JSON object")
    return payload


def build_unreachable_hub_payload(*, error: str, base_url: str) -> dict[str, Any]:
    """Hub down before deploy — do not block restore deploy."""
    return {
        "schema": "error_budget_gate@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": base_url,
        "inputs": {
            "hub_unreachable": True,
            "hub_error": error,
            "critical_breaches": 0,
            "warning_breaches": 0,
            "slo_dashboard_not_ok": False,
            "per_camera_warn_count_24h": 0,
            "recording_artifact_failures": False,
        },
        "costs": {
            "critical_breaches": 0,
            "warning_breaches": 0,
            "dashboard_not_ok": 0,
            "per_camera_warn_count": 0,
            "recording_artifact_failures": 0,
        },
        "budget": {
            "consumed_pct": 0,
            "remaining_pct": 100,
            "state": "hub_unreachable",
            "exhausted": False,
        },
        "gate": {
            "override_used": False,
            "override_reason": "",
            "override_has_ticket": False,
            "warning_requires_override": True,
            "requires_override": False,
            "warning_override_active": False,
            "block_release": False,
            "hub_unreachable": True,
            "ok": True,
        },
    }


def evaluate_gate(
    report: dict[str, Any],
    *,
    override_reason: str,
    warning_requires_override: bool = True,
) -> dict[str, Any]:
    alerting_rules = report.get("alerting_rules")
    if not isinstance(alerting_rules, list):
        alerting_rules = []
    slo_dashboard = report.get("slo_dashboard")
    if not isinstance(slo_dashboard, dict):
        slo_dashboard = {}
    snapshot = slo_dashboard.get("snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    status = slo_dashboard.get("status")
    if not isinstance(status, dict):
        status = {}
    reliability = report.get("reliability_alerts")
    if not isinstance(reliability, dict):
        reliability = {}
    reliability_alerts = reliability.get("alerts")
    if not isinstance(reliability_alerts, dict):
        reliability_alerts = {}

    critical_breaches = 0
    warning_breaches = 0
    for item in alerting_rules:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("breach")):
            continue
        severity = str(item.get("severity") or "warning").strip().lower()
        if severity == "critical":
            critical_breaches += 1
        else:
            warning_breaches += 1

    slo_not_ok = bool(status.get("ok") is False)
    per_camera_warn = int(snapshot.get("per_camera_warn_count_24h") or 0)
    recording_artifact_failures = bool(
        reliability_alerts.get("recording_artifact_failures")
    )

    costs = {
        "critical_breaches": int(critical_breaches * 45),
        "warning_breaches": int(warning_breaches * 15),
        "dashboard_not_ok": int(20 if slo_not_ok else 0),
        "per_camera_warn_count": int(max(0, min(per_camera_warn, 4)) * 5),
        "recording_artifact_failures": int(
            10 if recording_artifact_failures else 0
        ),
    }
    consumed_pct = int(min(100, sum(costs.values())))
    remaining_pct = int(max(0, 100 - consumed_pct))
    exhausted = bool(consumed_pct >= 100)
    warning_state = bool(not exhausted and consumed_pct >= 80)
    override_reason_clean = override_reason.strip()
    override_used = bool(override_reason_clean)
    override_has_ticket = bool(
        re.search(r"#\d+", override_reason_clean)
    )
    warning_override_active = bool(warning_state and warning_requires_override)
    requires_override = bool(exhausted or warning_override_active)
    override_valid = bool(override_used and override_has_ticket)
    block_release = bool(requires_override and not override_valid)
    policy_state = (
        "exhausted"
        if exhausted
        else ("warning" if warning_state else "ok")
    )

    return {
        "schema": "error_budget_gate@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": {
            "window": "rolling_28d",
            "budget_pct_total": 100,
            "warn_at_pct": 80,
            "exhausted_at_pct": 100,
            "critical_breach_cost_pct": 45,
            "warning_breach_cost_pct": 15,
            "dashboard_not_ok_cost_pct": 20,
            "per_camera_warn_cost_pct": 5,
            "recording_artifact_fail_cost_pct": 10,
        },
        "inputs": {
            "critical_breaches": int(critical_breaches),
            "warning_breaches": int(warning_breaches),
            "slo_dashboard_not_ok": bool(slo_not_ok),
            "per_camera_warn_count_24h": int(per_camera_warn),
            "recording_artifact_failures": bool(recording_artifact_failures),
        },
        "costs": costs,
        "budget": {
            "consumed_pct": int(consumed_pct),
            "remaining_pct": int(remaining_pct),
            "state": policy_state,
            "exhausted": bool(exhausted),
        },
        "gate": {
            "override_used": bool(override_used),
            "override_reason": override_reason_clean,
            "override_has_ticket": bool(override_has_ticket),
            "warning_requires_override": bool(warning_requires_override),
            "requires_override": bool(requires_override),
            "warning_override_active": bool(warning_override_active),
            "block_release": bool(block_release),
            "ok": bool(not block_release),
        },
    }


def _to_md(payload: dict[str, Any]) -> str:
    budget = payload.get("budget") or {}
    gate = payload.get("gate") or {}
    inputs = payload.get("inputs") or {}
    costs = payload.get("costs") or {}
    return "\n".join(
        [
            "# Error Budget Gate",
            "",
            f"- generated_at: `{payload.get('generated_at')}`",
            f"- state: `{budget.get('state')}`",
            f"- consumed_pct: `{budget.get('consumed_pct')}`",
            f"- remaining_pct: `{budget.get('remaining_pct')}`",
            f"- gate_ok: `{gate.get('ok')}`",
            "",
            "## Inputs",
            "",
            (
                "- critical_breaches: "
                f"`{inputs.get('critical_breaches')}`"
            ),
            (
                "- warning_breaches: "
                f"`{inputs.get('warning_breaches')}`"
            ),
            (
                "- slo_dashboard_not_ok: "
                f"`{inputs.get('slo_dashboard_not_ok')}`"
            ),
            (
                "- per_camera_warn_count_24h: "
                f"`{inputs.get('per_camera_warn_count_24h')}`"
            ),
            (
                "- recording_artifact_failures: "
                f"`{inputs.get('recording_artifact_failures')}`"
            ),
            "",
            "## Costs",
            "",
            f"- critical_breaches: `{costs.get('critical_breaches')}`",
            f"- warning_breaches: `{costs.get('warning_breaches')}`",
            f"- dashboard_not_ok: `{costs.get('dashboard_not_ok')}`",
            f"- per_camera_warn_count: `{costs.get('per_camera_warn_count')}`",
            (
                "- recording_artifact_failures: "
                f"`{costs.get('recording_artifact_failures')}`"
            ),
            "",
            "## Gate",
            "",
            f"- override_used: `{gate.get('override_used')}`",
            f"- override_reason: `{gate.get('override_reason')}`",
            f"- block_release: `{gate.get('block_release')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DEPLOY_URL", "http://127.0.0.1:8085"),
    )
    parser.add_argument("--timeout-sec", type=int, default=20)
    parser.add_argument(
        "--api-key",
        default=os.environ.get("BIRDLENSE_UI_API_KEY", ""),
    )
    parser.add_argument("--mcp-token", default=os.environ.get("MCP_TOKEN", ""))
    parser.add_argument("--report", default="")
    parser.add_argument(
        "--override-reason",
        default=os.environ.get("BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON", ""),
    )
    parser.add_argument(
        "--warning-requires-override",
        action="store_true",
        default=_truthy(
            os.environ.get(
                "BIRDLENSE_ERROR_BUDGET_WARNING_REQUIRES_OVERRIDE",
                "1",
            )
        ),
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/error_budget_gate/error_budget_gate_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/error_budget_gate/error_budget_gate_latest.md",
    )
    parser.add_argument(
        "--require-hub",
        action="store_true",
        help="Fail when hub is unreachable (post-deploy re-run).",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    if args.report:
        report_path = Path(args.report).expanduser()
        if not report_path.is_absolute():
            report_path = REPO / report_path
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise SystemExit("report must be JSON object")
    else:
        try:
            report = _fetch_domain_health(
                base_url=args.base_url,
                timeout_sec=args.timeout_sec,
                headers=_headers(args.api_key, args.mcp_token),
            )
        except RuntimeError as exc:
            err = str(exc)
            if "url_error" in err or err.startswith("http_"):
                payload = build_unreachable_hub_payload(
                    error=err,
                    base_url=args.base_url,
                )
                if args.require_hub:
                    payload["gate"]["ok"] = False
                    payload["gate"]["block_release"] = True
                    payload["gate"]["require_hub_failed"] = True
                out_json = Path(args.out_json).expanduser()
                if not out_json.is_absolute():
                    out_json = REPO / out_json
                out_md = Path(args.out_md).expanduser()
                if not out_md.is_absolute():
                    out_md = REPO / out_md
                out_json.parent.mkdir(parents=True, exist_ok=True)
                out_md.parent.mkdir(parents=True, exist_ok=True)
                out_json.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                out_md.write_text(_to_md(payload), encoding="utf-8")
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "state": "hub_unreachable",
                            "consumed_pct": 0,
                            "json": str(out_json),
                            "md": str(out_md),
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            raise SystemExit(err) from exc

    payload = evaluate_gate(
        report,
        override_reason=str(args.override_reason or ""),
        warning_requires_override=bool(args.warning_requires_override),
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
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_to_md(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool((payload.get("gate") or {}).get("ok")),
                "state": (payload.get("budget") or {}).get("state"),
                "consumed_pct": (
                    (payload.get("budget") or {}).get("consumed_pct")
                ),
                "json": str(out_json),
                "md": str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool((payload.get("gate") or {}).get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
