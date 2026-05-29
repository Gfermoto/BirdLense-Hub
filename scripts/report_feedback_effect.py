#!/usr/bin/env python3
"""Build feedback_effect_report@v1 from two calibration reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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


def _delta(cur: float | None, base: float | None) -> float | None:
    if cur is None or base is None:
        return None
    return float(cur - base)


def build_feedback_effect_report(
    *,
    baseline_report: dict[str, Any],
    current_report: dict[str, Any],
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
    b_false = _f(b_topk.get("false_species_rate_before"))
    c_false = _f(c_topk.get("false_species_rate_before"))
    b_ece = _f(b_cal.get("ece"))
    c_ece = _f(c_cal.get("ece"))
    deltas = {
        "top1_gain": _delta(c_top1, b_top1),
        "top3_proxy_gain": _delta(c_top3, b_top3),
        "false_species_rate_delta": _delta(c_false, b_false),
        "ece_delta": _delta(c_ece, b_ece),
    }
    gates = {
        "top1_non_regression": (
            deltas["top1_gain"] is not None and deltas["top1_gain"] >= 0.0
        ),
        "top3_non_regression": (
            deltas["top3_proxy_gain"] is not None
            and deltas["top3_proxy_gain"] >= 0.0
        ),
        "ece_non_regression": (
            deltas["ece_delta"] is not None and deltas["ece_delta"] <= 0.0
        ),
        "false_species_reduced": (
            deltas["false_species_rate_delta"] is not None
            and deltas["false_species_rate_delta"] <= 0.0
        ),
    }
    return {
        "schema": "feedback_effect_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "baseline_schema": baseline_report.get("schema"),
            "current_schema": current_report.get("schema"),
        },
        "baseline": {
            "top1_before": b_top1,
            "top3_proxy_before": b_top3,
            "false_species_rate_before": b_false,
            "ece": b_ece,
        },
        "current": {
            "top1_before": c_top1,
            "top3_proxy_before": c_top3,
            "false_species_rate_before": c_false,
            "ece": c_ece,
        },
        "deltas": deltas,
        "gates": gates,
        "ok": all(bool(v) for v in gates.values()),
    }


def build_markdown(report: dict[str, Any]) -> str:
    deltas = report.get("deltas") if isinstance(report.get("deltas"), dict) else {}
    lines = [
        "## Feedback Effect Report",
        "",
        f"- `ok`: **{bool(report.get('ok'))}**",
        f"- `top1_gain`: **{deltas.get('top1_gain')}**",
        f"- `top3_proxy_gain`: **{deltas.get('top3_proxy_gain')}**",
        f"- `false_species_rate_delta`: **{deltas.get('false_species_rate_delta')}**",
        f"- `ece_delta`: **{deltas.get('ece_delta')}**",
        "",
    ]
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-report", required=True)
    parser.add_argument("--current-report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_feedback_effect_report(
        baseline_report=_load_json(args.baseline_report),
        current_report=_load_json(args.current_report),
    )
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.summary_out:
        summary = Path(args.summary_out).expanduser().resolve()
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(build_markdown(report), encoding="utf-8")
    return 0 if bool(report.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
