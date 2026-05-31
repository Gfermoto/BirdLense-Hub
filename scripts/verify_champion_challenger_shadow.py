#!/usr/bin/env python3
"""Verify champion/challenger shadow promotion safety contract (#536)."""

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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def evaluate_shadow_pipeline(
    *,
    contract: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    required_candidates = {
        str(item).strip()
        for item in (contract.get("required_candidates") or [])
        if str(item).strip()
    }
    min_shadow_coverage_ratio = float(
        contract.get("min_shadow_coverage_ratio") or 1.0
    )
    require_documented_evidence = bool(
        contract.get("require_documented_evidence", True)
    )
    require_safe_promotion_only = bool(
        contract.get("require_safe_promotion_only", True)
    )

    candidate_seen: set[str] = set()
    shadow_passed_total = 0
    unsafe_promotions: list[str] = []
    missing_evidence: list[str] = []
    rows: list[dict[str, Any]] = []

    for row in history:
        candidate_id = str(row.get("candidate_id") or "").strip()
        champion_id = str(row.get("champion_id") or "").strip()
        shadow_passed = bool(row.get("shadow_passed"))
        unsafe_promotion = bool(row.get("unsafe_promotion"))
        evidence_path = str(row.get("evidence_path") or "").strip()
        evidence_ok = True
        if require_documented_evidence:
            evidence_ok = bool(
                evidence_path and (REPO / evidence_path).is_file()
            )
        if candidate_id:
            candidate_seen.add(candidate_id)
        if shadow_passed:
            shadow_passed_total += 1
        if unsafe_promotion and require_safe_promotion_only:
            unsafe_promotions.append(candidate_id or "unknown")
        if not evidence_ok:
            missing_evidence.append(candidate_id or evidence_path or "unknown")
        rows.append(
            {
                "candidate_id": candidate_id,
                "champion_id": champion_id,
                "shadow_passed": shadow_passed,
                "unsafe_promotion": unsafe_promotion,
                "evidence_ok": evidence_ok,
            }
        )

    missing_required = sorted(
        item for item in required_candidates if item not in candidate_seen
    )
    coverage_ratio = (
        float(len(required_candidates - set(missing_required)))
        / float(len(required_candidates))
        if required_candidates
        else 1.0
    )
    shadow_pass_rate = (
        float(shadow_passed_total) / float(len(rows))
        if rows
        else 0.0
    )

    checks = {
        "required_candidates_ok": len(missing_required) == 0,
        "shadow_coverage_ok": coverage_ratio >= min_shadow_coverage_ratio,
        "shadow_pass_rate_ok": shadow_pass_rate >= 1.0,
        "documented_evidence_ok": len(missing_evidence) == 0,
        "safe_promotion_only_ok": len(unsafe_promotions) == 0,
    }
    return {
        "schema": "champion_challenger_shadow_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "required_candidates_total": len(required_candidates),
            "covered_candidates_total": len(
                required_candidates - set(missing_required)
            ),
            "shadow_coverage_ratio": round(coverage_ratio, 6),
            "shadow_coverage_target": min_shadow_coverage_ratio,
            "history_rows": len(rows),
            "shadow_pass_rate": round(shadow_pass_rate, 6),
        },
        "drift": {
            "missing_required_candidates": missing_required,
            "unsafe_promotions": unsafe_promotions,
            "missing_evidence": missing_evidence,
        },
        "history": rows,
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    summary = report.get("summary") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# Champion Challenger Shadow Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            (
                "- shadow_coverage_ratio: "
                f"`{summary.get('shadow_coverage_ratio')}` "
                f"(target `{summary.get('shadow_coverage_target')}`)"
            ),
            f"- shadow_pass_rate: `{summary.get('shadow_pass_rate')}`",
            (
                "- missing_required_candidates: "
                f"`{len(drift.get('missing_required_candidates') or [])}`"
            ),
            (
                "- unsafe_promotions: "
                f"`{len(drift.get('unsafe_promotions') or [])}`"
            ),
            (
                "- missing_evidence: "
                f"`{len(drift.get('missing_evidence') or [])}`"
            ),
            (
                "- safe_promotion_only_ok: "
                f"`{checks.get('safe_promotion_only_ok')}`"
            ),
            (
                "- documented_evidence_ok: "
                f"`{checks.get('documented_evidence_ok')}`"
            ),
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/ml_shadow/champion_challenger_contract.json",
    )
    parser.add_argument(
        "--history",
        default="docs/reports/ml_shadow/shadow_pipeline_history.jsonl",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/ml_shadow/champion_challenger_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/ml_shadow/champion_challenger_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract_file = Path(args.contract).expanduser()
    if not contract_file.is_absolute():
        contract_file = REPO / contract_file
    history_file = Path(args.history).expanduser()
    if not history_file.is_absolute():
        history_file = REPO / history_file
    report = evaluate_shadow_pipeline(
        contract=_read_json(contract_file),
        history=_read_jsonl(history_file),
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
