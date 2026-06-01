#!/usr/bin/env python3
"""Verify final domain closure package and quality-uplift evidence (#557)."""

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


def evaluate_closure_package(
    *,
    contract: dict[str, Any],
    closure_doc: Path,
    domain_loop: dict[str, Any],
    stream_quality: dict[str, Any],
    champion_shadow: dict[str, Any],
) -> dict[str, Any]:
    closure_text = (
        closure_doc.read_text(encoding="utf-8")
        if closure_doc.is_file()
        else ""
    )
    required_sections = [
        str(item).strip()
        for item in list(contract.get("required_report_sections") or [])
        if str(item).strip()
    ]
    missing_sections = [
        section for section in required_sections if section not in closure_text
    ]
    required_runbooks = [
        str(item).strip()
        for item in list(contract.get("required_runbooks") or [])
        if str(item).strip()
    ]
    missing_runbooks = [
        path for path in required_runbooks if not (REPO / path).is_file()
    ]

    rules = contract.get("quality_uplift_rules") or {}
    stream_reid = (stream_quality.get("streams") or {}).get("reid") or {}
    shadow_checks = champion_shadow.get("checks") or {}
    checks = {
        "closure_doc_exists_ok": closure_doc.is_file(),
        "required_sections_ok": len(missing_sections) == 0,
        "required_runbooks_ok": len(missing_runbooks) == 0,
        "domain_loop_ok": (
            not bool(rules.get("require_domain_loop_ok", True))
            or bool(domain_loop.get("ok"))
        ),
        "reid_link_accuracy_ok": (
            float(stream_reid.get("link_accuracy") or 0.0)
            >= float(rules.get("min_reid_link_accuracy") or 0.0)
        ),
        "reid_id_switches_ok": (
            int(stream_reid.get("id_switches") or 0)
            <= int(rules.get("max_reid_id_switches") or 0)
        ),
        "shadow_safe_promotion_ok": (
            not bool(rules.get("require_shadow_safe_promotion_only", True))
            or bool(shadow_checks.get("safe_promotion_only_ok"))
        ),
    }
    return {
        "schema": "domain_closure_package_report@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
        "drift": {
            "missing_sections": missing_sections,
            "missing_runbooks": missing_runbooks,
        },
        "summary": {
            "closure_doc": str(closure_doc),
            "required_sections_total": len(required_sections),
            "required_runbooks_total": len(required_runbooks),
        },
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    drift = report.get("drift") or {}
    summary = report.get("summary") or {}
    return "\n".join(
        [
            "# Domain Closure Package Report",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- closure_doc: `{summary.get('closure_doc')}`",
            (
                "- required_sections_total: "
                f"`{summary.get('required_sections_total')}`"
            ),
            (
                "- required_runbooks_total: "
                f"`{summary.get('required_runbooks_total')}`"
            ),
            f"- checks: `{checks}`",
            (
                "- missing_sections: "
                f"`{len(drift.get('missing_sections') or [])}`"
            ),
            (
                "- missing_runbooks: "
                f"`{len(drift.get('missing_runbooks') or [])}`"
            ),
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/domain_finetune/closure_package_contract.json",
    )
    parser.add_argument(
        "--closure-doc",
        default="docs/reports/domain_finetune/closure_package_30_60_90.md",
    )
    parser.add_argument(
        "--domain-loop",
        default=(
            "docs/reports/domain_finetune/domain_finetune_loop_latest.json"
        ),
    )
    parser.add_argument(
        "--stream-quality",
        default="docs/reports/stream_quality/stream_quality_latest.json",
    )
    parser.add_argument(
        "--champion-shadow",
        default="docs/reports/ml_shadow/champion_challenger_latest.json",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/domain_finetune/closure_package_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/domain_finetune/closure_package_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract_file = REPO / args.contract
    closure_doc = REPO / args.closure_doc
    report = evaluate_closure_package(
        contract=_read_json(contract_file),
        closure_doc=closure_doc,
        domain_loop=_read_json(REPO / args.domain_loop),
        stream_quality=_read_json(REPO / args.stream_quality),
        champion_shadow=_read_json(REPO / args.champion_shadow),
    )
    out_json = REPO / args.out_json
    out_md = REPO / args.out_md
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
