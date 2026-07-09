#!/usr/bin/env python3
"""Build track_quality_regression_report@v1 from domain-health API payload."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


def _auth_headers(
    api_key: str | None,
    mcp_token: str | None,
) -> dict[str, str]:
    if api_key:
        return {"X-Birdlense-Api-Key": api_key}
    if mcp_token:
        return {"Authorization": f"Bearer {mcp_token}"}
    return {}


def fetch_domain_health_payload(
    *,
    base_url: str,
    timeout_sec: int = 20,
    api_key: str | None = None,
    mcp_token: str | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/ui/system/domain-health"
    headers = _auth_headers(api_key, mcp_token)
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=max(1, int(timeout_sec))) as resp:
            body = resp.read().decode("utf-8")
    except error.URLError as exc:
        raise RuntimeError(f"domain-health fetch failed: {exc}") from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("domain-health returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("domain-health payload must be a JSON object")
    return payload


def build_track_quality_regression_report(
    *,
    domain_health_payload: dict[str, Any],
    base_url: str,
    fail_on_regression: bool = False,
) -> dict[str, Any]:
    metrics = (
        domain_health_payload.get("metrics")
        if isinstance(domain_health_payload.get("metrics"), dict)
        else {}
    )
    samples = (
        domain_health_payload.get("samples")
        if isinstance(domain_health_payload.get("samples"), dict)
        else {}
    )
    strict_quality = (
        domain_health_payload.get("strict_quality")
        if isinstance(domain_health_payload.get("strict_quality"), dict)
        else {}
    )
    regression_block = (
        samples.get("track_quality_regression_24h")
        if isinstance(samples.get("track_quality_regression_24h"), dict)
        else {}
    )
    unstable_examples = (
        samples.get("track_unstable_examples_24h")
        if isinstance(samples.get("track_unstable_examples_24h"), list)
        else []
    )
    regression_detected = bool(metrics.get("track_quality_regression_24h"))
    stability_delta = metrics.get("track_stability_score_delta_prev_24h")
    fragmented_delta = metrics.get("track_fragmented_ratio_delta_prev_24h")
    gaps_delta = metrics.get("track_gaps_ratio_delta_prev_24h")

    gates = {
        "track_quality_regression_absent": not regression_detected,
        "strict_quality_ready": bool(strict_quality.get("strict_quality_ready")),
    }
    ok = all(bool(v) for v in gates.values())
    if not fail_on_regression:
        ok = True

    return {
        "schema": "track_quality_regression_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "base_url": base_url,
            "domain_contract_version": domain_health_payload.get(
                "domain_contract_version"
            ),
        },
        "thresholds": {
            "fail_on_regression": bool(fail_on_regression),
            "regression_min_sample_per_window": 30,
            "regression_stability_drop_threshold": -0.05,
            "regression_fragmentation_rise_threshold": 0.05,
            "regression_gaps_rise_threshold": 0.05,
        },
        "metrics": {
            "track_rows_with_id_24h": metrics.get("track_rows_with_id_24h"),
            "track_stability_score_avg_24h": metrics.get(
                "track_stability_score_avg_24h"
            ),
            "track_rows_fragmented_ratio_24h": metrics.get(
                "track_rows_fragmented_ratio_24h"
            ),
            "track_rows_with_gaps_ratio_24h": metrics.get(
                "track_rows_with_gaps_ratio_24h"
            ),
            "track_stability_score_delta_prev_24h": stability_delta,
            "track_fragmented_ratio_delta_prev_24h": fragmented_delta,
            "track_gaps_ratio_delta_prev_24h": gaps_delta,
            "track_quality_regression_24h": regression_detected,
            "strict_quality_ready": bool(
                strict_quality.get("strict_quality_ready")
            ),
        },
        "samples": {
            "track_quality_regression_24h": regression_block,
            "track_unstable_examples_24h_top5": unstable_examples[:5],
        },
        "gates": gates,
        "ok": ok,
    }


def build_markdown_summary(report: dict[str, Any]) -> str:
    metrics = (
        report.get("metrics")
        if isinstance(report.get("metrics"), dict)
        else {}
    )
    regression = (
        report.get("samples", {}).get("track_quality_regression_24h", {})
        if isinstance(report.get("samples"), dict)
        else {}
    )
    reasons = regression.get("reasons") if isinstance(regression, dict) else []
    reasons_l = reasons if isinstance(reasons, list) else []
    reasons_text = (
        ", ".join(str(r) for r in reasons_l)
        if reasons_l
        else "none"
    )
    return "\n".join(
        [
            "## Track Quality Regression",
            "",
            f"- `ok`: **{bool(report.get('ok'))}**",
            (
                "- `track_quality_regression_24h`: "
                f"**{bool(metrics.get('track_quality_regression_24h'))}**"
            ),
            (
                "- `strict_quality_ready`: "
                f"**{bool(metrics.get('strict_quality_ready'))}**"
            ),
            f"- `track_rows_with_id_24h`: **{metrics.get('track_rows_with_id_24h')}**",
            (
                "- `track_stability_score_avg_24h`: "
                f"**{metrics.get('track_stability_score_avg_24h')}**"
            ),
            (
                "- `track_stability_score_delta_prev_24h`: "
                f"**{metrics.get('track_stability_score_delta_prev_24h')}**"
            ),
            (
                "- `track_fragmented_ratio_delta_prev_24h`: "
                f"**{metrics.get('track_fragmented_ratio_delta_prev_24h')}**"
            ),
            (
                "- `track_gaps_ratio_delta_prev_24h`: "
                f"**{metrics.get('track_gaps_ratio_delta_prev_24h')}**"
            ),
            f"- `regression_reasons`: **{reasons_text}**",
            "",
        ]
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout-sec", type=int, default=20)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--mcp-token", default="")
    parser.add_argument(
        "--out",
        required=True,
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--summary-out",
        default="",
        help="Optional markdown summary path for GITHUB_STEP_SUMMARY.",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero when regression gate fails.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    domain = fetch_domain_health_payload(
        base_url=args.base_url,
        timeout_sec=int(args.timeout_sec),
        api_key=(args.api_key or "").strip() or None,
        mcp_token=(args.mcp_token or "").strip() or None,
    )
    report = build_track_quality_regression_report(
        domain_health_payload=domain,
        base_url=args.base_url,
        fail_on_regression=bool(args.fail_on_regression),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.summary_out:
        summary_path = Path(args.summary_out).expanduser().resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            build_markdown_summary(report),
            encoding="utf-8",
        )
    return 0 if bool(report.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
