#!/usr/bin/env python3
"""Verify SSDF control mapping completeness and gaps (#551)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
REQUIRED_PRACTICES = (
    "PO.1",
    "PO.3",
    "PS.1",
    "PS.2",
    "PW.4",
    "PW.8",
    "RV.1",
    "RV.3",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def evaluate_ssdf_map(payload: dict[str, Any]) -> dict[str, Any]:
    controls = payload.get("controls") or []
    if not isinstance(controls, list):
        controls = []
    by_id: dict[str, dict[str, Any]] = {}
    malformed: list[str] = []
    p0_p1_open_gaps = 0
    for item in controls:
        if not isinstance(item, dict):
            malformed.append("non_object_control")
            continue
        pid = str(item.get("ssdf_practice") or "").strip()
        if not pid:
            malformed.append("missing_ssdf_practice")
            continue
        owner = str(item.get("owner") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        evidence = item.get("evidence")
        evidence_ok = isinstance(evidence, list) and bool(evidence)
        if not owner or not evidence_ok:
            malformed.append(pid)
        if str(item.get("priority") or "").strip().upper() in ("P0", "P1"):
            if status != "implemented":
                p0_p1_open_gaps += 1
        by_id[pid] = {
            "status": status,
            "owner": owner,
            "evidence_ok": bool(evidence_ok),
        }

    missing = [pid for pid in REQUIRED_PRACTICES if pid not in by_id]
    covered = sum(1 for pid in REQUIRED_PRACTICES if pid in by_id)
    coverage_pct = round((covered / float(len(REQUIRED_PRACTICES))) * 100.0, 2)
    ok = bool(
        not missing
        and not malformed
        and p0_p1_open_gaps == 0
    )
    return {
        "schema": "ssdf_control_map_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "required_practices": list(REQUIRED_PRACTICES),
        "coverage": {
            "covered": int(covered),
            "total": int(len(REQUIRED_PRACTICES)),
            "percent": coverage_pct,
        },
        "missing_practices": missing,
        "malformed_controls": malformed,
        "p0_p1_open_gaps": int(p0_p1_open_gaps),
        "ok": ok,
    }


def _to_md(report: dict[str, Any], source_file: Path) -> str:
    coverage = report.get("coverage") or {}
    return "\n".join(
        [
            "# SSDF Control Map Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- source_file: `{source_file}`",
            f"- coverage: `{coverage.get('covered')}/{coverage.get('total')}`",
            f"- coverage_pct: `{coverage.get('percent')}`",
            f"- p0_p1_open_gaps: `{report.get('p0_p1_open_gaps')}`",
            f"- ok: `{report.get('ok')}`",
            "",
            "## Missing Practices",
            "",
            (
                ", ".join(report.get("missing_practices") or [])
                if report.get("missing_practices")
                else "none"
            ),
            "",
            "## Malformed Controls",
            "",
            (
                ", ".join(report.get("malformed_controls") or [])
                if report.get("malformed_controls")
                else "none"
            ),
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--map-file",
        default="docs/reports/ssdf/ssdf_control_map.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/ssdf/ssdf_control_map_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/ssdf/ssdf_control_map_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    source = Path(args.map_file).expanduser()
    if not source.is_absolute():
        source = REPO / source
    report = evaluate_ssdf_map(_load_json(source))

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
    out_md.write_text(_to_md(report, source), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "coverage_pct": (report.get("coverage") or {}).get("percent"),
                "json": str(out_json),
                "md": str(out_md),
            }
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
