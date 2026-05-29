#!/usr/bin/env python3
"""Verify similarity_behavior_summary@v1 quality gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _f(raw: Any) -> float | None:
    try:
        if raw is None:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def verify_report(
    report: dict[str, Any],
    *,
    min_topk_hit_rate: float,
    min_behavior_macro_f1: float,
    max_retrieval_p95_ms: float,
) -> list[str]:
    errs: list[str] = []
    if str(report.get("schema") or "") != "similarity_behavior_summary@v1":
        errs.append("schema_mismatch")
    sim = report.get("similarity") if isinstance(report.get("similarity"), dict) else {}
    beh = report.get("behavior") if isinstance(report.get("behavior"), dict) else {}
    runtime = report.get("runtime_cost") if isinstance(report.get("runtime_cost"), dict) else {}

    topk = _f(sim.get("topk_hit_rate"))
    macro = _f(beh.get("macro_f1"))
    p95 = _f(sim.get("p95_query_ms"))
    if topk is None or topk < min_topk_hit_rate:
        errs.append("topk_hit_rate_below_threshold")
    if macro is None or macro < min_behavior_macro_f1:
        errs.append("behavior_macro_f1_below_threshold")
    if p95 is None or p95 > max_retrieval_p95_ms:
        errs.append("retrieval_p95_ms_above_threshold")
    if runtime.get("retrieval_p95_ok") is False:
        errs.append("runtime_guardrail_failed")
    return errs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--min-topk-hit-rate", type=float, default=0.6)
    parser.add_argument("--min-behavior-macro-f1", type=float, default=0.4)
    parser.add_argument("--max-retrieval-p95-ms", type=float, default=50.0)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = _load_json(args.report)
    errs = verify_report(
        report,
        min_topk_hit_rate=float(args.min_topk_hit_rate),
        min_behavior_macro_f1=float(args.min_behavior_macro_f1),
        max_retrieval_p95_ms=float(args.max_retrieval_p95_ms),
    )
    out = {
        "schema": "verify_similarity_behavior_summary@v1",
        "ok": not errs,
        "errors": errs,
        "input_schema": report.get("schema"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.out:
        p = Path(args.out).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if not errs else 2


if __name__ == "__main__":
    raise SystemExit(main())
