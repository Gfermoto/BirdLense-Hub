#!/usr/bin/env python3
"""Merge multiple behavior_tracklet_manifest@v1 files with split assignment."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ml_behavior_eval_harness import assign_splits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--holdout-ratio", type=float, default=0.2)
    args = ap.parse_args()

    merged = []
    for inp in args.inputs:
        payload = json.loads(Path(inp).read_text(encoding="utf-8"))
        merged.extend(payload.get("tracklets") or [])

    out = {
        "schema": "behavior_tracklet_manifest@v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "merged",
        "tracklet_count": len(merged),
        "label_counts": dict(Counter(str(r.get("label") or "unlabeled") for r in merged if isinstance(r, dict))),
        "tracklets": merged,
    }
    out = assign_splits(out, holdout_ratio=float(args.holdout_ratio))
    outp = Path(args.out).expanduser().resolve()
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(outp), "tracklet_count": out["tracklet_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
