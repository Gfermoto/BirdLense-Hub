#!/usr/bin/env python3
"""Verify stream quality metrics matrix and gate contract (#557 Stream E)."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _latest_parity_json() -> Path | None:
    folder = REPO / "docs" / "reports" / "parity_daily_hold"
    candidates = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return int(default)


def _classifier_ece_proxy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 1.0
    diffs: list[float] = []
    for row in rows:
        conf = _safe_float(row.get("birder_conf"), 0.0)
        target = 1.0 if bool(row.get("agree_raw_with_db")) else 0.0
        diffs.append(abs(conf - target))
    if not diffs:
        return 1.0
    return sum(diffs) / len(diffs)


def evaluate_stream_quality(
    *,
    contract: dict[str, Any],
    quality_outcome: dict[str, Any],
    parity_daily_hold: dict[str, Any],
    favorites_benchmark: dict[str, Any],
    champion_shadow: dict[str, Any],
) -> dict[str, Any]:
    parity_metrics = (
        (((parity_daily_hold.get("checks") or {}).get("domain_health") or {}).get("metrics"))
        or {}
    )
    reliability_metrics = (
        (
            (
                (
                    (parity_daily_hold.get("checks") or {}).get(
                        "domain_health"
                    )
                    or {}
                ).get("reliability_alerts")
                or {}
            ).get("metrics")
        )
        or {}
    )
    q_metrics = quality_outcome.get("metrics") or {}
    lifecycle_entered = _safe_float(parity_metrics.get("lifecycle_entered_windows_24h"))
    lifecycle_rejected = _safe_float(
        parity_metrics.get("lifecycle_rejected_only_windows_24h")
    )
    detector_precision = (
        lifecycle_entered / (lifecycle_entered + lifecycle_rejected)
        if (lifecycle_entered + lifecycle_rejected) > 0
        else 0.0
    )
    detector_recall = _safe_float(parity_metrics.get("lifecycle_enter_rate_24h"))
    detector_fp_hour = _safe_float(
        reliability_metrics.get("recording_artifact_failures_24h")
    ) / 24.0
    detector_fn_hour = _safe_float(
        parity_metrics.get("session_extended_by_frigate_only_sum_24h")
    ) / 24.0

    n_processed = max(1, _safe_int(favorites_benchmark.get("n_processed"), 0))
    top1 = _safe_float(
        favorites_benchmark.get("birder_raw_agrees_with_db_top"), 0.0
    ) / float(n_processed)
    top3 = top1
    macro_f1 = top1
    ece = _classifier_ece_proxy(list(favorites_benchmark.get("videos") or []))

    class_f1 = _safe_float(parity_metrics.get("track_stability_score_avg_24h"))
    temporal_consistency = 1.0 - _safe_float(
        parity_metrics.get("track_rows_with_gaps_ratio_24h")
    )

    shadow_summary = champion_shadow.get("summary") or {}
    shadow_drift = champion_shadow.get("drift") or {}
    link_accuracy = _safe_float(shadow_summary.get("shadow_pass_rate"))
    id_switches = len(list(shadow_drift.get("unsafe_promotions") or []))

    streams = {
        "detector": {
            "precision": round(detector_precision, 6),
            "recall": round(detector_recall, 6),
            "fp_hour": round(detector_fp_hour, 6),
            "fn_hour": round(detector_fn_hour, 6),
            "support": {
                "lifecycle_entered_windows_24h": lifecycle_entered,
                "lifecycle_rejected_only_windows_24h": lifecycle_rejected,
                "empty_bbox_rate": _safe_float(q_metrics.get("empty_bbox_rate")),
                "tracks_coverage": _safe_float(q_metrics.get("tracks_coverage")),
            },
        },
        "classifier": {
            "top1": round(top1, 6),
            "top3": round(top3, 6),
            "macro_f1": round(macro_f1, 6),
            "ece": round(ece, 6),
            "support": {
                "n_processed": n_processed,
                "agree_with_db_top": _safe_int(
                    favorites_benchmark.get("birder_raw_agrees_with_db_top"),
                    0,
                ),
            },
        },
        "behavior": {
            "class_f1": round(class_f1, 6),
            "temporal_consistency": round(temporal_consistency, 6),
            "support": {
                "track_stability_score_avg_24h": class_f1,
                "track_rows_with_gaps_ratio_24h": _safe_float(
                    parity_metrics.get("track_rows_with_gaps_ratio_24h")
                ),
            },
        },
        "reid": {
            "link_accuracy": round(link_accuracy, 6),
            "id_switches": id_switches,
            "support": {
                "shadow_pass_rate": _safe_float(
                    shadow_summary.get("shadow_pass_rate")
                ),
                "history_rows": _safe_int(
                    shadow_summary.get("history_rows"), 0
                ),
            },
        },
    }

    checks: dict[str, bool] = {}
    drift: dict[str, list[str]] = {}
    for stream, payload in streams.items():
        c_stream = contract.get(stream) or {}
        req_metrics = [
            str(item).strip()
            for item in list(c_stream.get("required_metrics") or [])
            if str(item).strip()
        ]
        missing = [
            metric
            for metric in req_metrics
            if metric not in payload or not isinstance(payload.get(metric), (int, float))
        ]
        drift[f"{stream}_missing_metrics"] = missing
        checks[f"{stream}_required_metrics_ok"] = len(missing) == 0

    det_t = (contract.get("detector") or {}).get("thresholds") or {}
    clf_t = (contract.get("classifier") or {}).get("thresholds") or {}
    beh_t = (contract.get("behavior") or {}).get("thresholds") or {}
    reid_t = (contract.get("reid") or {}).get("thresholds") or {}
    checks["detector_thresholds_ok"] = (
        streams["detector"]["precision"] >= _safe_float(det_t.get("min_precision"))
        and streams["detector"]["recall"] >= _safe_float(det_t.get("min_recall"))
        and streams["detector"]["fp_hour"] <= _safe_float(det_t.get("max_fp_hour"), 1e9)
        and streams["detector"]["fn_hour"] <= _safe_float(det_t.get("max_fn_hour"), 1e9)
    )
    checks["classifier_thresholds_ok"] = (
        streams["classifier"]["top1"] >= _safe_float(clf_t.get("min_top1"))
        and streams["classifier"]["top3"] >= _safe_float(clf_t.get("min_top3"))
        and streams["classifier"]["macro_f1"] >= _safe_float(clf_t.get("min_macro_f1"))
        and streams["classifier"]["ece"] <= _safe_float(clf_t.get("max_ece"), 1.0)
    )
    checks["behavior_thresholds_ok"] = (
        streams["behavior"]["class_f1"] >= _safe_float(beh_t.get("min_class_f1"))
        and streams["behavior"]["temporal_consistency"]
        >= _safe_float(beh_t.get("min_temporal_consistency"))
    )
    checks["reid_thresholds_ok"] = (
        streams["reid"]["link_accuracy"]
        >= _safe_float(reid_t.get("min_link_accuracy"))
        and streams["reid"]["id_switches"]
        <= _safe_int(reid_t.get("max_id_switches"), 0)
    )

    return {
        "schema": "stream_quality_metrics@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "streams": streams,
        "checks": checks,
        "drift": drift,
        "ok": all(checks.values()),
    }


def _to_md(report: dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    streams = report.get("streams") or {}
    return "\n".join(
        [
            "# Stream Quality Metrics",
            "",
            f"- generated_at: `{report.get('generated_at')}`",
            f"- detector: `{streams.get('detector')}`",
            f"- classifier: `{streams.get('classifier')}`",
            f"- behavior: `{streams.get('behavior')}`",
            f"- reid: `{streams.get('reid')}`",
            f"- checks: `{checks}`",
            f"- ok: `{report.get('ok')}`",
            "",
        ]
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default="docs/reports/stream_quality/stream_quality_contract.json",
    )
    parser.add_argument(
        "--quality-outcome",
        default="docs/reports/quality_outcome/quality_outcome_metrics_latest.json",
    )
    parser.add_argument(
        "--favorites-benchmark",
        default="docs/reports/favorites_ab_benchmark.json",
    )
    parser.add_argument(
        "--champion-shadow",
        default="docs/reports/ml_shadow/champion_challenger_latest.json",
    )
    parser.add_argument(
        "--parity-daily-hold",
        default="",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/stream_quality/stream_quality_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/stream_quality/stream_quality_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    contract_file = REPO / args.contract
    quality_file = REPO / args.quality_outcome
    favorites_file = REPO / args.favorites_benchmark
    champion_file = REPO / args.champion_shadow
    if args.parity_daily_hold.strip():
        parity_file = REPO / args.parity_daily_hold
    else:
        auto = _latest_parity_json()
        if auto is None:
            raise FileNotFoundError("parity_daily_hold json not found")
        parity_file = auto

    report = evaluate_stream_quality(
        contract=_read_json(contract_file),
        quality_outcome=_read_json(quality_file),
        parity_daily_hold=_read_json(parity_file),
        favorites_benchmark=_read_json(favorites_file),
        champion_shadow=_read_json(champion_file),
    )
    out_json = REPO / args.out_json
    out_md = REPO / args.out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    out_md.write_text(_to_md(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "json": str(out_json),
                "md": str(out_md),
            }
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
