#!/usr/bin/env python3
"""Validate behavior_runtime_profile@v1 against p95/mean latency gates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def build_behavior_runtime_gate_report(
    *,
    profile: dict,
    max_p95_ms: float,
    max_mean_ms: float,
) -> dict:
    if str(profile.get("schema") or "") != "behavior_runtime_profile@v1":
        raise ValueError("profile schema must be behavior_runtime_profile@v1")

    wall = profile.get("wall_seconds") or {}
    p95_sec = wall.get("p95")
    mean_sec = wall.get("mean")
    if p95_sec is None or mean_sec is None:
        raise ValueError("profile must contain wall_seconds.mean and wall_seconds.p95")

    p95_ms = float(p95_sec) * 1000.0
    mean_ms = float(mean_sec) * 1000.0
    gates = {
        "p95_within_limit": p95_ms <= float(max_p95_ms),
        "mean_within_limit": mean_ms <= float(max_mean_ms),
    }
    return {
        "schema": "behavior_runtime_gate_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": {
            "max_p95_ms": float(max_p95_ms),
            "max_mean_ms": float(max_mean_ms),
        },
        "metrics": {
            "p95_ms": p95_ms,
            "mean_ms": mean_ms,
        },
        "gates": gates,
        "ok": all(bool(v) for v in gates.values()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", required=True, help="behavior_runtime_profile@v1 JSON")
    ap.add_argument("--out", required=True, help="Output behavior_runtime_gate_report@v1 JSON")
    ap.add_argument(
        "--max-p95-ms",
        type=float,
        default=25.0,
        help="Maximum allowed p95 latency in milliseconds (default: 25)",
    )
    ap.add_argument(
        "--max-mean-ms",
        type=float,
        default=15.0,
        help="Maximum allowed mean latency in milliseconds (default: 15)",
    )
    args = ap.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    report = build_behavior_runtime_gate_report(
        profile=profile,
        max_p95_ms=float(args.max_p95_ms),
        max_mean_ms=float(args.max_mean_ms),
    )

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": bool(report["ok"]), "out": str(out_path)}, ensure_ascii=False))
    return 0 if report["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
