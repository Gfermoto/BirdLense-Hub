#!/usr/bin/env python3
"""Build track_failure_modes_report@v1 (occlusion/fast-motion/night-noise)."""

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


def build_track_failure_modes_report(
    *,
    benchmark_sota_report: dict[str, Any],
    benchmark_trackers_ab_report: dict[str, Any],
    track_quality_core_metrics_report: dict[str, Any],
) -> dict[str, Any]:
    clips = (
        benchmark_sota_report.get("clips")
        if isinstance(benchmark_sota_report.get("clips"), dict)
        else {}
    )
    clip_1816 = (
        clips.get("1816")
        if isinstance(clips.get("1816"), dict)
        else {}
    )
    clip_1819 = (
        clips.get("1819")
        if isinstance(clips.get("1819"), dict)
        else {}
    )
    m1816 = (
        clip_1816.get("metrics")
        if isinstance(clip_1816.get("metrics"), dict)
        else {}
    )
    m1819 = (
        clip_1819.get("metrics")
        if isinstance(clip_1819.get("metrics"), dict)
        else {}
    )
    core_metrics = (
        track_quality_core_metrics_report.get("metrics")
        if isinstance(track_quality_core_metrics_report.get("metrics"), dict)
        else {}
    )
    skip_smoke_gates = bool(
        core_metrics.get("skip_proxy_gates_smoke_no_detections")
    )
    tracker_rows = (
        benchmark_trackers_ab_report.get("rows")
        if isinstance(benchmark_trackers_ab_report.get("rows"), list)
        else []
    )
    botsort_ratio = None
    for row in tracker_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("preset") or "") == "botsort_birdlense":
            raw_ratio = row.get("recall_ratio_vs_baseline")
            if raw_ratio is not None:
                try:
                    botsort_ratio = float(raw_ratio)
                except (TypeError, ValueError):
                    botsort_ratio = None
            break

    idsw = _metric_int(m1819, "track_id_switches_count")
    avg_track_duration = _metric_float(m1819, "avg_track_duration_sec")
    yolo_frames_ran = _metric_int(m1819, "yolo_frames_ran")
    frames_with_tracks = _metric_int(m1819, "frames_with_tracks")
    frame_cover = (
        (frames_with_tracks / float(yolo_frames_ran))
        if yolo_frames_ran > 0
        else 0.0
    )
    noise_fp = _metric_int(m1816, "yolo_accepted_boxes_total")
    hota_proxy = _metric_float(core_metrics, "hota_proxy")
    idf1_proxy = _metric_float(core_metrics, "idf1_proxy")

    occlusion_risk = (
        "high"
        if idsw >= 8
        else "medium" if idsw >= 4 else "low"
    )
    fast_motion_risk = (
        "high"
        if frame_cover < 0.35 or avg_track_duration < 0.15
        else (
            "medium"
            if frame_cover < 0.55 or avg_track_duration < 0.25
            else "low"
        )
    )
    night_noise_risk = (
        "high"
        if noise_fp >= 3
        else "medium" if noise_fp >= 1 else "low"
    )

    recommendations = {
        "baseline_tracker_profile": (
            "models/tracker/bytetrack_birdlense_lowfps.yaml"
        ),
        "fallback_tracker_profile": (
            "models/tracker/bytetrack_birdlense.yaml"
        ),
        "night_tracker_profile": (
            "models/tracker/bytetrack_birdlense.yaml"
        ),
        "night_fallback_tracker_profile": (
            "models/tracker/bytetrack_birdlense.yaml"
        ),
        "runtime_switches": {
            "processor.auto_unstick_enabled": True,
            "processor.track_regen_match_live_pipeline": True,
            "processor.tracker_profiles.night": (
                "models/tracker/bytetrack_birdlense.yaml"
            ),
        },
    }

    gates = {
        "occlusion_risk_not_high": occlusion_risk != "high",
        "fast_motion_risk_not_high": fast_motion_risk != "high",
        "night_noise_risk_not_high": night_noise_risk != "high",
        "hota_proxy_not_critical": hota_proxy >= 0.05,
        "idf1_proxy_not_critical": idf1_proxy >= 0.05,
    }
    if skip_smoke_gates:
        gates = {key: True for key in gates}
    return {
        "schema": "track_failure_modes_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "benchmark_sota_report_format": benchmark_sota_report.get(
                "report_format"
            ),
            "benchmark_trackers_ab_schema": benchmark_trackers_ab_report.get(
                "schema"
            ),
            "track_quality_core_schema": track_quality_core_metrics_report.get(
                "schema"
            ),
        },
        "metrics": {
            "skip_gates_smoke_no_detections": skip_smoke_gates,
            "idsw_count_1819": idsw,
            "avg_track_duration_sec_1819": round(avg_track_duration, 6),
            "frame_cover_ratio_1819": round(frame_cover, 6),
            "noise_fp_count_1816": noise_fp,
            "botsort_recall_ratio_vs_baseline": botsort_ratio,
            "hota_proxy_1819": round(hota_proxy, 6),
            "idf1_proxy_1819": round(idf1_proxy, 6),
        },
        "failure_modes": {
            "occlusion": {"risk": occlusion_risk},
            "fast_motion": {"risk": fast_motion_risk},
            "night_noise": {"risk": night_noise_risk},
        },
        "mitigation": recommendations,
        "gates": gates,
        "ok": True if skip_smoke_gates else all(bool(v) for v in gates.values()),
    }


def build_markdown_summary(report: dict[str, Any]) -> str:
    modes = (
        report.get("failure_modes")
        if isinstance(report.get("failure_modes"), dict)
        else {}
    )
    lines = [
        "## Failure Modes & Mitigation",
        "",
        f"- `ok`: **{bool(report.get('ok'))}**",
        (
            "- `occlusion risk`: "
            f"**{((modes.get('occlusion') or {}).get('risk') or 'unknown')}**"
        ),
        (
            "- `fast_motion risk`: "
            f"**{((modes.get('fast_motion') or {}).get('risk') or 'unknown')}**"
        ),
        (
            "- `night_noise risk`: "
            f"**{((modes.get('night_noise') or {}).get('risk') or 'unknown')}**"
        ),
        "",
    ]
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-sota-report", required=True)
    parser.add_argument("--benchmark-trackers-ab-report", required=True)
    parser.add_argument("--track-quality-core-report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_track_failure_modes_report(
        benchmark_sota_report=_load_json(args.benchmark_sota_report),
        benchmark_trackers_ab_report=_load_json(
            args.benchmark_trackers_ab_report
        ),
        track_quality_core_metrics_report=_load_json(
            args.track_quality_core_report
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
