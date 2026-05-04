#!/usr/bin/env python3
"""Build track_continuity_eval@v1 from detector continuity artifacts (#414)."""

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


def build_track_continuity_eval_report(
    *,
    continuity_report: dict[str, Any],
    max_empty_track_rate: float = 0.01,
    min_track_emit_success_rate: float = 0.995,
) -> dict[str, Any]:
    metrics = continuity_report.get("metrics") if isinstance(continuity_report.get("metrics"), dict) else {}
    rows = continuity_report.get("rows") if isinstance(continuity_report.get("rows"), dict) else {}
    detections_total = int(rows.get("yolo_like_rows_total") or continuity_report.get("detections_total") or 0)
    with_track_id = int(rows.get("yolo_like_rows_with_track_id") or 0)
    track_id_missing = int(
        continuity_report.get("track_id_missing")
        or max(0, detections_total - with_track_id)
    )
    track_ratio = float(metrics.get("track_continuity_ratio") or 0.0)
    empty_track_with_detection_rate = (
        float(track_id_missing) / float(detections_total)
        if detections_total > 0
        else 0.0
    )
    track_emit_success_rate = float(track_ratio)
    gates = {
        "empty_track_with_detection_rate_ok": bool(empty_track_with_detection_rate <= float(max_empty_track_rate)),
        "track_emit_success_rate_ok": bool(track_emit_success_rate >= float(min_track_emit_success_rate)),
    }
    return {
        "schema": "track_continuity_eval@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "continuity_schema": continuity_report.get("schema"),
            "detections_total": detections_total,
            "track_id_missing": track_id_missing,
        },
        "thresholds": {
            "max_empty_track_with_detection_rate": float(max_empty_track_rate),
            "min_track_emit_success_rate": float(min_track_emit_success_rate),
        },
        "metrics": {
            "empty_track_with_detection_rate": round(empty_track_with_detection_rate, 6),
            "track_emit_success_rate": round(track_emit_success_rate, 6),
        },
        "gates": gates,
        "ok": all(bool(v) for v in gates.values()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--continuity-report", required=True, help="Path to detector_continuity_report@v1 JSON.")
    parser.add_argument("--max-empty-track-rate", type=float, default=0.01)
    parser.add_argument("--min-track-emit-success-rate", type=float, default=0.995)
    parser.add_argument("--out", required=True, help="Output JSON path for track_continuity_eval@v1.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    continuity = _load_json(args.continuity_report)
    out = build_track_continuity_eval_report(
        continuity_report=continuity,
        max_empty_track_rate=float(args.max_empty_track_rate),
        min_track_emit_success_rate=float(args.min_track_emit_success_rate),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(out.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
