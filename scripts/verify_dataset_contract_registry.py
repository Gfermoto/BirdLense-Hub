#!/usr/bin/env python3
"""Verify dataset contract registry coverage and required structure (#557)."""

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


def _nonempty_str_set(values: Any) -> set[str]:
    return {
        str(v).strip()
        for v in (values or [])
        if str(v).strip()
    }


def evaluate_registry(*, contract: dict[str, Any]) -> dict[str, Any]:
    required_streams = _nonempty_str_set(contract.get("required_streams"))
    contracts_raw = list(contract.get("contracts") or [])
    stream_rows: dict[str, dict[str, Any]] = {}
    for row in contracts_raw:
        if not isinstance(row, dict):
            continue
        stream = str(row.get("stream") or "").strip()
        if stream:
            stream_rows[stream] = row

    missing_streams = sorted(
        s for s in required_streams if s not in stream_rows
    )
    stream_errors: dict[str, list[str]] = {}
    valid_streams: list[str] = []

    for stream in sorted(required_streams):
        row = stream_rows.get(stream) or {}
        errors: list[str] = []

        schema = str(row.get("contract_schema") or "").strip()
        if not schema.endswith("@v1"):
            errors.append("contract_schema must end with @v1")

        required_fields = _nonempty_str_set(row.get("required_fields"))
        if not required_fields:
            errors.append("required_fields missing or empty")

        split_policy = row.get("split_policy")
        if not isinstance(split_policy, dict):
            errors.append("split_policy missing")
        else:
            split_keys = _nonempty_str_set(split_policy.get("required_keys"))
            if "train" not in split_keys or "val" not in split_keys:
                errors.append(
                    "split_policy.required_keys must include train/val"
                )
            if "cross_split_leakage_forbidden" not in split_policy:
                errors.append(
                    "split_policy.cross_split_leakage_forbidden missing"
                )

        versioning = row.get("versioning")
        if not isinstance(versioning, dict):
            errors.append("versioning missing")
        else:
            strategy = str(versioning.get("strategy") or "").strip()
            if strategy not in {"semver", "calendar_version"}:
                errors.append("versioning.strategy invalid")
            try:
                if int(versioning.get("minimum_major") or 0) < 1:
                    errors.append("versioning.minimum_major must be >= 1")
            except (TypeError, ValueError):
                errors.append("versioning.minimum_major invalid")

        provenance = row.get("provenance")
        if not isinstance(provenance, dict):
            errors.append("provenance missing")
        else:
            provenance_keys = _nonempty_str_set(
                provenance.get("required_keys")
            )
            for key in ("source_system", "collected_at", "license"):
                if key not in provenance_keys:
                    errors.append(f"provenance.required_keys missing {key}")

        if stream == "reid":
            export_policy = row.get("export_policy")
            if not isinstance(export_policy, dict):
                errors.append("reid export_policy missing")
            else:
                if bool(export_policy.get("community_export_allowed", True)):
                    errors.append(
                        "reid community_export_allowed must be false"
                    )
                if not bool(export_policy.get("private_backup_only", False)):
                    errors.append("reid private_backup_only must be true")

        if errors:
            stream_errors[stream] = errors
        else:
            valid_streams.append(stream)

    checks = {
        "required_streams_present_ok": len(missing_streams) == 0,
        "all_stream_contracts_valid_ok": len(stream_errors) == 0,
        "streams_count_ok": len(valid_streams) == len(required_streams),
    }
    return {
        "schema": "dataset_contract_registry_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "required_streams_total": len(required_streams),
            "contracts_total": len(stream_rows),
            "valid_streams_total": len(valid_streams),
        },
        "drift": {
            "missing_streams": missing_streams,
            "stream_errors": stream_errors,
        },
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    summary = report.get("summary") or {}
    drift = report.get("drift") or {}
    lines = [
        "# Dataset Contract Registry",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- required_streams_total: `{summary.get('required_streams_total')}`",
        f"- contracts_total: `{summary.get('contracts_total')}`",
        f"- valid_streams_total: `{summary.get('valid_streams_total')}`",
        (
            "- required_streams_present_ok: "
            f"`{checks.get('required_streams_present_ok')}`"
        ),
        (
            "- all_stream_contracts_valid_ok: "
            f"`{checks.get('all_stream_contracts_valid_ok')}`"
        ),
        f"- ok: `{report.get('ok')}`",
        "",
    ]
    missing_streams = list(drift.get("missing_streams") or [])
    stream_errors = drift.get("stream_errors") or {}
    if missing_streams or stream_errors:
        lines.extend(["## Drift", ""])
        if missing_streams:
            lines.append(f"- missing_streams: `{missing_streams}`")
        for stream, errors in sorted(stream_errors.items()):
            lines.append(f"- {stream}: `{errors}`")
        lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/datasets/dataset_contract_registry.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/datasets/dataset_contract_registry_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/datasets/dataset_contract_registry_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract_file = Path(args.contract).expanduser()
    if not contract_file.is_absolute():
        contract_file = REPO / contract_file

    report = evaluate_registry(contract=_read_json(contract_file))

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
