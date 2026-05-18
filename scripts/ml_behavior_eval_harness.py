#!/usr/bin/env python3
"""Train/holdout split and classification metrics for Behavior v2 (#457)."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def deterministic_split(tracklet_id: str, *, holdout_ratio: float = 0.2) -> str:
    h = hashlib.sha256(tracklet_id.encode("utf-8")).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF
    return "holdout" if bucket < float(holdout_ratio) else "train"


def assign_splits(manifest: dict[str, Any], *, holdout_ratio: float = 0.2) -> dict[str, Any]:
    rows = [r for r in (manifest.get("tracklets") or []) if isinstance(r, dict)]
    for row in rows:
        if str(row.get("split") or "").strip() in {"train", "holdout", "val", "test"}:
            continue
        row["split"] = deterministic_split(str(row.get("tracklet_id") or ""), holdout_ratio=holdout_ratio)
    manifest["tracklets"] = rows
    manifest["split_counts"] = dict(Counter(str(r.get("split") or "train") for r in rows))
    return manifest


def confusion_matrix(labels: list[str], y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    idx = {lab: i for i, lab in enumerate(labels)}
    mat = [[0 for _ in labels] for _ in labels]
    for t, p in zip(y_true, y_pred, strict=True):
        if t not in idx or p not in idx:
            continue
        mat[idx[t]][idx[p]] += 1
    return {"labels": labels, "matrix": mat}


def macro_f1_from_confusion(labels: list[str], matrix: list[list[int]]) -> float:
    f1s: list[float] = []
    for i, lab in enumerate(labels):
        tp = matrix[i][i]
        fp = sum(matrix[r][i] for r in range(len(labels)) if r != i)
        fn = sum(matrix[i][c] for c in range(len(labels)) if c != i)
        if tp == 0 and fp == 0 and fn == 0:
            continue
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        f1s.append(f1)
    return float(np.mean(f1s)) if f1s else 0.0


def evaluate_predictions(
    *,
    labels: list[str],
    y_true: list[str],
    y_pred: list[str],
) -> dict[str, Any]:
    correct = sum(1 for a, b in zip(y_true, y_pred, strict=True) if a == b)
    n = len(y_true)
    cm = confusion_matrix(labels, y_true, y_pred)
    macro_f1 = macro_f1_from_confusion(labels, cm["matrix"])
    return {
        "accuracy": round(correct / n, 6) if n else 0.0,
        "macro_f1": round(macro_f1, 6),
        "n_samples": n,
        "confusion": cm,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--predictions", help="JSON list {tracklet_id, label, predicted}")
    ap.add_argument("--holdout-ratio", type=float, default=0.2)
    ap.add_argument("--assign-splits-only", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    manifest = assign_splits(manifest, holdout_ratio=float(args.holdout_ratio))
    out_path = Path(args.out).expanduser().resolve()

    if args.assign_splits_only:
        out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "out": str(out_path), "split_counts": manifest.get("split_counts")}))
        return 0

    if not args.predictions:
        raise SystemExit("--predictions required unless --assign-splits-only")
    preds = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    by_id = {str(p["tracklet_id"]): str(p["predicted"]) for p in preds if isinstance(p, dict)}

    holdout = [
        r
        for r in manifest.get("tracklets") or []
        if isinstance(r, dict) and str(r.get("split")) == "holdout" and str(r.get("label") or "").strip()
    ]
    labels = sorted({str(r.get("label")) for r in holdout})
    y_true: list[str] = []
    y_pred: list[str] = []
    for row in holdout:
        tid = str(row.get("tracklet_id"))
        if tid not in by_id:
            continue
        y_true.append(str(row.get("label")))
        y_pred.append(by_id[tid])

    metrics = evaluate_predictions(labels=labels, y_true=y_true, y_pred=y_pred)
    report = {
        "schema": "behavior_eval_report@v1",
        "created_at": _utc_now(),
        "holdout_ratio": float(args.holdout_ratio),
        "metrics": metrics,
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out_path), "metrics": metrics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
