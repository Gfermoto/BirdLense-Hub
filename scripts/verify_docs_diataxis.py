#!/usr/bin/env python3
"""Verify docs Diataxis classification coverage contract (#541)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ALLOWED_TYPES = ("tutorial", "how-to", "reference", "explanation")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _normalize_type(raw: Any) -> str:
    return str(raw or "").strip().lower()


def evaluate_diataxis(plan: dict[str, Any]) -> dict[str, Any]:
    targets = plan.get("targets") or []
    if not isinstance(targets, list):
        targets = []
    rows: list[dict[str, Any]] = []
    classified = 0
    cross_type_bleed = 0
    for row in targets:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "").strip()
        d_type = _normalize_type(row.get("diataxis_type"))
        exists = bool(rel and (REPO / rel).is_file())
        type_ok = bool(d_type in ALLOWED_TYPES)
        # Lightweight bleed heuristic: explicit multi-type declaration.
        bleed = "," in d_type or "/" in d_type
        if exists and type_ok:
            classified += 1
        if bleed:
            cross_type_bleed += 1
        rows.append(
            {
                "path": rel,
                "diataxis_type": d_type,
                "exists": exists,
                "type_ok": type_ok,
                "bleed_flag": bleed,
            }
        )
    total = len(rows)
    coverage_pct = round((classified / total) * 100.0, 2) if total else 0.0
    bleed_pct = round((cross_type_bleed / total) * 100.0, 2) if total else 0.0
    min_coverage_pct = float(plan.get("min_coverage_pct") or 100.0)
    max_bleed_pct = float(plan.get("max_cross_type_bleed_pct") or 30.0)
    coverage_ok = bool(coverage_pct >= min_coverage_pct)
    bleed_ok = bool(bleed_pct <= max_bleed_pct)
    ok = bool(coverage_ok and bleed_ok and total > 0)
    return {
        "schema": "docs_diataxis_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": {
            "allowed_types": list(ALLOWED_TYPES),
            "min_coverage_pct": min_coverage_pct,
            "max_cross_type_bleed_pct": max_bleed_pct,
        },
        "coverage": {
            "classified": int(classified),
            "total": int(total),
            "coverage_pct": coverage_pct,
            "ok": coverage_ok,
        },
        "cross_type_bleed": {
            "flagged": int(cross_type_bleed),
            "bleed_pct": bleed_pct,
            "ok": bleed_ok,
        },
        "targets": rows,
        "ok": ok,
    }


def _to_md(report: dict[str, Any], plan_file: Path) -> str:
    cov = report.get("coverage") or {}
    bleed = report.get("cross_type_bleed") or {}
    return "\n".join(
        [
            "# Docs Diataxis Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- plan_file: `{plan_file}`",
            f"- coverage_pct: `{cov.get('coverage_pct')}`",
            f"- classified: `{cov.get('classified')}/{cov.get('total')}`",
            f"- bleed_pct: `{bleed.get('bleed_pct')}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        default="docs/reports/docs_diataxis/diataxis_plan.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/docs_diataxis/docs_diataxis_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/docs_diataxis/docs_diataxis_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    plan_file = Path(args.plan).expanduser()
    if not plan_file.is_absolute():
        plan_file = REPO / plan_file
    report = evaluate_diataxis(_read_json(plan_file))
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
    out_md.write_text(_to_md(report, plan_file), encoding="utf-8")
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
