#!/usr/bin/env python3
"""Convert exported decision_trace JSON to active_learning_pool manifest JSONL (#369).

Reads one JSON object (file or stdin) with persisted_tracks / rejected_tracks,
or a bare list of trace rows. Emits pool_entry lines; crop paths are synthetic
``_pending/<video_id>_<track_id>.jpg`` until a separate export fills files.

Example::

  python3 decision_trace_to_pool_manifest.py trace.json --needs-review-only > pool.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _load_json(fp) -> Any:
    return json.load(fp)


def _iter_rows(obj: Any) -> list[dict]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if not isinstance(obj, dict):
        return []
    pt = obj.get("persisted_tracks") or []
    rt = obj.get("rejected_tracks") or []
    rows = []
    for x in pt + rt:
        if isinstance(x, dict):
            rows.append(x)
    return rows


def _maybe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def row_to_entry(row: dict, video_id: str, *, seed: int, model_version: str) -> dict | None:
    tid = row.get("track_id")
    try:
        tid_i = int(tid)
    except (TypeError, ValueError):
        return None
    ent = _maybe_float(row.get("classifier_entropy"))
    margin = _maybe_float(row.get("classifier_top1_top2_margin"))
    out = {
        "schema": "active_learning_pool_entry@v1",
        "video_id": str(video_id),
        "track_id": tid_i,
        "crop_relative_path": f"_pending/{video_id}_{tid_i}.jpg",
        "detector_conf": float(row.get("detector_confidence") or 0.0),
        "classifier_entropy": float(ent) if ent is not None else 0.0,
        "classifier_margin_top1_minus_top2": float(margin) if margin is not None else 0.0,
        "model_version": model_version,
        "seed": seed,
        "species_hint": row.get("species_name") or row.get("classifier_species_name"),
        "classifier_needs_review": bool(row.get("classifier_needs_review")),
        "decision_kind": row.get("decision_kind"),
        "source_trace": "persisted" if row.get("persisted_to_clip") else "rejected_or_trimmed",
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", nargs="?", help="JSON file (default: stdin)")
    ap.add_argument("--video-id", dest="video_id", default=None, help="Override video_id when missing in trace")
    ap.add_argument("--needs-review-only", action="store_true", help="Only rows with classifier_needs_review")
    ap.add_argument("--entropy-ge", dest="entropy_ge", type=float, default=None)
    ap.add_argument("--margin-le", dest="margin_le", type=float, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model-version", default="pipeline_unknown")
    args = ap.parse_args()
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            obj = _load_json(f)
    else:
        obj = _load_json(sys.stdin)
    vid = args.video_id
    if vid is None and isinstance(obj, dict):
        raw_vid = obj.get("video_id")
        if raw_vid is not None:
            vid = str(raw_vid)
    if vid is None:
        vid = "unknown_video"
    rows = _iter_rows(obj)
    for row in rows:
        if args.needs_review_only and not bool(row.get("classifier_needs_review")):
            continue
        ent = _maybe_float(row.get("classifier_entropy"))
        margin = _maybe_float(row.get("classifier_top1_top2_margin"))
        if args.entropy_ge is not None:
            if ent is None or ent < args.entropy_ge:
                continue
        if args.margin_le is not None:
            if margin is None or margin > args.margin_le:
                continue
        entry = row_to_entry(row, vid, seed=args.seed, model_version=args.model_version)
        if entry is None:
            continue
        sys.stdout.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
