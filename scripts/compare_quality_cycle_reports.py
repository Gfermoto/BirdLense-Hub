#!/usr/bin/env python3
"""Compare baseline/current quality-cycle reports for shadow A/B gate."""

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


def _f(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_reports(
    *,
    baseline_report: dict[str, Any],
    current_report: dict[str, Any],
    min_top1_gain: float = 0.0,
    min_top3_gain: float = 0.0,
    max_ece_delta: float = 0.0,
) -> dict[str, Any]:
    b_topk = (
        baseline_report.get("topk_metrics")
        if isinstance(baseline_report.get("topk_metrics"), dict)
        else {}
    )
    c_topk = (
        current_report.get("topk_metrics")
        if isinstance(current_report.get("topk_metrics"), dict)
        else {}
    )
    b_cal = (
        baseline_report.get("calibration_metrics")
        if isinstance(baseline_report.get("calibration_metrics"), dict)
        else {}
    )
    c_cal = (
        current_report.get("calibration_metrics")
        if isinstance(current_report.get("calibration_metrics"), dict)
        else {}
    )
    b_top1 = _f(b_topk.get("top1_before"))
    c_top1 = _f(c_topk.get("top1_before"))
    b_top3 = _f(b_topk.get("top3_proxy_before"))
    c_top3 = _f(c_topk.get("top3_proxy_before"))
    b_ece = _f(b_cal.get("ece"))
    c_ece = _f(c_cal.get("ece"))
    top1_gain = (
        (c_top1 - b_top1)
        if (b_top1 is not None and c_top1 is not None)
        else None
    )
    top3_gain = (
        (c_top3 - b_top3)
        if (b_top3 is not None and c_top3 is not None)
        else None
    )
    ece_delta = (
        (c_ece - b_ece)
        if (b_ece is not None and c_ece is not None)
        else None
    )
    errors: list[str] = []
    if top1_gain is None:
        errors.append("top1_gain_missing")
    elif top1_gain < float(min_top1_gain):
        errors.append(f"top1_gain_below_min:{top1_gain}")
    if top3_gain is None:
        errors.append("top3_gain_missing")
    elif top3_gain < float(min_top3_gain):
        errors.append(f"top3_gain_below_min:{top3_gain}")
    if ece_delta is None:
        errors.append("ece_delta_missing")
    elif ece_delta > float(max_ece_delta):
        errors.append(f"ece_regression:{ece_delta}")
    return {
        "schema": "quality_cycle_comparison@v1",
        "ok": len(errors) == 0,
        "errors": errors,
        "deltas": {
            "top1_gain": top1_gain,
            "top3_proxy_gain": top3_gain,
            "ece_delta": ece_delta,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-report", required=True)
    parser.add_argument("--current-report", required=True)
    parser.add_argument("--min-top1-gain", type=float, default=0.0)
    parser.add_argument("--min-top3-gain", type=float, default=0.0)
    parser.add_argument("--max-ece-delta", type=float, default=0.0)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = compare_reports(
        baseline_report=_load_json(args.baseline_report),
        current_report=_load_json(args.current_report),
        min_top1_gain=float(args.min_top1_gain),
        min_top3_gain=float(args.min_top3_gain),
        max_ece_delta=float(args.max_ece_delta),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
