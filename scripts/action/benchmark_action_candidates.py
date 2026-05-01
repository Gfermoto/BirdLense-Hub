#!/usr/bin/env python3
# flake8: noqa
"""Benchmark action-model candidate predictions against labeled events."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Event:
    video_id: int
    label: str
    time_sec: float
    model_id: str


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        obj = json.loads(ln)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _time_sec(row: dict[str, Any]) -> float | None:
    if row.get("time_offset") is not None:
        try:
            return float(row["time_offset"])
        except Exception:
            return None
    if row.get("time_ms") is not None:
        try:
            return float(row["time_ms"]) / 1000.0
        except Exception:
            return None
    if row.get("t_start_ms") is not None and row.get("t_end_ms") is not None:
        try:
            a = float(row["t_start_ms"]) / 1000.0
            b = float(row["t_end_ms"]) / 1000.0
            return (a + b) / 2.0
        except Exception:
            return None
    return None


def _normalize_rows(rows: list[dict[str, Any]], *, default_model_id: str) -> list[Event]:
    out: list[Event] = []
    for row in rows:
        try:
            video_id = int(row.get("video_id"))
        except Exception:
            continue
        label = str(row.get("action_label") or row.get("label") or "").strip()
        if not label:
            continue
        ts = _time_sec(row)
        if ts is None or ts < 0.0:
            continue
        model_id = str(row.get("model_id") or default_model_id).strip() or default_model_id
        out.append(Event(video_id=video_id, label=label, time_sec=float(ts), model_id=model_id))
    return out


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    xs = sorted(float(v) for v in values)
    idx = int(math.ceil(0.95 * len(xs))) - 1
    idx = max(0, min(idx, len(xs) - 1))
    return xs[idx]


def _match_key(video_id: int, label: str) -> tuple[int, str]:
    return int(video_id), str(label)


def benchmark_candidates(
    *,
    ground_truth_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    tolerance_sec: float,
) -> dict[str, Any]:
    gt_events = _normalize_rows(ground_truth_rows, default_model_id="ground_truth")
    pred_events = _normalize_rows(prediction_rows, default_model_id="unknown_model")

    gt_by_key: dict[tuple[int, str], list[Event]] = defaultdict(list)
    for ev in gt_events:
        gt_by_key[_match_key(ev.video_id, ev.label)].append(ev)
    for key in list(gt_by_key.keys()):
        gt_by_key[key].sort(key=lambda e: e.time_sec)

    pred_by_model: dict[str, list[Event]] = defaultdict(list)
    for ev in pred_events:
        pred_by_model[ev.model_id].append(ev)

    reports: list[dict[str, Any]] = []
    for model_id, model_events in sorted(pred_by_model.items()):
        pred_by_key: dict[tuple[int, str], list[Event]] = defaultdict(list)
        per_video_max_t: dict[int, float] = defaultdict(float)
        for ev in model_events:
            pred_by_key[_match_key(ev.video_id, ev.label)].append(ev)
            per_video_max_t[ev.video_id] = max(per_video_max_t[ev.video_id], ev.time_sec)
        for key in list(pred_by_key.keys()):
            pred_by_key[key].sort(key=lambda e: e.time_sec)

        for ev in gt_events:
            per_video_max_t[ev.video_id] = max(per_video_max_t[ev.video_id], ev.time_sec)

        tp = 0
        fp = 0
        fn = 0
        delays: list[float] = []
        per_label = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

        all_keys = set(gt_by_key.keys()) | set(pred_by_key.keys())
        for key in sorted(all_keys):
            gt_list = gt_by_key.get(key, [])
            pred_list = pred_by_key.get(key, [])
            used_pred = [False] * len(pred_list)

            for gt in gt_list:
                best_i = -1
                best_d = None
                for i, pred in enumerate(pred_list):
                    if used_pred[i]:
                        continue
                    d = abs(pred.time_sec - gt.time_sec)
                    if d <= float(tolerance_sec) and (best_d is None or d < best_d):
                        best_d = d
                        best_i = i
                if best_i >= 0:
                    used_pred[best_i] = True
                    tp += 1
                    per_label[key[1]]["tp"] += 1
                    delays.append(float(best_d or 0.0))
                else:
                    fn += 1
                    per_label[key[1]]["fn"] += 1

            for i, _pred in enumerate(pred_list):
                if not used_pred[i]:
                    fp += 1
                    per_label[key[1]]["fp"] += 1

        precision = float(tp) / float(tp + fp) if (tp + fp) > 0 else 0.0
        recall = float(tp) / float(tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        duration_h = sum(max(v, 1.0) for v in per_video_max_t.values()) / 3600.0
        fp_per_hour = float(fp) / duration_h if duration_h > 0 else None

        reports.append(
            {
                "model_id": model_id,
                "events_predicted": len(model_events),
                "events_ground_truth": len(gt_events),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": round(precision, 6),
                "recall": round(recall, 6),
                "f1": round(f1, 6),
                "boundary_delay_p95_sec": _p95(delays),
                "fp_per_hour": None if fp_per_hour is None else round(fp_per_hour, 6),
                "tolerance_sec": float(tolerance_sec),
                "per_label": dict(per_label),
            }
        )

    reports.sort(key=lambda r: (r["f1"], r["recall"], -r["fp"]), reverse=True)
    return {
        "schema": "action_candidate_benchmark@v1",
        "ground_truth_count": len(gt_events),
        "prediction_count": len(pred_events),
        "models": reports,
        "best_model_id": reports[0]["model_id"] if reports else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-jsonl", required=True)
    parser.add_argument("--predictions-jsonl", required=True)
    parser.add_argument("--tolerance-sec", type=float, default=1.5)
    parser.add_argument("--output-json", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = benchmark_candidates(
        ground_truth_rows=_read_jsonl(Path(args.ground_truth_jsonl).resolve()),
        prediction_rows=_read_jsonl(Path(args.predictions_jsonl).resolve()),
        tolerance_sec=float(args.tolerance_sec),
    )
    if args.output_json:
        out = Path(args.output_json).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
