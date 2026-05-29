#!/usr/bin/env python3
"""Freeze truth-set splits (day/night/weather) from clip metadata JSON."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected: {path}")
    return payload


def _norm_bucket(text: Any, *, default: str) -> str:
    v = str(text or "").strip().lower()
    return v if v else default


def freeze_truthset_splits(
    *,
    clips: list[dict[str, Any]],
    seed: int = 42,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    min_clips: int = 300,
) -> dict[str, Any]:
    total = len(clips)
    coverage = {
        "day_night": Counter(),
        "weather": Counter(),
    }
    rows: list[dict[str, Any]] = []
    for clip in clips:
        cid = str(clip.get("clip_id") or "").strip()
        if not cid:
            continue
        day_night = _norm_bucket(clip.get("day_night"), default="unknown")
        weather = _norm_bucket(clip.get("weather"), default="unknown")
        coverage["day_night"][day_night] += 1
        coverage["weather"][weather] += 1
        rows.append(
            {
                "clip_id": cid,
                "day_night": day_night,
                "weather": weather,
            }
        )

    rng = random.Random(int(seed))
    rng.shuffle(rows)
    n = len(rows)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    if n_train + n_val > n:
        n_val = max(0, n - n_train)
    n_test = n - n_train - n_val
    split_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if idx < n_train:
            split = "train"
        elif idx < n_train + n_val:
            split = "val"
        else:
            split = "test"
        split_rows.append({**row, "split": split})
    coverage_ok = (
        coverage["day_night"].get("day", 0) > 0
        and coverage["day_night"].get("night", 0) > 0
        and (
            coverage["weather"].get("rain", 0) > 0
            or coverage["weather"].get("rainy", 0) > 0
        )
    )
    gates = {
        "min_clips_ok": bool(n >= int(min_clips)),
        "coverage_day_night_weather_ok": bool(coverage_ok),
        "non_empty_splits_ok": bool(n_train > 0 and n_val > 0 and n_test > 0),
    }
    return {
        "schema": "truthset_splits@v1",
        "seed": int(seed),
        "counts": {
            "clips_total": n,
            "train": n_train,
            "val": n_val,
            "test": n_test,
        },
        "coverage": {
            "day_night": dict(coverage["day_night"]),
            "weather": dict(coverage["weather"]),
        },
        "rows": split_rows,
        "gates": gates,
        "ok": all(bool(v) for v in gates.values()),
        "notes": {
            "min_clips_required": int(min_clips),
            "source_rows_total": int(total),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        help="JSON with {clips:[...]}",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--min-clips", type=int, default=300)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = _load_json(args.input)
    clips = (
        payload.get("clips")
        if isinstance(payload.get("clips"), list)
        else []
    )
    clips_rows = [r for r in clips if isinstance(r, dict)]
    report = freeze_truthset_splits(
        clips=clips_rows,
        seed=int(args.seed),
        train_ratio=float(args.train_ratio),
        val_ratio=float(args.val_ratio),
        min_clips=int(args.min_clips),
    )
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if bool(report.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
