#!/usr/bin/env python3
"""Build int8_candidate_eval@v1 from baseline/candidate benchmark reports (#415)."""

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


def _mean_runtime_seconds(report: dict[str, Any]) -> float | None:
    rows = report.get("videos")
    if not isinstance(rows, list) or not rows:
        return None
    vals = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            vals.append(float(row.get("runtime_seconds") or 0.0))
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def _label_eval_kpi(report: dict[str, Any]) -> tuple[float | None, int]:
    rows = report.get("videos")
    if not isinstance(rows, list):
        return None, 0
    matched = 0
    gold = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        le = row.get("label_eval")
        if not isinstance(le, dict) or bool(le.get("skipped")):
            continue
        matched += int(le.get("matched") or 0)
        gold += int(le.get("gold_count") or 0)
    if gold <= 0:
        return None, 0
    return float(matched) / float(gold), int(gold)


def build_int8_candidate_eval_report(
    *,
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
    continuity_report: dict[str, Any] | None,
    min_latency_improvement_ratio: float = 0.20,
    max_quality_drop_pp: float = 1.0,
) -> dict[str, Any]:
    base_runtime = _mean_runtime_seconds(baseline_report)
    cand_runtime = _mean_runtime_seconds(candidate_report)
    base_kpi, sample_count = _label_eval_kpi(baseline_report)
    cand_kpi, _ = _label_eval_kpi(candidate_report)
    latency_improvement = None
    if base_runtime and base_runtime > 0 and cand_runtime is not None:
        latency_improvement = (base_runtime - cand_runtime) / base_runtime
    quality_drop_pp = None
    if base_kpi is not None and cand_kpi is not None:
        quality_drop_pp = (base_kpi - cand_kpi) * 100.0
    cont_ok = True
    if continuity_report is not None:
        cont_metrics = continuity_report.get("metrics") if isinstance(continuity_report.get("metrics"), dict) else {}
        cont_ok = bool(cont_metrics.get("track_gate_ok")) and bool(cont_metrics.get("crop_gate_ok"))
    gates = {
        "latency_improvement_ok": bool(
            latency_improvement is not None and latency_improvement >= float(min_latency_improvement_ratio)
        ),
        "quality_drop_ok": bool(
            quality_drop_pp is None or quality_drop_pp <= (float(max_quality_drop_pp) + 1e-9)
        ),
        "continuity_ok": bool(cont_ok),
    }
    rollback = {
        "steps": [
            "Set processor.inference_backend=torch (or previous stable backend) in user_config.yaml.",
            "Restore previous detector artifact (best.pt / OpenVINO bundle) from backup path.",
            "Restart processor and re-run detector_continuity_report + offline gate.",
        ],
        "trigger": "Any gate failure in int8_candidate_eval@v1 or continuity regression alerts.",
    }
    return {
        "schema": "int8_candidate_eval@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": {
            "min_latency_improvement_ratio": float(min_latency_improvement_ratio),
            "max_quality_drop_pp": float(max_quality_drop_pp),
        },
        "metrics": {
            "baseline_runtime_mean_s": (None if base_runtime is None else round(base_runtime, 6)),
            "candidate_runtime_mean_s": (None if cand_runtime is None else round(cand_runtime, 6)),
            "latency_improvement_ratio": (None if latency_improvement is None else round(latency_improvement, 6)),
            "baseline_quality_kpi": (None if base_kpi is None else round(base_kpi, 6)),
            "candidate_quality_kpi": (None if cand_kpi is None else round(cand_kpi, 6)),
            "quality_drop_pp": (None if quality_drop_pp is None else round(quality_drop_pp, 6)),
            "quality_sample_count": int(sample_count),
        },
        "gates": gates,
        "rollback_instructions": rollback,
        "go_no_go": "go" if all(bool(v) for v in gates.values()) else "no_go",
        "ok": all(bool(v) for v in gates.values()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-report", required=True, help="Path to baseline benchmark_track_regen@v1 report.")
    parser.add_argument("--candidate-report", required=True, help="Path to candidate benchmark_track_regen@v1 report.")
    parser.add_argument("--continuity-report", default="", help="Optional detector_continuity_report@v1 path.")
    parser.add_argument("--min-latency-improvement-ratio", type=float, default=0.20)
    parser.add_argument("--max-quality-drop-pp", type=float, default=1.0)
    parser.add_argument("--out", required=True, help="Output int8_candidate_eval@v1 JSON path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    baseline = _load_json(args.baseline_report)
    candidate = _load_json(args.candidate_report)
    continuity = _load_json(args.continuity_report) if (args.continuity_report or "").strip() else None
    out = build_int8_candidate_eval_report(
        baseline_report=baseline,
        candidate_report=candidate,
        continuity_report=continuity,
        min_latency_improvement_ratio=float(args.min_latency_improvement_ratio),
        max_quality_drop_pp=float(args.max_quality_drop_pp),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(out.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
