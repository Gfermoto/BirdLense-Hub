#!/usr/bin/env python3
"""Merge balanced FP-suppression overrides into user_config.yaml (prod-safe).

Location-agnostic (no site masks). Safe with detection_quality bird_trust_floor fix:
motion/MOG2/static stay on; static thresholds align to min_confidence_binary_bird.

Run on VPS after deploy:
  python3 scripts/patch_prod_nuclear_user_config.py
  cd /app && docker compose up -d --force-recreate birdlense

For emergency bypass (YOLO accepted=0): use patch_prod_recovery_user_config.py instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)

BALANCED_PROCESSOR = {
    "min_confidence_binary": 0.28,
    "min_confidence_binary_bird": 0.28,
    "openvino_min_confidence_binary_bird": 0.28,
    "openvino_binary_track_ultralytics_conf": 0.24,
    "min_track_duration": 1.0,
    "auto_small_object_relax_enabled": True,
    "yolo_weak_track_salvage_enabled": True,
    "ultra_weak_box_salvage_enabled": False,
    "motion_verified_detection_enabled": True,
    "motion_verified_min_pixel_change": 10,
    "motion_global_static_reject_enabled": True,
    "motion_global_max_mean_absdiff": 2.0,
    "motion_strict_consecutive_frames": 3,
    "motion_hard_conf_ceiling": 0.55,
    "static_object_suppression_enabled": True,
    "static_scene_bird_min_confidence": 0.28,
    "static_square_hard_reject_max_conf": 0.22,
    "static_temporal_min_seconds": 6,
    "background_subtraction_enabled": True,
    "scene_adaptive_conf_enabled": True,
    "scene_adaptive_static_boost": 0.06,
    "detection_ignore_masks": [],
}

BALANCED_DETECTION = {
    "min_confidence_to_store": 0.32,
}

BALANCED_ADAPTIVE_NIGHT = {
    "min_confidence_binary": 0.38,
    "min_confidence_binary_bird": 0.38,
    "openvino_min_confidence_binary_bird": 0.38,
    "min_track_duration": 1.0,
    "min_confidence_to_process": 0.32,
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
    data["processor"] = _deep_merge(proc, BALANCED_PROCESSOR)

    det = data.setdefault("detection", {})
    if isinstance(det, dict):
        data["detection"] = _deep_merge(det, BALANCED_DETECTION)

    ap = proc.get("adaptive_profiles")
    if isinstance(ap, dict):
        night = ap.get("night")
        if isinstance(night, dict):
            overrides = night.setdefault("overrides", {})
            if isinstance(overrides, dict):
                night["overrides"] = _deep_merge(overrides, BALANCED_ADAPTIVE_NIGHT)

    cfg_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"patched {cfg_path} (balanced FP, masks cleared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
