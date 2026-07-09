#!/usr/bin/env python3
"""Verify runtime_slo_dashboard@v1 payload from domain-health API."""

from __future__ import annotations

import argparse
import json
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("runtime_slo_dashboard payload must be a JSON object")
    return payload


def verify_report(
    report: dict[str, Any],
    *,
    min_sustained_fps: float,
    max_skipped_ratio: float,
    max_latency_p95_ms: float,
    max_per_camera_warn: int,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    dashboard = report.get("slo_dashboard")
    if not isinstance(dashboard, dict):
        errors.append("missing slo_dashboard block")
        return False, errors
    if str(dashboard.get("schema") or "") != "runtime_slo_dashboard@v1":
        errors.append("unexpected slo_dashboard schema")
    snapshot = dashboard.get("snapshot")
    status = dashboard.get("status")
    if not isinstance(snapshot, dict):
        errors.append("missing slo_dashboard.snapshot")
        snapshot = {}
    if not isinstance(status, dict):
        errors.append("missing slo_dashboard.status")
        status = {}
    try:
        fps = snapshot.get("sustained_fps_avg_24h")
        if fps is not None and float(fps) < float(min_sustained_fps):
            errors.append(
                "sustained_fps_avg_24h="
                f"{float(fps):.3f} < {float(min_sustained_fps):.3f}"
            )
    except (TypeError, ValueError):
        errors.append("invalid sustained_fps_avg_24h")
    try:
        skipped = snapshot.get("skipped_ratio_avg_24h")
        if skipped is not None and float(skipped) > float(max_skipped_ratio):
            errors.append(
                "skipped_ratio_avg_24h="
                f"{float(skipped):.4f} > {float(max_skipped_ratio):.4f}"
            )
    except (TypeError, ValueError):
        errors.append("invalid skipped_ratio_avg_24h")
    try:
        latency = snapshot.get("pipeline_latency_p95_ms_24h")
        if latency is not None and float(latency) > float(max_latency_p95_ms):
            errors.append(
                "pipeline_latency_p95_ms_24h="
                f"{float(latency):.3f} > {float(max_latency_p95_ms):.3f}"
            )
    except (TypeError, ValueError):
        errors.append("invalid pipeline_latency_p95_ms_24h")
    try:
        warn_count = int(snapshot.get("per_camera_warn_count_24h") or 0)
        if warn_count > int(max_per_camera_warn):
            errors.append(
                "per_camera_warn_count_24h="
                f"{warn_count} > {int(max_per_camera_warn)}"
            )
    except (TypeError, ValueError):
        errors.append("invalid per_camera_warn_count_24h")
    if status.get("ok") is False:
        breaches = status.get("breaches")
        if isinstance(breaches, list) and breaches:
            errors.append(
                "dashboard status not ok: "
                + ", ".join(str(x) for x in breaches)
            )
        else:
            errors.append("dashboard status not ok")
    return len(errors) == 0, errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--min-sustained-fps", type=float, default=7.0)
    parser.add_argument("--max-skipped-ratio", type=float, default=0.05)
    parser.add_argument("--max-latency-p95-ms", type=float, default=2500.0)
    parser.add_argument("--max-per-camera-warn", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    ok, errors = verify_report(
        _load_json(args.report),
        min_sustained_fps=args.min_sustained_fps,
        max_skipped_ratio=args.max_skipped_ratio,
        max_latency_p95_ms=args.max_latency_p95_ms,
        max_per_camera_warn=args.max_per_camera_warn,
    )
    if ok:
        print("runtime_slo_dashboard verify: PASS")
        return 0
    print("runtime_slo_dashboard verify: FAIL")
    for err in errors:
        print(f"- {err}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
