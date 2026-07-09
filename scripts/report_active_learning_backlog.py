#!/usr/bin/env python3
"""Build active_learning_backlog@v1 from quality reports."""

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


def _f(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _i(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_backlog_report(
    *,
    track_regression_report: dict[str, Any],
    species_calibration_report: dict[str, Any],
    truthset_delta_report: dict[str, Any],
    min_priority: int = 2,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    metrics = (
        track_regression_report.get("metrics")
        if isinstance(track_regression_report.get("metrics"), dict)
        else {}
    )
    parity_rate = _f(metrics.get("parity_mismatch_rate_24h"))
    idsw_rate = _f(metrics.get("track_id_switch_rate_24h"))
    if parity_rate >= 0.2:
        items.append(
            {
                "id": "fp_fn_weekly_mining",
                "priority": 3,
                "reason": "parity_mismatch_rate_24h",
                "value": round(parity_rate, 6),
                "action": "mine_fp_fn_from_recent_sessions",
            }
        )
    if idsw_rate >= 0.05:
        items.append(
            {
                "id": "id_switch_mining",
                "priority": 3,
                "reason": "track_id_switch_rate_24h",
                "value": round(idsw_rate, 6),
                "action": "collect_id_switch_hard_cases",
            }
        )

    topk = (
        species_calibration_report.get("topk_metrics")
        if isinstance(species_calibration_report.get("topk_metrics"), dict)
        else {}
    )
    unknown = (
        species_calibration_report.get("unknown_ood_dashboard")
        if isinstance(
            species_calibration_report.get("unknown_ood_dashboard"),
            dict,
        )
        else {}
    )
    unknown_policy = (
        unknown.get("unknown_policy")
        if isinstance(unknown.get("unknown_policy"), dict)
        else {}
    )
    false_species_rate = _f(topk.get("false_species_rate_before"))
    unknown_share = _f(unknown_policy.get("unknown_share_after_policy"))
    if false_species_rate >= 0.3:
        items.append(
            {
                "id": "species_mismatch_mining",
                "priority": 3,
                "reason": "false_species_rate_before",
                "value": round(false_species_rate, 6),
                "action": "curate_species_mismatch_subset",
            }
        )
    if unknown_share >= 0.25:
        items.append(
            {
                "id": "unknown_spike_mining",
                "priority": 2,
                "reason": "unknown_share_after_policy",
                "value": round(unknown_share, 6),
                "action": "review_unknown_spikes_and_hard_negatives",
            }
        )

    pairs = (
        species_calibration_report.get("top_confusion_pairs")
        if isinstance(
            species_calibration_report.get("top_confusion_pairs"),
            list,
        )
        else []
    )
    pair_rows = [r for r in pairs if isinstance(r, dict)]
    if pair_rows:
        top = pair_rows[0]
        items.append(
            {
                "id": "negative_flip_targeting",
                "priority": 3,
                "reason": "top_confusion_pair",
                "value": {
                    "from": top.get("from"),
                    "to": top.get("to"),
                    "count": _i(top.get("count")),
                },
                "action": "sample_negative_flip_subset",
            }
        )

    deltas = (
        truthset_delta_report.get("deltas")
        if isinstance(truthset_delta_report.get("deltas"), dict)
        else {}
    )
    idsw_reduction_ratio = _f(deltas.get("idsw_reduction_ratio"))
    if idsw_reduction_ratio < 0:
        items.append(
            {
                "id": "regression_shadow_ab_required",
                "priority": 3,
                "reason": "idsw_reduction_ratio_negative",
                "value": round(idsw_reduction_ratio, 6),
                "action": "run_shadow_ab_before_rollout",
            }
        )

    selected = [i for i in items if _i(i.get("priority")) >= int(min_priority)]
    selected.sort(
        key=lambda x: (_i(x.get("priority")), str(x.get("id"))),
        reverse=True,
    )
    return {
        "schema": "active_learning_backlog@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "track_regression_schema": track_regression_report.get("schema"),
            "species_calibration_schema": (
                species_calibration_report.get("schema")
            ),
            "truthset_delta_schema": truthset_delta_report.get("schema"),
        },
        "items_total": len(selected),
        "items": selected,
        "ok": len(selected) > 0,
    }


def build_markdown(report: dict[str, Any]) -> str:
    items = (
        report.get("items")
        if isinstance(report.get("items"), list)
        else []
    )
    lines = [
        "## Active Learning Backlog",
        "",
        f"- `ok`: **{bool(report.get('ok'))}**",
        f"- `items_total`: **{report.get('items_total')}**",
        "",
    ]
    for item in items:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- "
            f"[P{item.get('priority')}] `{item.get('id')}` "
            f"({item.get('reason')}={item.get('value')}) -> "
            f"{item.get('action')}"
        )
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track-regression-report", required=True)
    parser.add_argument("--species-calibration-report", required=True)
    parser.add_argument("--truthset-delta-report", required=True)
    parser.add_argument("--min-priority", type=int, default=2)
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_backlog_report(
        track_regression_report=_load_json(args.track_regression_report),
        species_calibration_report=_load_json(args.species_calibration_report),
        truthset_delta_report=_load_json(args.truthset_delta_report),
        min_priority=int(args.min_priority),
    )
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.summary_out:
        summary = Path(args.summary_out).expanduser().resolve()
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(build_markdown(report), encoding="utf-8")
    return 0 if bool(report.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
