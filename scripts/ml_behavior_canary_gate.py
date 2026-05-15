#!/usr/bin/env python3
"""Офлайн-гейт для сравнения двух behavior_train_report@v1 (baseline vs canary), #416 Wave 6."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object in {path}")
    return payload


def build_behavior_canary_gate_report(
    *,
    baseline_report: dict[str, Any],
    canary_report: dict[str, Any],
    max_macro_f1_drop: float = 0.03,
    max_accuracy_drop: float = 0.05,
) -> dict[str, Any]:
    if str(baseline_report.get("schema") or "") != "behavior_train_report@v1":
        raise ValueError("baseline schema must be behavior_train_report@v1")
    if str(canary_report.get("schema") or "") != "behavior_train_report@v1":
        raise ValueError("canary schema must be behavior_train_report@v1")

    bm = baseline_report.get("metrics") or {}
    cm = canary_report.get("metrics") or {}
    b_f1 = float(bm.get("macro_f1") or 0.0)
    c_f1 = float(cm.get("macro_f1") or 0.0)
    b_acc = float(bm.get("accuracy") or 0.0)
    c_acc = float(cm.get("accuracy") or 0.0)

    f1_drop = b_f1 - c_f1
    acc_drop = b_acc - c_acc

    gates = {
        "macro_f1_regression_ok": bool(f1_drop <= float(max_macro_f1_drop)),
        "accuracy_regression_ok": bool(acc_drop <= float(max_accuracy_drop)),
        "canary_report_ok": bool(canary_report.get("ok")),
    }

    return {
        "schema": "behavior_canary_gate_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": {
            "max_macro_f1_drop": float(max_macro_f1_drop),
            "max_accuracy_drop": float(max_accuracy_drop),
        },
        "metrics": {
            "baseline_macro_f1": round(b_f1, 6),
            "canary_macro_f1": round(c_f1, 6),
            "macro_f1_drop": round(f1_drop, 6),
            "baseline_accuracy": round(b_acc, 6),
            "canary_accuracy": round(c_acc, 6),
            "accuracy_drop": round(acc_drop, 6),
        },
        "gates": gates,
        "ok": all(bool(v) for v in gates.values()),
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-report", required=True)
    p.add_argument("--canary-report", required=True)
    p.add_argument("--max-macro-f1-drop", type=float, default=0.03)
    p.add_argument("--max-accuracy-drop", type=float, default=0.05)
    p.add_argument("--out", required=True)
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    base = _load(args.baseline_report)
    can = _load(args.canary_report)
    rep = build_behavior_canary_gate_report(
        baseline_report=base,
        canary_report=can,
        max_macro_f1_drop=float(args.max_macro_f1_drop),
        max_accuracy_drop=float(args.max_accuracy_drop),
    )
    outp = Path(args.out).expanduser().resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
