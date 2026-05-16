#!/usr/bin/env python3
"""Build detector-first baseline protocol report for issue #403."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be JSON object")
    return data


def _recall_values(report: dict[str, Any]) -> list[float]:
    vals: list[float] = []
    rows = report.get("videos")
    if not isinstance(rows, list):
        return vals
    for row in rows:
        if not isinstance(row, dict):
            continue
        label_eval = row.get("label_eval")
        if not isinstance(label_eval, dict):
            continue
        if label_eval.get("skipped"):
            continue
        value = label_eval.get("gold_species_recall")
        try:
            x = float(value)
        except (TypeError, ValueError):
            continue
        vals.append(x)
    return vals


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _metric_from_videos(report: dict[str, Any], field: str) -> float:
    rows = report.get("videos")
    if not isinstance(rows, list):
        return 0.0
    vals: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = row.get(field)
        try:
            vals.append(float(value))
        except (TypeError, ValueError):
            continue
    return _mean(vals)


def build_baseline_protocol_report(
    *,
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
    continuity_report: dict[str, Any] | None,
    max_recall_drop: float,
    max_yolo_silent_clip_rate: float,
) -> dict[str, Any]:
    baseline_recalls = _recall_values(baseline_report)
    candidate_recalls = _recall_values(candidate_report)
    baseline_recall_mean = _mean(baseline_recalls)
    candidate_recall_mean = _mean(candidate_recalls)
    recall_delta = candidate_recall_mean - baseline_recall_mean
    yolo_silent_rate = _metric_from_videos(candidate_report, "yolo_silent_clip_rate")

    continuity_track_ok = True
    continuity_crop_ok = True
    continuity_schema = None
    if isinstance(continuity_report, dict):
        continuity_schema = continuity_report.get("schema")
        metrics = continuity_report.get("metrics")
        if isinstance(metrics, dict):
            continuity_track_ok = bool(metrics.get("track_gate_ok", True))
            continuity_crop_ok = bool(metrics.get("crop_gate_ok", True))

    gates = {
        "quality_recall_gate_ok": bool(recall_delta >= -float(max_recall_drop)),
        "quality_yolo_silent_gate_ok": bool(yolo_silent_rate <= float(max_yolo_silent_clip_rate)),
        "continuity_track_gate_ok": continuity_track_ok,
        "continuity_crop_gate_ok": continuity_crop_ok,
    }
    out = {
        "schema": "ml_baseline_protocol@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "baseline_report_format": baseline_report.get("report_format"),
            "candidate_report_format": candidate_report.get("report_format"),
            "continuity_report_schema": continuity_schema,
        },
        "thresholds": {
            "max_recall_drop": float(max_recall_drop),
            "max_yolo_silent_clip_rate": float(max_yolo_silent_clip_rate),
        },
        "metrics": {
            "baseline_recall_mean": round(baseline_recall_mean, 6),
            "candidate_recall_mean": round(candidate_recall_mean, 6),
            "recall_delta": round(recall_delta, 6),
            "candidate_yolo_silent_clip_rate": round(yolo_silent_rate, 6),
            "baseline_label_eval_samples": len(baseline_recalls),
            "candidate_label_eval_samples": len(candidate_recalls),
        },
        "gates": gates,
    }
    out["ok"] = all(bool(v) for v in gates.values())
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-report",
        required=True,
        help="JSON from benchmark-track-regen.py (baseline, e.g. Frigate/BirdLense reference)",
    )
    parser.add_argument(
        "--candidate-report",
        required=True,
        help="JSON from benchmark-track-regen.py (current candidate)",
    )
    parser.add_argument(
        "--continuity-report",
        default="",
        help="Optional JSON from ml_detector_continuity_report.py",
    )
    parser.add_argument(
        "--max-recall-drop",
        type=float,
        default=0.02,
        help="Allowed absolute drop in mean recall versus baseline",
    )
    parser.add_argument(
        "--max-yolo-silent-clip-rate",
        type=float,
        default=0.20,
        help="Allowed mean yolo_silent_clip_rate in candidate report",
    )
    parser.add_argument("--out", default="", help="Optional path to write report JSON")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    baseline = _read_json(args.baseline_report)
    candidate = _read_json(args.candidate_report)
    continuity = _read_json(args.continuity_report) if str(args.continuity_report).strip() else None

    report = build_baseline_protocol_report(
        baseline_report=baseline,
        candidate_report=candidate,
        continuity_report=continuity,
        max_recall_drop=args.max_recall_drop,
        max_yolo_silent_clip_rate=args.max_yolo_silent_clip_rate,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    out = str(args.out or "").strip()
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
