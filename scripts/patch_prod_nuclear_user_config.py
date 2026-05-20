#!/usr/bin/env python3
"""Merge nuclear FP-suppression overrides into app/app_config/user_config.yaml (prod-safe).

Run on VPS inside repo or via:
  docker exec birdlense python3 /app/scripts/patch_prod_nuclear_user_config.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)

NUCLEAR_PROCESSOR = {
    "min_confidence_binary": 0.38,
    "min_confidence_binary_bird": 0.38,
    "openvino_min_confidence_binary_bird": 0.38,
    "openvino_binary_track_ultralytics_conf": 0.28,
    "min_track_duration": 1.0,
    "auto_small_object_relax_enabled": False,
    "yolo_weak_track_salvage_enabled": False,
    "ultra_weak_box_salvage_enabled": False,
    "motion_verified_detection_enabled": True,
    "motion_verified_min_pixel_change": 10,
    "motion_global_max_mean_absdiff": 2.0,
    "motion_strict_consecutive_frames": 3,
    "motion_hard_conf_ceiling": 0.55,
    "static_object_suppression_enabled": True,
    "static_temporal_min_seconds": 5,
    "detection_ignore_masks": [
        [[0.72, 0.55], [0.95, 0.55], [0.95, 0.95], [0.72, 0.95]],
    ],
}

NUCLEAR_DETECTION = {
    "min_confidence_to_store": 0.35,
}

NUCLEAR_ADAPTIVE_NIGHT = {
    "min_confidence_binary": 0.45,
    "min_confidence_binary_bird": 0.45,
    "openvino_min_confidence_binary_bird": 0.45,
    "min_track_duration": 1.0,
    "min_confidence_to_process": 0.35,
}


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cfg_path = root / "app" / "app_config" / "user_config.yaml"
    if not cfg_path.is_file():
        cfg_path = Path("/app/app_config/user_config.yaml")
    if not cfg_path.is_file():
        print(f"missing {cfg_path}", file=sys.stderr)
        return 1

    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    proc = data.setdefault("processor", {})
    if not isinstance(proc, dict):
        proc = {}
        data["processor"] = proc
    data["processor"] = _deep_merge(proc, NUCLEAR_PROCESSOR)

    det = data.setdefault("detection", {})
    if isinstance(det, dict):
        data["detection"] = _deep_merge(det, NUCLEAR_DETECTION)

    ap = proc.get("adaptive_profiles")
    if isinstance(ap, dict):
        night = ap.get("night")
        if isinstance(night, dict):
            overrides = night.setdefault("overrides", {})
            if isinstance(overrides, dict):
                night["overrides"] = _deep_merge(overrides, NUCLEAR_ADAPTIVE_NIGHT)

    cfg_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"patched {cfg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
