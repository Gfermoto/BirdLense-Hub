#!/usr/bin/env python3
"""Verify reproducibility of parity baseline snapshots (#528)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _as_int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def _extract_aggregates(snapshot: dict[str, Any]) -> dict[str, int]:
    checks = snapshot.get("checks") or {}
    trigger = snapshot.get("trigger_graph") or {}
    core = snapshot.get("core_contract") or {}
    errors = snapshot.get("errors") or []
    status_payload = checks.get("status") if isinstance(checks, dict) else None
    status_ok_components = 0
    if isinstance(status_payload, dict):
        for value in status_payload.values():
            if isinstance(value, str) and value.strip().lower() == "ok":
                status_ok_components += 1
    return {
        "errors_total": int(len(errors) if isinstance(errors, list) else 0),
        "active_triggers_count": int(
            len(trigger.get("active_triggers") or [])
            if isinstance(trigger, dict)
            else 0
        ),
        "core_ok": _as_int_bool(
            core.get("ok") if isinstance(core, dict) else False
        ),
        "health_ok": _as_int_bool(
            core.get("health_ok") if isinstance(core, dict) else False
        ),
        "readiness_ok": _as_int_bool(
            core.get("readiness_ok") if isinstance(core, dict) else False
        ),
        "status_web_ok": _as_int_bool(
            core.get("status_web_ok") if isinstance(core, dict) else False
        ),
        "status_ok_components": int(status_ok_components),
    }


def _relative_delta(old: int, new: int) -> float:
    if old == 0 and new == 0:
        return 0.0
    if old == 0:
        return 1.0
    return abs(new - old) / float(abs(old))


def compare_snapshots(
    *,
    baseline: dict[str, Any],
    current: dict[str, Any],
    tolerance: float,
    require_same_material: bool = True,
) -> dict[str, Any]:
    old_aggr = _extract_aggregates(baseline)
    new_aggr = _extract_aggregates(current)
    deltas: dict[str, dict[str, Any]] = {}
    for key, old_value in old_aggr.items():
        new_value = int(new_aggr.get(key, 0))
        delta = _relative_delta(int(old_value), new_value)
        deltas[key] = {
            "baseline": int(old_value),
            "current": new_value,
            "relative_delta": round(delta, 6),
            "within_tolerance": bool(delta <= float(tolerance)),
        }
    schema_ok = (
        str(baseline.get("schema") or "") == "parity_daily_hold@v1"
        and str(current.get("schema") or "") == "parity_daily_hold@v1"
    )
    base_url_match = str(baseline.get("base_url") or "") == str(
        current.get("base_url") or ""
    )
    baseline_material = str(
        (
            (baseline.get("config_fingerprint") or {}).get(
                "material_sha256"
            )
            or ""
        )
    )
    current_material = str(
        (
            (current.get("config_fingerprint") or {}).get(
                "material_sha256"
            )
            or ""
        )
    )
    material_match = baseline_material == current_material
    ok = bool(
        schema_ok
        and base_url_match
        and all(bool(row.get("within_tolerance")) for row in deltas.values())
        and (
            material_match
            if require_same_material
            else True
        )
    )
    return {
        "schema": "baseline_snapshot_contract@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tolerance": float(tolerance),
        "checks": {
            "schema_ok": schema_ok,
            "base_url_match": base_url_match,
            "material_match": material_match,
            "require_same_material": bool(require_same_material),
        },
        "baseline_epoch_fingerprint": str(
            baseline.get("epoch_fingerprint") or ""
        ),
        "current_epoch_fingerprint": str(
            current.get("epoch_fingerprint") or ""
        ),
        "deltas": deltas,
        "ok": ok,
    }


def _latest_two_snapshots(path: Path) -> tuple[Path, Path]:
    files = sorted(
        path.glob("parity_daily_hold_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if len(files) < 2:
        raise FileNotFoundError(
            "need at least 2 parity snapshots for reproducibility check"
        )
    return files[1], files[0]


def _to_md(
    report: dict[str, Any],
    baseline_file: Path,
    current_file: Path,
) -> str:
    lines = [
        "# Baseline Snapshot Contract",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- baseline_file: `{baseline_file}`",
        f"- current_file: `{current_file}`",
        f"- tolerance: `{report.get('tolerance')}`",
        f"- ok: `{report.get('ok')}`",
        "",
        "## Checks",
        "",
        (
            "- schema_ok: "
            f"`{(report.get('checks') or {}).get('schema_ok')}`"
        ),
        (
            "- base_url_match: "
            f"`{(report.get('checks') or {}).get('base_url_match')}`"
        ),
        (
            "- material_match: "
            f"`{(report.get('checks') or {}).get('material_match')}`"
        ),
        "",
        "## Deltas",
        "",
    ]
    for key, row in (report.get("deltas") or {}).items():
        lines.append(
            "- "
            f"`{key}`: "
            f"base={row.get('baseline')} current={row.get('current')} "
            f"delta={row.get('relative_delta')} "
            f"within={row.get('within_tolerance')}"
        )
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-dir",
        default="docs/reports/parity_daily_hold",
    )
    parser.add_argument("--baseline-file", default="")
    parser.add_argument("--current-file", default="")
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument(
        "--allow-material-diff",
        action="store_true",
        help="Do not fail on config_fingerprint diff.",
    )
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/baseline_snapshot_contract/"
            "baseline_snapshot_contract_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default=(
            "docs/reports/baseline_snapshot_contract/"
            "baseline_snapshot_contract_latest.md"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    snapshot_dir = Path(args.snapshot_dir).expanduser()
    if not snapshot_dir.is_absolute():
        snapshot_dir = REPO / snapshot_dir
    if args.baseline_file and args.current_file:
        baseline_file = Path(args.baseline_file).expanduser()
        current_file = Path(args.current_file).expanduser()
        if not baseline_file.is_absolute():
            baseline_file = REPO / baseline_file
        if not current_file.is_absolute():
            current_file = REPO / current_file
    else:
        baseline_file, current_file = _latest_two_snapshots(snapshot_dir)

    baseline = _load_json(baseline_file)
    current = _load_json(current_file)
    report = compare_snapshots(
        baseline=baseline,
        current=current,
        tolerance=max(0.0, float(args.tolerance)),
        require_same_material=not bool(args.allow_material_diff),
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
    out_md.write_text(
        _to_md(report, baseline_file, current_file),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "baseline_file": str(baseline_file),
                "current_file": str(current_file),
                "json": str(out_json),
                "md": str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
