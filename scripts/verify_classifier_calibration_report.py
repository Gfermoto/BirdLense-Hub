#!/usr/bin/env python3
"""Verify classifier_calibration_report@v1 gate thresholds."""

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


def verify_report(
    *,
    report: dict[str, Any],
    max_ece: float = 0.25,
    max_false_species_rate_before: float = 0.9,
    max_unknown_share_after_policy: float = 0.8,
) -> tuple[bool, list[str]]:
    errs: list[str] = []
    samples = int(report.get("corrections_analyzed") or 0)
    if samples <= 0:
        errs.append("no_corrections_samples")
    calibration = (
        report.get("calibration_metrics")
        if isinstance(report.get("calibration_metrics"), dict)
        else {}
    )
    topk = (
        report.get("topk_metrics")
        if isinstance(report.get("topk_metrics"), dict)
        else {}
    )
    ece_raw = calibration.get("ece")
    false_rate_raw = topk.get("false_species_rate_before")
    unknown_raw = topk.get("unknown_share_after_policy")
    try:
        ece = float(ece_raw) if ece_raw is not None else None
    except (TypeError, ValueError):
        ece = None
    try:
        false_rate = (
            float(false_rate_raw)
            if false_rate_raw is not None
            else None
        )
    except (TypeError, ValueError):
        false_rate = None
    try:
        unknown_share = float(unknown_raw) if unknown_raw is not None else None
    except (TypeError, ValueError):
        unknown_share = None
    if ece is None:
        errs.append("ece_missing")
    elif ece > float(max_ece):
        errs.append(f"ece_too_high:{ece}")
    if false_rate is None:
        errs.append("false_species_rate_before_missing")
    elif false_rate > float(max_false_species_rate_before):
        errs.append(f"false_species_rate_before_high:{false_rate}")
    if unknown_share is None:
        errs.append("unknown_share_after_policy_missing")
    elif unknown_share > float(max_unknown_share_after_policy):
        errs.append(f"unknown_share_after_policy_high:{unknown_share}")
    return (len(errs) == 0), errs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-ece", type=float, default=0.25)
    parser.add_argument(
        "--max-false-species-rate-before",
        type=float,
        default=0.9,
    )
    parser.add_argument(
        "--max-unknown-share-after-policy",
        type=float,
        default=0.8,
    )
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = _load_json(args.report)
    ok, errs = verify_report(
        report=report,
        max_ece=float(args.max_ece),
        max_false_species_rate_before=float(
            args.max_false_species_rate_before
        ),
        max_unknown_share_after_policy=float(
            args.max_unknown_share_after_policy
        ),
    )
    out = {
        "schema": "verify_classifier_calibration_report@v1",
        "ok": ok,
        "errors": errs,
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
