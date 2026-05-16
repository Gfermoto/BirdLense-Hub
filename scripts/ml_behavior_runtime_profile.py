#!/usr/bin/env python3
"""Micro-benchmark softmax inference for behavior export (#416 Wave 4 artifact).

Produces ``behavior_runtime_profile@v1`` JSON with wall-clock stats for N forward passes
(same math as ``behavior_baseline_runtime`` in the processor).
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def _softmax(logits: np.ndarray) -> np.ndarray:
    x = logits.astype(np.float64)
    x = x - np.max(x)
    e = np.exp(x)
    return e / (np.sum(e) + 1e-12)


def main() -> int:
    """CLI entry."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--export", required=True, help="behavior_logistic_export@v1.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--iterations", type=int, default=5000)
    ap.add_argument("--batch", type=int, default=1, help="rows per iteration (repeated X)")
    args = ap.parse_args()
    payload = json.loads(Path(args.export).read_text(encoding="utf-8"))
    if str(payload.get("schema") or "") != "behavior_logistic_export@v1":
        raise SystemExit("export schema must be behavior_logistic_export@v1")
    labels = payload["labels"]
    w = np.array(payload["coef"], dtype=np.float64)
    b = np.array(payload["intercept"], dtype=np.float64).reshape(-1)
    n_feat = w.shape[1]
    rng = np.random.default_rng(0)
    iters = max(1, int(args.iterations))
    batch = max(1, int(args.batch))
    times: list[float] = []
    for _ in range(iters):
        x = rng.standard_normal((batch, n_feat))
        t0 = time.perf_counter()
        for i in range(batch):
            row = x[i].reshape(1, -1)
            logits = (row @ w.T).reshape(-1) + b
            _ = _softmax(logits)
        times.append(time.perf_counter() - t0)
    arr = np.array(times, dtype=np.float64)
    report = {
        "schema": "behavior_runtime_profile@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "export_path": str(Path(args.export).resolve()),
            "iterations": iters,
            "batch": batch,
            "n_classes": len(labels),
            "n_features": int(n_feat),
        },
        "wall_seconds": {
            "mean": float(arr.mean()),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
        },
    }
    outp = Path(args.out).expanduser().resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(outp)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
