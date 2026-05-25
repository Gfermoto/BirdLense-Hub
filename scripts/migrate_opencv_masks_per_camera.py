#!/usr/bin/env python3
"""Migrate OpenCV masks to video.cameras[].opencv_masks; clear global triggers.opencv.masks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)


def _polygons_to_mask_strings(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for poly in raw:
        if not isinstance(poly, list) or len(poly) < 3:
            continue
        pts: list[str] = []
        for p in poly:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                continue
            try:
                x = max(0.0, min(1.0, float(p[0])))
                y = max(0.0, min(1.0, float(p[1])))
            except (TypeError, ValueError):
                continue
            pts.append(f"{round(x, 4)},{round(y, 4)}")
        if len(pts) >= 3:
            out.append(",".join(pts))
    return out


def _mask_specs_from_raw(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            coords = str(item.get("coordinates") or "").strip()
            if coords:
                out.append(coords)
    return out


def migrate_user_config(data: dict) -> list[str]:
    notes: list[str] = []
    video = data.setdefault("video", {})
    if not isinstance(video, dict):
        video = {}
        data["video"] = video
    cameras = video.get("cameras")
    if not isinstance(cameras, list):
        cameras = []
        video["cameras"] = cameras

    for cam in cameras:
        if not isinstance(cam, dict):
            continue
        cid = str(cam.get("id") or cam.get("stream_name") or "?")
        if cam.get("opencv_masks"):
            continue
        wrong = cam.get("detection_ignore_masks")
        converted = _polygons_to_mask_strings(wrong)
        if converted:
            cam["opencv_masks"] = converted
            cam.pop("detection_ignore_masks", None)
            notes.append(f"{cid}: detection_ignore_masks -> opencv_masks ({len(converted)})")

    triggers = data.setdefault("triggers", {})
    if not isinstance(triggers, dict):
        triggers = {}
        data["triggers"] = triggers
    opencv = triggers.setdefault("opencv", {})
    if not isinstance(opencv, dict):
        opencv = {}
        triggers["opencv"] = opencv
    global_masks = _mask_specs_from_raw(opencv.get("masks"))
    if not global_masks:
        return notes

    empty = [
        c
        for c in cameras
        if isinstance(c, dict) and not _mask_specs_from_raw(c.get("opencv_masks"))
    ]
    if len(empty) == 1:
        empty[0]["opencv_masks"] = list(global_masks)
        notes.append(
            f"{empty[0].get('id') or '?'}: triggers.opencv.masks -> opencv_masks",
        )
    elif len(empty) > 1:
        first = empty[0]
        first_id = str(first.get("id") or first.get("stream_name") or "?")
        first["opencv_masks"] = list(global_masks)
        notes.append(
            f"{first_id}: global masks (only first of {len(empty)} cameras; "
            "configure others in Live Editor)",
        )
    opencv["masks"] = []
    notes.append("cleared triggers.opencv.masks (global deprecated)")

    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="user_config.yaml path (default: app/app_config/user_config.yaml)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cfg_path = args.config or (root / "app" / "app_config" / "user_config.yaml")
    if not cfg_path.is_file():
        cfg_path = Path("/app/app_config/user_config.yaml")
    if not cfg_path.is_file():
        print(f"missing {cfg_path}", file=sys.stderr)
        return 1

    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    notes = migrate_user_config(data)
    if not notes:
        print(f"no changes needed ({cfg_path})")
        return 0
    print(f"migration plan ({cfg_path}):")
    for line in notes:
        print(f"  - {line}")
    if args.dry_run:
        return 0
    cfg_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"written {cfg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
