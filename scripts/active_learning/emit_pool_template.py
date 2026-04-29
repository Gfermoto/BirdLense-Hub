#!/usr/bin/env python3
"""Emit one JSONL template line for active learning manifest (#369)."""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="manifest.jsonl path")
    args = ap.parse_args()
    row = {
        "schema": "active_learning_pool_entry@v1",
        "video_id": "example_video_id",
        "track_id": 0,
        "crop_relative_path": "crops/example_track_0.jpg",
        "detector_conf": 0.0,
        "classifier_entropy": 0.0,
        "classifier_margin_top1_minus_top2": 0.0,
        "model_version": "classifier_semver_or_git_sha",
        "seed": 0,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
