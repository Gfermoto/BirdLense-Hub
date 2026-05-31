#!/usr/bin/env python3
"""Verify integration contract registry coverage and validity (#547)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OPENAPI = REPO / "app" / "web" / "openapi.yaml"
ALLOWED_CHANNELS = {"mqtt", "http"}
ALLOWED_AUTH = {"mcp_token", "ui_api_key", "internal", "public"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _openapi_has_path(spec_text: str, path: str) -> bool:
    candidates = [path]
    if path.startswith("/api/ui/"):
        candidates.append(path.replace("/api/ui", "", 1))
    for item in candidates:
        marker = f"  {item}:"
        if marker in spec_text:
            return True
    return False


def evaluate_registry(
    registry: dict[str, Any],
    openapi_text: str,
) -> dict[str, Any]:
    contracts = registry.get("contracts") or []
    if not isinstance(contracts, list):
        contracts = []
    required_ids = {
        str(item).strip()
        for item in (registry.get("required_ids") or [])
        if str(item).strip()
    }
    min_registry_size = int(registry.get("min_registry_size") or 0)
    seen_ids: set[str] = set()
    duplicates: list[str] = []
    rows: list[dict[str, Any]] = []
    missing_docs: list[str] = []
    missing_endpoints: list[str] = []
    invalid_auth: list[str] = []
    invalid_channels: list[str] = []

    for row in contracts:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        channel = str(row.get("channel") or "").strip().lower()
        auth_mode = str(row.get("auth_mode") or "").strip().lower()
        contract_doc = str(row.get("contract_doc") or "").strip()
        status_endpoint = str(row.get("status_endpoint") or "").strip()
        if cid in seen_ids:
            duplicates.append(cid)
        seen_ids.add(cid)
        doc_ok = bool(contract_doc and (REPO / contract_doc).is_file())
        endpoint_ok = True
        if channel == "http":
            endpoint_ok = bool(
                status_endpoint
                and _openapi_has_path(openapi_text, status_endpoint)
            )
        channel_ok = channel in ALLOWED_CHANNELS
        auth_ok = auth_mode in ALLOWED_AUTH
        if not doc_ok:
            missing_docs.append(cid or contract_doc or "unknown")
        if channel == "http" and not endpoint_ok:
            missing_endpoints.append(cid or status_endpoint or "unknown")
        if not auth_ok:
            invalid_auth.append(cid or auth_mode or "unknown")
        if not channel_ok:
            invalid_channels.append(cid or channel or "unknown")
        rows.append(
            {
                "id": cid,
                "channel": channel,
                "auth_mode": auth_mode,
                "contract_doc_ok": doc_ok,
                "endpoint_ok": endpoint_ok,
                "channel_ok": channel_ok,
                "auth_ok": auth_ok,
            }
        )

    missing_required = sorted(
        item for item in required_ids if item not in seen_ids
    )
    checks = {
        "registry_size_ok": len(rows) >= min_registry_size,
        "required_ids_ok": len(missing_required) == 0,
        "duplicates_ok": len(duplicates) == 0,
        "docs_ok": len(missing_docs) == 0,
        "endpoints_ok": len(missing_endpoints) == 0,
        "channel_ok": len(invalid_channels) == 0,
        "auth_ok": len(invalid_auth) == 0,
    }
    ok = all(checks.values())
    return {
        "schema": "integration_contract_registry_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "registry_total": len(rows),
            "required_total": len(required_ids),
            "min_registry_size": min_registry_size,
        },
        "drift": {
            "missing_required_ids": missing_required,
            "duplicate_ids": duplicates,
            "missing_docs": missing_docs,
            "missing_endpoints": missing_endpoints,
            "invalid_channels": invalid_channels,
            "invalid_auth": invalid_auth,
        },
        "contracts": rows,
        "ok": bool(ok),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    drift = report.get("drift") or {}
    summary = report.get("summary") or {}
    return "\n".join(
        [
            "# Integration Contract Registry Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            (
                "- registry_total: "
                f"`{summary.get('registry_total')}` "
                f"(min `{summary.get('min_registry_size')}`)"
            ),
            f"- required_total: `{summary.get('required_total')}`",
            f"- required_ids_ok: `{checks.get('required_ids_ok')}`",
            f"- docs_ok: `{checks.get('docs_ok')}`",
            f"- endpoints_ok: `{checks.get('endpoints_ok')}`",
            (
                "- missing_required_ids: "
                f"`{len(drift.get('missing_required_ids') or [])}`"
            ),
            f"- missing_docs: `{len(drift.get('missing_docs') or [])}`",
            (
                "- missing_endpoints: "
                f"`{len(drift.get('missing_endpoints') or [])}`"
            ),
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        default="docs/reports/integrations/integration_contract_registry.json",
    )
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/integrations/"
            "integration_contract_registry_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default=(
            "docs/reports/integrations/"
            "integration_contract_registry_latest.md"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    registry_file = Path(args.registry).expanduser()
    if not registry_file.is_absolute():
        registry_file = REPO / registry_file
    report = evaluate_registry(
        registry=_read_json(registry_file),
        openapi_text=OPENAPI.read_text(encoding="utf-8"),
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
