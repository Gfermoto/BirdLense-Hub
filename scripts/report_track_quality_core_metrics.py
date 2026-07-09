#!/usr/bin/env python3
"""Build track_quality_core_metrics_report@v1 from benchmark_sota output."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _metric_int(metrics: dict[str, Any], key: str) -> int:
    try:
        return int(metrics.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _metric_float(metrics: dict[str, Any], key: str) -> float:
    try:
        return float(metrics.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def build_track_quality_core_metrics_report(
    *,
    benchmark_sota_report: dict[str, Any],
    baseline: dict[str, Any],
    min_idf1_proxy: float = 0.05,
    min_hota_proxy: float = 0.05,
    max_fragmentation_proxy: float = 0.95,
) -> dict[str, Any]:
    clips = (
        benchmark_sota_report.get("clips")
        if isinstance(benchmark_sota_report.get("clips"), dict)
        else {}
    )
    clip_1819 = (
        clips.get("1819")
        if isinstance(clips.get("1819"), dict)
        else {}
    )
    metrics = (
        clip_1819.get("metrics")
        if isinstance(clip_1819.get("metrics"), dict)
        else {}
    )
    baseline_thresholds = (
        baseline.get("thresholds")
        if isinstance(baseline.get("thresholds"), dict)
        else {}
    )
    base_1819 = (
        baseline_thresholds.get("1819")
        if isinstance(baseline_thresholds.get("1819"), dict)
        else {}
    )

    yolo_frames_ran = _metric_int(metrics, "yolo_frames_ran")
    frames_with_tracks = _metric_int(metrics, "frames_with_tracks")
    fused_track_count = _metric_int(metrics, "fused_track_count")
    idsw_count = _metric_int(metrics, "track_id_switches_count")
    avg_track_duration_sec = _metric_float(metrics, "avg_track_duration_sec")

    min_avg_track_duration_sec = float(
        base_1819.get("min_avg_track_duration_sec", 0.2)
    )
    max_track_id_switches = int(base_1819.get("max_track_id_switches", 8))
    min_fused_track_count = int(base_1819.get("min_fused_track_count", 1))
    available = bool(yolo_frames_ran > 0 or fused_track_count > 0)
    # Synthetic CI clip: pipeline ran, zero detections — skip proxy gates (see golden_baseline_smoke.json).
    skip_proxy_gates = bool(
        min_fused_track_count <= 0
        and fused_track_count <= 0
        and frames_with_tracks <= 0
        and yolo_frames_ran > 0
    )

    idf1_proxy = None
    hota_proxy = None
    fragmentation_proxy = None
    if available and not skip_proxy_gates:
        idf1_proxy = (
            round(frames_with_tracks / float(yolo_frames_ran), 6)
            if yolo_frames_ran > 0
            else 0.0
        )
        idsw_quality = 1.0 - min(
            1.0,
            idsw_count / float(max(max_track_id_switches, 1)),
        )
        hota_proxy = round(
            math.sqrt(
                max(0.0, idf1_proxy) * max(0.0, idsw_quality)
            ),
            6,
        )
        if min_avg_track_duration_sec > 0:
            fragmentation_proxy = round(
                max(
                    0.0,
                    1.0
                    - (
                        avg_track_duration_sec
                        / float(min_avg_track_duration_sec)
                    ),
                ),
                6,
            )
        else:
            fragmentation_proxy = 0.0

    gates = {
        "idsw_count_ok": bool(idsw_count <= max_track_id_switches),
        "idf1_proxy_ok": (
            True
            if idf1_proxy is None
            else bool(idf1_proxy >= float(min_idf1_proxy))
        ),
        "hota_proxy_ok": (
            True
            if hota_proxy is None
            else bool(hota_proxy >= float(min_hota_proxy))
        ),
        "fragmentation_proxy_ok": (
            True
            if fragmentation_proxy is None
            else bool(fragmentation_proxy <= float(max_fragmentation_proxy))
        ),
    }

    return {
        "schema": "track_quality_core_metrics_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "benchmark_sota_report_format": benchmark_sota_report.get(
                "report_format"
            ),
            "clip_1819_status": clip_1819.get("status"),
            "baseline_schema": baseline.get("schema"),
        },
        "thresholds": {
            "max_track_id_switches": max_track_id_switches,
            "min_idf1_proxy": float(min_idf1_proxy),
            "min_hota_proxy": float(min_hota_proxy),
            "max_fragmentation_proxy": float(max_fragmentation_proxy),
            "min_avg_track_duration_sec_reference": min_avg_track_duration_sec,
        },
        "metrics": {
            "track_metrics_available": available,
            "skip_proxy_gates_smoke_no_detections": skip_proxy_gates,
            "yolo_frames_ran": yolo_frames_ran,
            "frames_with_tracks": frames_with_tracks,
            "fused_track_count": fused_track_count,
            "idsw_count": idsw_count,
            "avg_track_duration_sec": avg_track_duration_sec,
            "idf1_proxy": idf1_proxy,
            "hota_proxy": hota_proxy,
            "fragmentation_proxy": fragmentation_proxy,
            "metric_aliases": {
                "HOTA": "hota_proxy",
                "IDF1": "idf1_proxy",
                "IDSW": "idsw_count",
                "fragmentation": "fragmentation_proxy",
            },
        },
        "gates": gates,
        "ok": all(bool(v) for v in gates.values()),
    }


def build_markdown_summary(report: dict[str, Any]) -> str:
    metrics = (
        report.get("metrics")
        if isinstance(report.get("metrics"), dict)
        else {}
    )
    lines = [
        "## Track Quality Core Metrics",
        "",
        f"- `ok`: **{bool(report.get('ok'))}**",
        (
            "- `track_metrics_available`: "
            f"**{bool(metrics.get('track_metrics_available'))}**"
        ),
        f"- `IDSW (count)`: **{metrics.get('idsw_count')}**",
        f"- `IDF1 (proxy)`: **{metrics.get('idf1_proxy')}**",
        f"- `HOTA (proxy)`: **{metrics.get('hota_proxy')}**",
        f"- `fragmentation (proxy)`: **{metrics.get('fragmentation_proxy')}**",
        "",
    ]
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-sota-report", required=True)
    parser.add_argument(
        "--baseline",
        default="benchmarks/golden_baseline.json",
    )
    parser.add_argument("--min-idf1-proxy", type=float, default=0.05)
    parser.add_argument("--min-hota-proxy", type=float, default=0.05)
    parser.add_argument("--max-fragmentation-proxy", type=float, default=0.95)
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    sota_report = _load_json(args.benchmark_sota_report)
    baseline = _load_json(args.baseline)
    report = build_track_quality_core_metrics_report(
        benchmark_sota_report=sota_report,
        baseline=baseline,
        min_idf1_proxy=float(args.min_idf1_proxy),
        min_hota_proxy=float(args.min_hota_proxy),
        max_fragmentation_proxy=float(args.max_fragmentation_proxy),
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
