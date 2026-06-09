#!/usr/bin/env python3
"""Verify health/readiness/status consistency contract (#530)."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]


def _headers(api_key: str, mcp_token: str) -> dict[str, str]:
    if api_key:
        return {"X-Birdlense-Api-Key": api_key}
    if mcp_token:
        return {"Authorization": f"Bearer {mcp_token}"}
    return {}


def _http_json(
    *,
    base_url: str,
    path: str,
    timeout_sec: int,
    headers: dict[str, str],
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    url = f"{base_url.rstrip('/')}{path}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=max(1, int(timeout_sec))) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, dict):
                return None, int(resp.status), "non_object_json"
            return payload, int(resp.status), None
    except HTTPError as exc:
        status = int(exc.code)
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            if isinstance(payload, dict):
                return payload, status, None
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            pass
        return None, status, f"http_{exc.code}"
    except URLError as exc:
        return None, None, f"url_error:{exc.reason}"
    except json.JSONDecodeError:
        return None, None, "invalid_json"


def evaluate_contract(
    *,
    health_status_code: int | None,
    health_payload: dict[str, Any] | None,
    readiness_status_code: int | None,
    readiness_payload: dict[str, Any] | None,
    status_status_code: int | None,
    status_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    health_ok = bool(
        health_status_code == 200
        and isinstance(health_payload, dict)
        and str(health_payload.get("status") or "") == "ok"
    )
    readiness_ok = bool(
        readiness_status_code == 200
        and isinstance(readiness_payload, dict)
        and bool(readiness_payload.get("ready"))
    )
    status_web_ok = bool(
        status_status_code == 200
        and isinstance(status_payload, dict)
        and str(status_payload.get("web") or "") == "ok"
    )
    status_processor_ok = bool(
        status_status_code == 200
        and isinstance(status_payload, dict)
        and str(status_payload.get("processor") or "") == "ok"
    )
    false_green = bool(
        health_ok
        and (
            not readiness_ok
            or not status_web_ok
            or not status_processor_ok
        )
    )
    ok = bool(
        health_ok
        and readiness_ok
        and status_web_ok
        and status_processor_ok
        and not false_green
    )
    return {
        "schema": "health_readiness_contract@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": {
            "health_ok": bool(health_ok),
            "readiness_ok": bool(readiness_ok),
            "status_web_ok": bool(status_web_ok),
            "status_processor_ok": bool(status_processor_ok),
            "false_green_detected": bool(false_green),
        },
        "ok": bool(ok),
    }


def _to_md(report: dict[str, Any], errors: list[dict[str, Any]]) -> str:
    checks = report.get("checks") or {}
    lines = [
        "# Health Readiness Contract",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- ok: `{report.get('ok')}`",
        "",
        "## Checks",
        "",
        f"- health_ok: `{checks.get('health_ok')}`",
        f"- readiness_ok: `{checks.get('readiness_ok')}`",
        f"- status_web_ok: `{checks.get('status_web_ok')}`",
        f"- status_processor_ok: `{checks.get('status_processor_ok')}`",
        f"- false_green_detected: `{checks.get('false_green_detected')}`",
        "",
        "## Errors",
        "",
    ]
    if errors:
        for err in errors:
            lines.append(
                (
                    f"- `{err.get('path')}` "
                    f"status={err.get('status_code')} "
                    f"error={err.get('error')}"
                )
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


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
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/health_readiness_contract/"
            "health_readiness_contract_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default=(
            "docs/reports/health_readiness_contract/"
            "health_readiness_contract_latest.md"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    headers = _headers(args.api_key, args.mcp_token)
    endpoints = (
        ("health", "/api/ui/health"),
        ("readiness", "/api/ui/readiness"),
        ("status", "/api/ui/status"),
    )
    responses: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    for key, path in endpoints:
        payload, status_code, err = _http_json(
            base_url=args.base_url,
            path=path,
            timeout_sec=args.timeout_sec,
            headers=headers,
        )
        responses[key] = {"status_code": status_code, "payload": payload}
        if err:
            errors.append(
                {"path": path, "status_code": status_code, "error": err}
            )
    report = evaluate_contract(
        health_status_code=responses["health"]["status_code"],
        health_payload=responses["health"]["payload"],
        readiness_status_code=responses["readiness"]["status_code"],
        readiness_payload=responses["readiness"]["payload"],
        status_status_code=responses["status"]["status_code"],
        status_payload=responses["status"]["payload"],
    )
    report["base_url"] = args.base_url
    report["responses"] = responses
    report["errors"] = errors

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
    out_md.write_text(_to_md(report, errors), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "false_green_detected": (
                    (report.get("checks") or {}).get("false_green_detected")
                ),
                "json": str(out_json),
                "md": str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
