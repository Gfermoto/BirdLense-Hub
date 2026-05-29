#!/usr/bin/env python3
"""Verify parity_report@v1 against gate thresholds."""

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


def verify_parity_report(
    *,
    report: dict[str, Any],
    min_precision_proxy: float = 0.5,
    min_recall_proxy: float = 0.1,
    max_unknown_share: float = 0.95,
) -> tuple[bool, list[str]]:
    errs: list[str] = []
    schema = str(report.get("schema") or "")
    if schema != "parity_report@v1":
        errs.append(f"schema_invalid:{schema}")
    if not bool(report.get("ok")):
        errs.append("report_ok_false")

    sections = (
        report.get("sections")
        if isinstance(report.get("sections"), dict)
        else {}
    )
    quality = (
        sections.get("quality")
        if isinstance(sections.get("quality"), dict)
        else {}
    )
    events = (
        sections.get("event_structure")
        if isinstance(sections.get("event_structure"), dict)
        else {}
    )
    try:
        precision = float(quality.get("precision_proxy"))
    except (TypeError, ValueError):
        precision = -1.0
    try:
        recall = float(quality.get("recall_proxy"))
    except (TypeError, ValueError):
        recall = -1.0
    unknown_raw = events.get("unknown_share")
    unknown = None
    if unknown_raw is not None:
        try:
            unknown = float(unknown_raw)
        except (TypeError, ValueError):
            unknown = None

    if precision < float(min_precision_proxy):
        errs.append(f"precision_proxy_low:{precision}")
    if recall < float(min_recall_proxy):
        errs.append(f"recall_proxy_low:{recall}")
    if unknown is not None and unknown > float(max_unknown_share):
        errs.append(f"unknown_share_high:{unknown}")
    return (len(errs) == 0), errs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--min-precision-proxy", type=float, default=0.5)
    parser.add_argument("--min-recall-proxy", type=float, default=0.1)
    parser.add_argument("--max-unknown-share", type=float, default=0.95)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = _load_json(args.report)
    ok, errs = verify_parity_report(
        report=report,
        min_precision_proxy=float(args.min_precision_proxy),
        min_recall_proxy=float(args.min_recall_proxy),
        max_unknown_share=float(args.max_unknown_share),
    )
    out = {
        "schema": "verify_parity_report@v1",
        "ok": ok,
        "errors": errs,
        "input_schema": report.get("schema"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.out:
        p = Path(args.out).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
