#!/usr/bin/env python3
"""Report ML drift and retrain trigger gate status (#535)."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json object required: {path}")
    return payload


def _parse_ts(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


def _read_observations(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    values = []
    for row in rows:
        try:
            values.append(float(row.get(key)))
        except (TypeError, ValueError):
            continue
    if not values:
        return 0.0
    return float(statistics.mean(values))


def _observation_bounds(
    observations: list[dict[str, Any]],
) -> tuple[str, str]:
    stamps: list[datetime] = []
    for row in observations:
        ts = _parse_ts(row.get("observed_at"))
        if ts is not None:
            stamps.append(ts)
    if not stamps:
        return "", ""
    first = min(stamps).strftime("%Y-%m-%dT%H:%M:%SZ")
    last = max(stamps).strftime("%Y-%m-%dT%H:%M:%SZ")
    return first, last


def evaluate_drift(
    *,
    baseline: dict[str, Any],
    observations: list[dict[str, Any]],
    override_reason: str,
) -> dict[str, Any]:
    base_metrics = baseline.get("metrics") or {}
    thresholds = baseline.get("thresholds") or {}
    min_observations = int(baseline.get("min_observations") or 5)
    metric_keys = (
        "binary_positive_rate",
        "mean_confidence",
        "species_entropy",
    )
    first_observation, last_observation = _observation_bounds(observations)
    aggregates = {key: _mean(observations, key) for key in metric_keys}
    rows: list[dict[str, Any]] = []
    triggered = False
    for key in metric_keys:
        base_value = float(base_metrics.get(key) or 0.0)
        current = float(aggregates.get(key) or 0.0)
        delta = abs(current - base_value)
        threshold = float(thresholds.get(f"{key}_abs_delta") or 0.0)
        drift = bool(delta > threshold) if threshold > 0 else False
        triggered = bool(triggered or drift)
        rows.append(
            {
                "metric": key,
                "baseline": round(base_value, 6),
                "current": round(current, 6),
                "abs_delta": round(delta, 6),
                "threshold": round(threshold, 6),
                "drift": drift,
            }
        )
    enough_data = bool(len(observations) >= min_observations)
    retrain_trigger = bool(enough_data and triggered)
    override_used = bool(override_reason.strip())
    block_release = bool(retrain_trigger and not override_used)
    return {
        "schema": "ml_drift_trigger@v1",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": {
            "observations_total": int(len(observations)),
            "min_observations_required": int(min_observations),
            "enough_data": enough_data,
            "first_observation": first_observation,
            "last_observation": last_observation,
        },
        "metrics": rows,
        "trigger": {
            "retrain_required": retrain_trigger,
            "override_used": override_used,
            "override_reason": override_reason.strip(),
            "block_release": block_release,
            "ok": bool(not block_release),
        },
        "ok": bool(not block_release),
    }


def _to_md(report: dict[str, Any]) -> str:
    window = report.get("window") or {}
    trigger = report.get("trigger") or {}
    lines = [
        "# ML Drift Trigger Report",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- observations_total: `{window.get('observations_total')}`",
        (
            "- min_observations_required: "
            f"`{window.get('min_observations_required')}`"
        ),
        f"- retrain_required: `{trigger.get('retrain_required')}`",
        f"- block_release: `{trigger.get('block_release')}`",
        f"- ok: `{report.get('ok')}`",
        "",
        "## Metric Deltas",
        "",
    ]
    for row in report.get("metrics") or []:
        lines.append(
            (
                f"- `{row.get('metric')}`: baseline={row.get('baseline')} "
                f"current={row.get('current')} "
                f"delta={row.get('abs_delta')} "
                f"threshold={row.get('threshold')} drift={row.get('drift')}"
            )
        )
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        default="docs/reports/ml_drift/ml_drift_baseline.json",
    )
    parser.add_argument(
        "--observations",
        default="docs/reports/ml_drift/ml_observations.jsonl",
    )
    parser.add_argument(
        "--override-reason",
        default="",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/ml_drift/ml_drift_trigger_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/ml_drift/ml_drift_trigger_latest.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    baseline = Path(args.baseline).expanduser()
    if not baseline.is_absolute():
        baseline = REPO / baseline
    observations = Path(args.observations).expanduser()
    if not observations.is_absolute():
        observations = REPO / observations
    report = evaluate_drift(
        baseline=_load_json(baseline),
        observations=_read_observations(observations),
        override_reason=str(args.override_reason or ""),
    )
    out_json = Path(args.out_json).expanduser()
    if not out_json.is_absolute():
        out_json = REPO / out_json
    out_md = Path(args.out_md).expanduser()
    if not out_md.is_absolute():
        out_md = REPO / out_md
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
