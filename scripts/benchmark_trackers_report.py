#!/usr/bin/env python3
"""Build tracker_ab_report@v1 from benchmark_trackers@v1 artifact."""

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


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def build_tracker_ab_report(
    *,
    trackers_report: dict[str, Any],
    baseline_preset: str = "bytetrack_birdlense",
    min_recall_ratio_vs_baseline: float = 0.0,
) -> dict[str, Any]:
    presets = (
        trackers_report.get("presets")
        if isinstance(trackers_report.get("presets"), dict)
        else {}
    )
    baseline_raw = presets.get(baseline_preset)
    baseline = baseline_raw if isinstance(baseline_raw, dict) else {}
    baseline_fused = _as_int(baseline.get("fused_track_count"))
    rows: list[dict[str, Any]] = []
    gates: dict[str, bool] = {}

    for preset, raw in presets.items():
        if not isinstance(raw, dict):
            continue
        fused = _as_int(raw.get("fused_track_count"))
        yolo_with_tracks = _as_int(raw.get("yolo_frames_with_tracks"))
        yolo_total = _as_int(raw.get("yolo_frames_total"))
        wall_seconds = round(_as_float(raw.get("wall_seconds")), 4)
        recall_ratio = (
            round(fused / float(baseline_fused), 4)
            if baseline_fused > 0 and preset != baseline_preset
            else None
        )
        gate_key = f"{preset}_recall_ratio_vs_{baseline_preset}_ok"
        gate_ok = True
        if (
            preset != baseline_preset
            and min_recall_ratio_vs_baseline > 0
            and recall_ratio is not None
        ):
            gate_ok = bool(recall_ratio >= float(min_recall_ratio_vs_baseline))
        gates[gate_key] = gate_ok
        rows.append(
            {
                "preset": preset,
                "tracker_resolved": raw.get("tracker_resolved"),
                "fused_track_count": fused,
                "yolo_frames_with_tracks": yolo_with_tracks,
                "yolo_frames_total": yolo_total,
                "wall_seconds": wall_seconds,
                "recall_ratio_vs_baseline": recall_ratio,
                "tracking_unified_with_live": bool(
                    raw.get("tracking_unified_with_live")
                ),
            }
        )

    rows.sort(key=lambda item: item["preset"])
    ok = all(bool(v) for v in gates.values()) if gates else True
    return {
        "schema": "tracker_ab_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "report_format": trackers_report.get("report_format"),
            "clip": trackers_report.get("clip"),
            "frame_step": trackers_report.get("frame_step"),
            "baseline_preset": baseline_preset,
        },
        "thresholds": {
            "min_recall_ratio_vs_baseline": float(
                min_recall_ratio_vs_baseline
            ),
        },
        "metrics": {
            "preset_count": len(rows),
            "baseline_fused_track_count": baseline_fused,
        },
        "rows": rows,
        "gates": gates,
        "ok": ok,
    }


def build_markdown_summary(report: dict[str, Any]) -> str:
    metrics = (
        report.get("metrics")
        if isinstance(report.get("metrics"), dict)
        else {}
    )
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    lines = [
        "## Tracker A/B (Smoke)",
        "",
        f"- `ok`: **{bool(report.get('ok'))}**",
        f"- `preset_count`: **{metrics.get('preset_count')}**",
        (
            "- `baseline_fused_track_count`: "
            f"**{metrics.get('baseline_fused_track_count')}**"
        ),
        "",
        "| preset | fused_tracks | yolo_with_tracks | yolo_total | "
        "recall_ratio_vs_baseline | wall_seconds |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        ratio = row.get("recall_ratio_vs_baseline")
        ratio_cell = "-" if ratio is None else f"{ratio}"
        lines.append(
            f"| `{row.get('preset')}` | {row.get('fused_track_count')} | "
            f"{row.get('yolo_frames_with_tracks')} | "
            f"{row.get('yolo_frames_total')} | {ratio_cell} | "
            f"{row.get('wall_seconds')} |"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trackers-report",
        required=True,
        help="Path to benchmark_trackers@v1 JSON.",
    )
    parser.add_argument(
        "--baseline-preset",
        default="bytetrack_birdlense",
    )
    parser.add_argument(
        "--min-recall-ratio-vs-baseline",
        type=float,
        default=0.0,
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    source = _load_json(args.trackers_report)
    report = build_tracker_ab_report(
        trackers_report=source,
        baseline_preset=args.baseline_preset,
        min_recall_ratio_vs_baseline=float(args.min_recall_ratio_vs_baseline),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.summary_out:
        summary_path = Path(args.summary_out).expanduser().resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            build_markdown_summary(report),
            encoding="utf-8",
        )
    return 0 if bool(report.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
