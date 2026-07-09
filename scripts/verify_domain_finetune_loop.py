#!/usr/bin/env python3
"""Verify domain fine-tune loop evidence contract (#557 Stream C)."""

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


def _marker_missing(path: Path, markers: list[str]) -> list[str]:
    if not path.is_file():
        return list(markers)
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    return missing


def _parse_uplift_f1(row: dict[str, Any], evidence_path: Path | None) -> float | None:
    raw = row.get("uplift_f1")
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    if evidence_path is None or not evidence_path.is_file():
        return None
    for line in evidence_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("- uplift_f1:"):
            try:
                return float(line.split(":", 1)[1].strip())
            except (TypeError, ValueError):
                return None
    return None


def evaluate_domain_finetune_loop(
    *,
    contract: dict[str, Any],
    champion_shadow: dict[str, Any],
    acceptance_gate: dict[str, Any],
    history_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    required_candidates = {
        str(item).strip()
        for item in (contract.get("required_candidates") or [])
        if str(item).strip()
    }
    required_evidence_markers = [
        str(item).strip()
        for item in (contract.get("required_evidence_markers") or [])
        if str(item).strip()
    ]
    require_champion_shadow_ok = bool(
        contract.get("require_champion_shadow_ok", True)
    )
    require_acceptance_gate_ok = bool(
        contract.get("require_acceptance_gate_ok", True)
    )
    require_rollback_ready_evidence = bool(
        contract.get("require_rollback_ready_evidence", True)
    )
    try:
        min_uplift_f1 = float(contract.get("min_uplift_f1") or 0.0)
    except (TypeError, ValueError):
        min_uplift_f1 = 0.0
    block_promote_on_weak_uplift = bool(
        contract.get("block_promote_on_weak_uplift", True)
    )

    candidate_history: dict[str, dict[str, Any]] = {}
    evidence_missing_files: list[str] = []
    evidence_missing_markers: dict[str, list[str]] = {}
    rollback_not_ready: list[str] = []
    weak_uplift_promotions: list[str] = []

    for row in history_rows:
        candidate_id = str(row.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        evidence_rel = str(row.get("evidence_path") or "").strip()
        evidence_path = REPO / evidence_rel if evidence_rel else Path("")
        if not evidence_rel or not evidence_path.is_file():
            evidence_missing_files.append(candidate_id)
            continue
        missing_markers = _marker_missing(
            evidence_path, required_evidence_markers
        )
        if missing_markers:
            evidence_missing_markers[candidate_id] = missing_markers
        if require_rollback_ready_evidence:
            text = evidence_path.read_text(encoding="utf-8")
            if "rollback_ready: true" not in text:
                rollback_not_ready.append(candidate_id)
        uplift_f1 = _parse_uplift_f1(row, evidence_path)
        promoted = bool(row.get("promoted"))
        if (
            block_promote_on_weak_uplift
            and promoted
            and min_uplift_f1 > 0.0
            and (uplift_f1 is None or uplift_f1 < min_uplift_f1)
        ):
            weak_uplift_promotions.append(candidate_id)
        candidate_history[candidate_id] = {
            "evidence_path": evidence_rel,
            "shadow_passed": bool(row.get("shadow_passed")),
            "unsafe_promotion": bool(row.get("unsafe_promotion")),
            "promoted": promoted,
            "uplift_f1": uplift_f1,
        }

    missing_required_candidates = sorted(
        item for item in required_candidates if item not in candidate_history
    )
    shadow_checks = champion_shadow.get("checks") or {}
    champion_shadow_ok = bool(champion_shadow.get("ok"))
    if require_champion_shadow_ok:
        champion_shadow_ok = champion_shadow_ok and bool(
            shadow_checks.get("safe_promotion_only_ok")
        )
    acceptance_ok = bool(acceptance_gate.get("ok"))
    if require_acceptance_gate_ok:
        acceptance_ok = (
            acceptance_ok and bool(acceptance_gate.get("schema")) and True
        )
    checks = {
        "required_candidates_present_ok": (
            len(missing_required_candidates) == 0
        ),
        "champion_shadow_ok": champion_shadow_ok,
        "acceptance_gate_ok": acceptance_ok,
        "evidence_files_ok": len(evidence_missing_files) == 0,
        "evidence_markers_ok": len(evidence_missing_markers) == 0,
        "rollback_ready_ok": len(rollback_not_ready) == 0,
        "promote_uplift_ok": len(weak_uplift_promotions) == 0,
    }
    return {
        "schema": "domain_finetune_loop_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "summary": {
            "required_candidates_total": len(required_candidates),
            "history_candidates_total": len(candidate_history),
            "champion_shadow_schema": champion_shadow.get("schema"),
            "acceptance_gate_schema": acceptance_gate.get("schema"),
            "min_uplift_f1": min_uplift_f1,
        },
        "drift": {
            "missing_required_candidates": missing_required_candidates,
            "evidence_missing_files": evidence_missing_files,
            "evidence_missing_markers": evidence_missing_markers,
            "rollback_not_ready": rollback_not_ready,
            "weak_uplift_promotions": weak_uplift_promotions,
        },
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    summary = report.get("summary") or {}
    drift = report.get("drift") or {}
    return "\n".join(
        [
            "# Domain Fine-tune Loop Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            (
                "- required_candidates_total: "
                f"`{summary.get('required_candidates_total')}`"
            ),
            (
                "- history_candidates_total: "
                f"`{summary.get('history_candidates_total')}`"
            ),
            f"- champion_shadow_ok: `{checks.get('champion_shadow_ok')}`",
            f"- acceptance_gate_ok: `{checks.get('acceptance_gate_ok')}`",
            f"- rollback_ready_ok: `{checks.get('rollback_ready_ok')}`",
            f"- ok: `{report.get('ok')}`",
            "",
            "## Drift",
            "",
            (
                "- missing_required_candidates: "
                f"`{len(drift.get('missing_required_candidates') or [])}`"
            ),
            (
                "- evidence_missing_files: "
                f"`{len(drift.get('evidence_missing_files') or [])}`"
            ),
            (
                "- evidence_missing_markers: "
                f"`{len(drift.get('evidence_missing_markers') or {})}`"
            ),
            (
                "- rollback_not_ready: "
                f"`{len(drift.get('rollback_not_ready') or [])}`"
            ),
            (
                "- weak_uplift_promotions: "
                f"`{len(drift.get('weak_uplift_promotions') or [])}`"
            ),
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/domain_finetune/domain_finetune_contract.json",
    )
    parser.add_argument(
        "--champion-shadow",
        default="docs/reports/ml_shadow/champion_challenger_latest.json",
    )
    parser.add_argument(
        "--acceptance-gate",
        default="docs/reports/golden_set_gate/golden_set_gate_latest.json",
    )
    parser.add_argument(
        "--history",
        default="docs/reports/ml_shadow/shadow_pipeline_history.jsonl",
    )
    parser.add_argument(
        "--out-json",
        default=(
            "docs/reports/domain_finetune/domain_finetune_loop_latest.json"
        ),
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/domain_finetune/domain_finetune_loop_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract_file = Path(args.contract).expanduser()
    if not contract_file.is_absolute():
        contract_file = REPO / contract_file
    champion_file = Path(args.champion_shadow).expanduser()
    if not champion_file.is_absolute():
        champion_file = REPO / champion_file
    acceptance_file = Path(args.acceptance_gate).expanduser()
    if not acceptance_file.is_absolute():
        acceptance_file = REPO / acceptance_file
    history_file = Path(args.history).expanduser()
    if not history_file.is_absolute():
        history_file = REPO / history_file

    report = evaluate_domain_finetune_loop(
        contract=_read_json(contract_file),
        champion_shadow=_read_json(champion_file),
        acceptance_gate=_read_json(acceptance_file),
        history_rows=_read_jsonl(history_file),
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
