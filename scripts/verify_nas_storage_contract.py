#!/usr/bin/env python3
"""Verify NAS/SFTP recordings storage contract implementation (#350)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def evaluate_nas_contract(contract: dict[str, Any]) -> dict[str, Any]:
    required_modes = {
        str(item).strip()
        for item in (contract.get("required_modes") or [])
        if str(item).strip()
    }
    required_components = {
        str(item).strip()
        for item in (contract.get("required_components") or [])
        if str(item).strip()
    }
    required_docs_keywords = [
        str(item).strip()
        for item in (contract.get("required_docs_keywords") or [])
        if str(item).strip()
    ]

    files = {
        "processor_remote_mirror": REPO
        / "app/processor/src/recordings_remote_mirror.py",
        "ui_storage_card": REPO
        / "app/ui/src/pages/System/RecordingsNasMirrorCard.tsx",
        "ui_api_test_endpoint": REPO
        / "app/web/routes/ui_system_storage_routes.py",
        "default_config_block": REPO / "app/app_config/default_config.yaml",
        "user_docs": REPO / "docs/user/configuration.md",
        "ui_api_tests": REPO
        / "app/web/tests/test_recordings_mirror_ui_api.py",
    }

    missing_components: list[str] = []
    component_checks: dict[str, bool] = {}
    for cid in required_components:
        path = files.get(cid)
        ok = bool(path and path.is_file())
        component_checks[cid] = ok
        if not ok:
            missing_components.append(cid)

    processor_text = files["processor_remote_mirror"].read_text(
        encoding="utf-8"
    )
    ui_text = files["ui_storage_card"].read_text(encoding="utf-8")
    route_text = files["ui_api_test_endpoint"].read_text(encoding="utf-8")
    cfg_text = files["default_config_block"].read_text(encoding="utf-8")
    docs_text = files["user_docs"].read_text(encoding="utf-8")

    modes_present = {
        "local_plus_background_sync": (
            "schedule_recordings_session_mirror" in processor_text
        ),
        "offload_after_success": (
            "delete_local_after_success" in processor_text
        ),
    }
    missing_modes = sorted(
        mode for mode in required_modes if not modes_present.get(mode, False)
    )

    docs_keyword_missing = sorted(
        kw for kw in required_docs_keywords if kw not in docs_text
    )

    route_contract_ok = "recordings-mirror/test" in route_text
    ui_contract_ok = "RecordingsNasMirrorCard" in ui_text
    config_contract_ok = "recordings_mirror:" in cfg_text
    api_tests_ok = files["ui_api_tests"].is_file()

    checks = {
        "components_exist_ok": len(missing_components) == 0,
        "required_modes_ok": len(missing_modes) == 0,
        "docs_keywords_ok": len(docs_keyword_missing) == 0,
        "route_contract_ok": route_contract_ok,
        "ui_contract_ok": ui_contract_ok,
        "config_contract_ok": config_contract_ok,
        "api_tests_ok": api_tests_ok,
    }
    return {
        "schema": "nas_storage_contract_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "required_components_total": len(required_components),
            "required_modes_total": len(required_modes),
            "required_docs_keywords_total": len(required_docs_keywords),
        },
        "drift": {
            "missing_components": missing_components,
            "missing_modes": missing_modes,
            "docs_keyword_missing": docs_keyword_missing,
        },
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# NAS Storage Contract Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            (
                "- missing_components: "
                f"`{len(drift.get('missing_components') or [])}`"
            ),
            f"- missing_modes: `{len(drift.get('missing_modes') or [])}`",
            (
                "- docs_keyword_missing: "
                f"`{len(drift.get('docs_keyword_missing') or [])}`"
            ),
            f"- route_contract_ok: `{checks.get('route_contract_ok')}`",
            f"- ui_contract_ok: `{checks.get('ui_contract_ok')}`",
            f"- config_contract_ok: `{checks.get('config_contract_ok')}`",
            f"- api_tests_ok: `{checks.get('api_tests_ok')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/storage/nas_storage_contract.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/storage/nas_storage_contract_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/storage/nas_storage_contract_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract_file = Path(args.contract).expanduser()
    if not contract_file.is_absolute():
        contract_file = REPO / contract_file
    report = evaluate_nas_contract(_read_json(contract_file))
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
