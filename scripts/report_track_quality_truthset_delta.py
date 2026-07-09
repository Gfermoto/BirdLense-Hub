#!/usr/bin/env python3
"""Build track_quality_truthset_delta_report@v1.

From baseline + benchmark_sota.
"""

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


def _derive_proxies(
    metrics: dict[str, Any],
    *,
    max_track_id_switches_ref: int = 8,
    min_avg_track_duration_ref: float = 0.2,
) -> dict[str, float | int]:
    yolo_frames_ran = _metric_int(metrics, "yolo_frames_ran")
    frames_with_tracks = _metric_int(metrics, "frames_with_tracks")
    idsw_count = _metric_int(metrics, "track_id_switches_count")
    avg_track_duration_sec = _metric_float(metrics, "avg_track_duration_sec")
    idf1_proxy = (
        (frames_with_tracks / float(yolo_frames_ran))
        if yolo_frames_ran > 0
        else 0.0
    )
    idsw_quality = 1.0 - min(
        1.0,
        idsw_count / float(max(max_track_id_switches_ref, 1)),
    )
    hota_proxy = math.sqrt(max(0.0, idf1_proxy) * max(0.0, idsw_quality))
    if min_avg_track_duration_ref > 0:
        fragmentation_proxy = max(
            0.0,
            1.0 - (avg_track_duration_sec / float(min_avg_track_duration_ref)),
        )
    else:
        fragmentation_proxy = 0.0
    return {
        "idsw_count": idsw_count,
        "idf1_proxy": round(idf1_proxy, 6),
        "hota_proxy": round(hota_proxy, 6),
        "fragmentation_proxy": round(fragmentation_proxy, 6),
    }


def build_truthset_delta_report(
    *,
    baseline: dict[str, Any],
    benchmark_sota_report: dict[str, Any],
    target_switch_reduction_ratio: float = 0.2,
) -> dict[str, Any]:
    base_metrics_all = (
        baseline.get("metrics")
        if isinstance(baseline.get("metrics"), dict)
        else {}
    )
    base_1819 = (
        base_metrics_all.get("1819")
        if isinstance(base_metrics_all.get("1819"), dict)
        else {}
    )
    base_thresholds_all = (
        baseline.get("thresholds")
        if isinstance(baseline.get("thresholds"), dict)
        else {}
    )
    base_thresholds_1819 = (
        base_thresholds_all.get("1819")
        if isinstance(base_thresholds_all.get("1819"), dict)
        else {}
    )
    max_track_id_switches_ref = int(
        base_thresholds_1819.get("max_track_id_switches", 8)
    )
    min_avg_track_duration_ref = float(
        base_thresholds_1819.get("min_avg_track_duration_sec", 0.2)
    )

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
    after_metrics = (
        clip_1819.get("metrics")
        if isinstance(clip_1819.get("metrics"), dict)
        else {}
    )

    before = _derive_proxies(
        base_1819,
        max_track_id_switches_ref=max_track_id_switches_ref,
        min_avg_track_duration_ref=min_avg_track_duration_ref,
    )
    after = _derive_proxies(
        after_metrics,
        max_track_id_switches_ref=max_track_id_switches_ref,
        min_avg_track_duration_ref=min_avg_track_duration_ref,
    )

    idsw_before = int(before["idsw_count"])
    idsw_after = int(after["idsw_count"])
    if idsw_before > 0:
        idsw_reduction_ratio = round(
            max(0.0, (idsw_before - idsw_after) / float(idsw_before)),
            6,
        )
    else:
        idsw_reduction_ratio = 0.0 if idsw_after > 0 else 1.0

    frag_before = float(before["fragmentation_proxy"])
    frag_after = float(after["fragmentation_proxy"])
    if frag_before > 0:
        fragmentation_reduction_ratio = round(
            max(0.0, (frag_before - frag_after) / float(frag_before)),
            6,
        )
    else:
        fragmentation_reduction_ratio = 0.0 if frag_after > 0 else 1.0

    gates = {
        "idf1_not_degraded": bool(
            float(after["idf1_proxy"]) >= float(before["idf1_proxy"])
        ),
        "hota_not_degraded": bool(
            float(after["hota_proxy"]) >= float(before["hota_proxy"])
        ),
        "idsw_reduction_target_met": bool(
            idsw_reduction_ratio >= float(target_switch_reduction_ratio)
        ),
        "fragmentation_reduction_target_met": bool(
            fragmentation_reduction_ratio >= float(target_switch_reduction_ratio)
        ),
    }

    return {
        "schema": "track_quality_truthset_delta_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "baseline_schema": baseline.get("schema"),
            "benchmark_sota_report_format": benchmark_sota_report.get(
                "report_format"
            ),
            "clip_1819_status": clip_1819.get("status"),
        },
        "thresholds": {
            "target_switch_reduction_ratio": float(
                target_switch_reduction_ratio
            ),
            "max_track_id_switches_ref": max_track_id_switches_ref,
            "min_avg_track_duration_ref": min_avg_track_duration_ref,
        },
        "before": before,
        "after": after,
        "deltas": {
            "idf1_proxy_delta": round(
                float(after["idf1_proxy"]) - float(before["idf1_proxy"]),
                6,
            ),
            "hota_proxy_delta": round(
                float(after["hota_proxy"]) - float(before["hota_proxy"]),
                6,
            ),
            "idsw_delta": int(idsw_after - idsw_before),
            "idsw_reduction_ratio": idsw_reduction_ratio,
            "fragmentation_proxy_delta": round(frag_after - frag_before, 6),
            "fragmentation_reduction_ratio": fragmentation_reduction_ratio,
        },
        "gates": gates,
        "ok": all(bool(v) for v in gates.values()),
    }


def build_markdown_summary(report: dict[str, Any]) -> str:
    deltas = (
        report.get("deltas")
        if isinstance(report.get("deltas"), dict)
        else {}
    )
    lines = [
        "## Truth-set Delta (Before/After)",
        "",
        f"- `ok`: **{bool(report.get('ok'))}**",
        f"- `IDF1 delta`: **{deltas.get('idf1_proxy_delta')}**",
        f"- `HOTA delta`: **{deltas.get('hota_proxy_delta')}**",
        f"- `IDSW delta`: **{deltas.get('idsw_delta')}**",
        f"- `IDSW reduction ratio`: **{deltas.get('idsw_reduction_ratio')}**",
        (
            "- `fragmentation reduction ratio`: "
            f"**{deltas.get('fragmentation_reduction_ratio')}**"
        ),
        "",
    ]
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        default="benchmarks/golden_baseline.json",
    )
    parser.add_argument("--benchmark-sota-report", required=True)
    parser.add_argument(
        "--target-switch-reduction-ratio",
        type=float,
        default=0.2,
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    baseline = _load_json(args.baseline)
    sota = _load_json(args.benchmark_sota_report)
    report = build_truthset_delta_report(
        baseline=baseline,
        benchmark_sota_report=sota,
        target_switch_reduction_ratio=float(
            args.target_switch_reduction_ratio
        ),
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
