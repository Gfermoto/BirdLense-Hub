#!/usr/bin/env python3
"""Build Day-1 baseline artifact for SOTA-0-01 / SOTA-2-01."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return _sha256_bytes(path.read_bytes())


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


def _headers(api_key: str, mcp_token: str) -> dict[str, str]:
    if api_key:
        return {"X-Birdlense-Api-Key": api_key}
    if mcp_token:
        return {"Authorization": f"Bearer {mcp_token}"}
    return {}


def _http_json(
    base_url: str,
    path: str,
    *,
    timeout_sec: int,
    headers: dict[str, str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    url = f"{base_url.rstrip('/')}{path}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read()
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                return None, {"url": url, "error": "non_object_json"}
            return payload, None
    except HTTPError as exc:
        return None, {"url": url, "error": f"http_{exc.code}"}
    except URLError as exc:
        return None, {"url": url, "error": f"url_error:{exc.reason}"}
    except TimeoutError:
        return None, {"url": url, "error": "timeout"}
    except json.JSONDecodeError:
        return None, {"url": url, "error": "invalid_json"}


def _config_fingerprint() -> dict[str, Any]:
    paths = {
        "version": REPO / "VERSION",
        "default_config": REPO / "app" / "app_config" / "default_config.yaml",
        "user_config": REPO / "app" / "app_config" / "user_config.yaml",
        "openapi": REPO / "app" / "web" / "openapi.yaml",
    }
    file_hashes: dict[str, Any] = {}
    for key, path in paths.items():
        file_hashes[key] = {
            "path": str(path.relative_to(REPO)),
            "sha256": _sha256_file(path),
        }
    material = json.dumps(file_hashes, sort_keys=True).encode("utf-8")
    return {
        "schema": "config_fingerprint@v1",
        "material_sha256": _sha256_bytes(material),
        "files": file_hashes,
    }


def _trigger_graph(status_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(status_payload, dict):
        return {
            "schema": "trigger_graph_snapshot@v1",
            "available": False,
            "active_triggers": [],
        }
    triggers = status_payload.get("active_triggers")
    if not isinstance(triggers, list):
        triggers = []
    return {
        "schema": "trigger_graph_snapshot@v1",
        "available": True,
        "active_triggers": [str(t) for t in triggers],
    }


def _core_status(snapshot: dict[str, Any]) -> dict[str, Any]:
    checks = snapshot.get("checks", {})
    health = checks.get("health")
    readiness = checks.get("readiness")
    status = checks.get("status")
    health_ok = isinstance(health, dict) and health.get("status") == "ok"
    readiness_ok = isinstance(readiness, dict) and bool(
        readiness.get("ready")
    )
    status_ok = isinstance(status, dict) and status.get("web") == "ok"
    return {
        "health_ok": bool(health_ok),
        "readiness_ok": bool(readiness_ok),
        "status_web_ok": bool(status_ok),
        "ok": bool(health_ok and readiness_ok and status_ok),
    }


def _to_md(snapshot: dict[str, Any]) -> str:
    checks = snapshot["checks"]
    core = snapshot["core_contract"]
    trigger = snapshot["trigger_graph"]
    errors = snapshot["errors"]
    lines = [
        "# Parity Daily Hold",
        "",
        f"- generated_at: `{snapshot['generated_at']}`",
        f"- base_url: `{snapshot['base_url']}`",
        f"- epoch_fingerprint: `{snapshot['epoch_fingerprint']}`",
        "",
        "## Core Contract",
        "",
        f"- health_ok: `{core['health_ok']}`",
        f"- readiness_ok: `{core['readiness_ok']}`",
        f"- status_web_ok: `{core['status_web_ok']}`",
        f"- overall_ok: `{core['ok']}`",
        "",
        "## Trigger Graph Snapshot",
        "",
        f"- available: `{trigger['available']}`",
        f"- active_triggers: `{', '.join(trigger.get('active_triggers', []))}`",
        "",
        "## Endpoint Availability",
        "",
        f"- `/api/ui/health`: `{'ok' if checks['health'] else 'fail'}`",
        f"- `/api/ui/readiness`: `{'ok' if checks['readiness'] else 'fail'}`",
        f"- `/api/ui/status`: `{'ok' if checks['status'] else 'fail'}`",
        f"- `/api/ui/system/domain-health`: `{'ok' if checks['domain_health'] else 'fail'}`",
        "",
        "## Errors",
        "",
    ]
    if errors:
        for err in errors:
            lines.append(
                f"- `{err.get('url', '?')}` -> `{err.get('error', 'unknown_error')}`"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DEPLOY_URL", "http://127.0.0.1:8085"),
    )
    parser.add_argument("--timeout-sec", type=int, default=15)
    parser.add_argument("--out-dir", default="docs/reports/parity_daily_hold")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("BIRDLENSE_UI_API_KEY", ""),
    )
    parser.add_argument("--mcp-token", default=os.environ.get("MCP_TOKEN", ""))
    parser.add_argument("--require-core-ok", action="store_true")
    args = parser.parse_args()

    auth_headers = _headers(args.api_key, args.mcp_token)
    checks: dict[str, dict[str, Any] | None] = {}
    errors: list[dict[str, Any]] = []

    for key, path in (
        ("health", "/api/ui/health"),
        ("readiness", "/api/ui/readiness"),
        ("status", "/api/ui/status"),
        ("domain_health", "/api/ui/system/domain-health"),
    ):
        payload, err = _http_json(
            args.base_url,
            path,
            timeout_sec=max(1, int(args.timeout_sec)),
            headers=auth_headers,
        )
        checks[key] = payload
        if err:
            errors.append(err)

    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    config_fp = _config_fingerprint()
    git_meta = {
        "branch": _git(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": _git(["git", "rev-parse", "HEAD"]),
        "commit_short": _git(["git", "rev-parse", "--short", "HEAD"]),
    }
    trigger_graph = _trigger_graph(checks.get("status"))

    epoch_seed = json.dumps(
        {
            "base_url": args.base_url,
            "config_material_sha256": config_fp["material_sha256"],
            "git_commit": git_meta["commit"],
            "active_triggers": trigger_graph.get("active_triggers", []),
        },
        ensure_ascii=True,
        sort_keys=True,
    ).encode("utf-8")

    snapshot = {
        "schema": "parity_daily_hold@v1",
        "generated_at": generated_at,
        "base_url": args.base_url,
        "git": git_meta,
        "config_fingerprint": config_fp,
        "trigger_graph": trigger_graph,
        "checks": checks,
        "errors": errors,
        "epoch_fingerprint": _sha256_bytes(epoch_seed),
    }
    snapshot["core_contract"] = _core_status(snapshot)

    out_dir = (REPO / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"parity_daily_hold_{stamp}.json"
    md_path = out_dir / f"parity_daily_hold_{stamp}.md"
    json_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_to_md(snapshot), encoding="utf-8")

    print(
        json.dumps(
            {"ok": True, "json": str(json_path), "md": str(md_path)},
            ensure_ascii=False,
        )
    )
    if args.require_core_ok and not bool(snapshot["core_contract"]["ok"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
