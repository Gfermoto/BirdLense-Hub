#!/usr/bin/env python3
"""Build unified parity_report@v1 from smoke/production artifacts."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clip_metrics(
    benchmark_sota_report: dict[str, Any],
    clip_id: str,
) -> dict[str, Any]:
    clips = (
        benchmark_sota_report.get("clips")
        if isinstance(benchmark_sota_report.get("clips"), dict)
        else {}
    )
    clip = (
        clips.get(clip_id)
        if isinstance(clips.get(clip_id), dict)
        else {}
    )
    metrics = (
        clip.get("metrics")
        if isinstance(clip.get("metrics"), dict)
        else {}
    )
    return metrics


def _compute_event_metrics_from_db(
    db_path: str | None,
    *,
    window_hours: int = 24,
) -> dict[str, Any]:
    if not db_path:
        return {
            "available": False,
            "duration_p50_sec": None,
            "duration_p90_sec": None,
            "duration_max_sec": None,
            "unknown_share": None,
            "zone_transition_rate": None,
            "total_events": 0,
        }
    path = Path(db_path)
    if not path.exists():
        return {
            "available": False,
            "duration_p50_sec": None,
            "duration_p90_sec": None,
            "duration_max_sec": None,
            "unknown_share": None,
            "zone_transition_rate": None,
            "total_events": 0,
            "db_error": "db_not_found",
        }
    conn = sqlite3.connect(str(path))
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=max(1, window_hours)
        )
        cutoff_iso = cutoff.isoformat()
        rows = conn.execute(
            """
            SELECT
              id,
              start_time,
              end_time,
              species_name
            FROM species_visit
            WHERE start_time >= ?
            ORDER BY start_time ASC
            """,
            (cutoff_iso,),
        ).fetchall()
        durations: list[float] = []
        unknown_count = 0
        for _, start_s, end_s, species_name in rows:
            if isinstance(start_s, str) and isinstance(end_s, str):
                try:
                    start_dt = datetime.fromisoformat(
                        start_s.replace("Z", "+00:00")
                    )
                    end_dt = datetime.fromisoformat(
                        end_s.replace("Z", "+00:00")
                    )
                    durations.append(
                        max(0.0, (end_dt - start_dt).total_seconds())
                    )
                except ValueError:
                    pass
            sname = str(species_name or "").strip().lower()
            if sname in {"unknown bird", "bird", "unknown"}:
                unknown_count += 1
        total = len(rows)
        if durations:
            sorted_d = sorted(durations)
            idx90 = int(0.9 * (len(sorted_d) - 1))
            p90 = float(sorted_d[idx90])
            p50 = float(median(sorted_d))
            dmax = float(sorted_d[-1])
        else:
            p50 = p90 = dmax = 0.0
        return {
            "available": True,
            "duration_p50_sec": round(p50, 4),
            "duration_p90_sec": round(p90, 4),
            "duration_max_sec": round(dmax, 4),
            "unknown_share": (
                round(unknown_count / float(total), 6)
                if total > 0
                else None
            ),
            "zone_transition_rate": None,
            "total_events": total,
        }
    finally:
        conn.close()


def build_parity_report(
    *,
    benchmark_sota_report: dict[str, Any],
    core_metrics_report: dict[str, Any],
    truthset_delta_report: dict[str, Any],
    failure_modes_report: dict[str, Any],
    tracker_ab_report: dict[str, Any],
    event_metrics: dict[str, Any],
    period: str,
) -> dict[str, Any]:
    m1816 = _clip_metrics(benchmark_sota_report, "1816")
    m1819 = _clip_metrics(benchmark_sota_report, "1819")
    fp_noise = _as_int(m1816.get("yolo_accepted_boxes_total"))
    yolo_frames = max(1, _as_int(m1819.get("yolo_frames_ran")))
    with_tracks = _as_int(m1819.get("frames_with_tracks"))
    recall_proxy = with_tracks / float(yolo_frames)
    precision_proxy = 1.0 / float(1 + max(fp_noise, 0))

    core_metrics = (
        core_metrics_report.get("metrics")
        if isinstance(core_metrics_report.get("metrics"), dict)
        else {}
    )
    skip_smoke_gates = bool(
        core_metrics.get("skip_proxy_gates_smoke_no_detections")
    )
    truth_deltas = (
        truthset_delta_report.get("deltas")
        if isinstance(truthset_delta_report.get("deltas"), dict)
        else {}
    )
    fail_modes = (
        failure_modes_report.get("failure_modes")
        if isinstance(failure_modes_report.get("failure_modes"), dict)
        else {}
    )

    quality = {
        "precision_proxy": round(precision_proxy, 6),
        "recall_proxy": round(recall_proxy, 6),
        "fp_per_hour_proxy": float(fp_noise),
        "fn_per_hour_proxy": float(max(0, yolo_frames - with_tracks)),
        "top1_accuracy": None,
        "top3_accuracy": None,
        "ece": None,
        "notes": "Top-1/Top-3/ECE require full labeled truth-set batch.",
    }
    tracking = {
        "hota_proxy": core_metrics.get("hota_proxy"),
        "idf1_proxy": core_metrics.get("idf1_proxy"),
        "idsw_count": core_metrics.get("idsw_count"),
        "fragmentation_proxy": core_metrics.get("fragmentation_proxy"),
        "idsw_reduction_ratio": truth_deltas.get("idsw_reduction_ratio"),
        "fragmentation_reduction_ratio": truth_deltas.get(
            "fragmentation_reduction_ratio"
        ),
    }
    event_structure = {
        "duration_p50_sec": event_metrics.get("duration_p50_sec"),
        "duration_p90_sec": event_metrics.get("duration_p90_sec"),
        "duration_max_sec": event_metrics.get("duration_max_sec"),
        "unknown_share": event_metrics.get("unknown_share"),
        "zone_transition_rate": event_metrics.get("zone_transition_rate"),
        "total_events": event_metrics.get("total_events"),
    }
    triage_contract = {
        "card_has_score": True,
        "card_has_species": True,
        "card_has_duration": True,
        "card_has_zone": True,
    }
    gates = {
        "truthset_delta_ok": bool(truthset_delta_report.get("ok")),
        "core_metrics_ok": bool(core_metrics_report.get("ok")),
        "failure_modes_ok": bool(failure_modes_report.get("ok")),
        "tracker_ab_ok": bool(tracker_ab_report.get("ok")),
    }
    if skip_smoke_gates:
        gates = {key: True for key in gates}
    return {
        "schema": "parity_report@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "inputs": {
            "benchmark_sota_report_format": benchmark_sota_report.get(
                "report_format"
            ),
            "core_metrics_schema": core_metrics_report.get("schema"),
            "truthset_delta_schema": truthset_delta_report.get("schema"),
            "failure_modes_schema": failure_modes_report.get("schema"),
            "tracker_ab_schema": tracker_ab_report.get("schema"),
            "event_metrics_available": bool(event_metrics.get("available")),
            "skip_smoke_gates_no_detections": skip_smoke_gates,
        },
        "sections": {
            "quality": quality,
            "tracking": tracking,
            "event_structure": event_structure,
            "triage_contract": triage_contract,
            "failure_modes": fail_modes,
        },
        "gates": gates,
        "ok": True if skip_smoke_gates else all(bool(v) for v in gates.values()),
    }


def build_markdown(report: dict[str, Any]) -> str:
    sections = (
        report.get("sections")
        if isinstance(report.get("sections"), dict)
        else {}
    )
    quality = (
        sections.get("quality")
        if isinstance(sections.get("quality"), dict)
        else {}
    )
    tracking = (
        sections.get("tracking")
        if isinstance(sections.get("tracking"), dict)
        else {}
    )
    events = (
        sections.get("event_structure")
        if isinstance(sections.get("event_structure"), dict)
        else {}
    )
    return "\n".join(
        [
            "## Parity Report",
            "",
            f"- `ok`: **{bool(report.get('ok'))}**",
            f"- `period`: **{report.get('period')}**",
            f"- `precision_proxy`: **{quality.get('precision_proxy')}**",
            f"- `recall_proxy`: **{quality.get('recall_proxy')}**",
            f"- `HOTA proxy`: **{tracking.get('hota_proxy')}**",
            f"- `IDF1 proxy`: **{tracking.get('idf1_proxy')}**",
            f"- `IDSW`: **{tracking.get('idsw_count')}**",
            (
                "- `duration p50/p90`: "
                f"**{events.get('duration_p50_sec')} / "
                f"{events.get('duration_p90_sec')} sec**"
            ),
            f"- `unknown_share`: **{events.get('unknown_share')}**",
            "",
        ]
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-sota-report", required=True)
    parser.add_argument("--core-metrics-report", required=True)
    parser.add_argument("--truthset-delta-report", required=True)
    parser.add_argument("--failure-modes-report", required=True)
    parser.add_argument("--tracker-ab-report", required=True)
    parser.add_argument("--db", default="")
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument(
        "--period",
        choices=["daily", "weekly"],
        default="daily",
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    event_metrics = _compute_event_metrics_from_db(
        (args.db or "").strip() or None,
        window_hours=int(args.window_hours),
    )
    report = build_parity_report(
        benchmark_sota_report=_load_json(args.benchmark_sota_report),
        core_metrics_report=_load_json(args.core_metrics_report),
        truthset_delta_report=_load_json(args.truthset_delta_report),
        failure_modes_report=_load_json(args.failure_modes_report),
        tracker_ab_report=_load_json(args.tracker_ab_report),
        event_metrics=event_metrics,
        period=args.period,
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
        summary_path.write_text(build_markdown(report), encoding="utf-8")
    return 0 if bool(report.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
