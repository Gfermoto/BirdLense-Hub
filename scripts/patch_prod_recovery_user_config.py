#!/usr/bin/env python3
"""Emergency recovery: restore YOLO accepted boxes on prod (location-agnostic).

Use when raw >> 0 but accepted = 0 (quality stack too aggressive). Run on VPS:
  python3 scripts/patch_prod_recovery_user_config.py
  cd /app && docker compose up -d --force-recreate birdlense
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)

RECOVERY_PROCESSOR = {
    "min_confidence_binary": 0.25,
    "min_confidence_binary_bird": 0.25,
    "openvino_min_confidence_binary_bird": 0.25,
    "openvino_binary_track_ultralytics_conf": 0.22,
    "motion_verified_detection_enabled": False,
    "motion_global_static_reject_enabled": False,
    "background_subtraction_enabled": False,
    "scene_adaptive_conf_enabled": False,
    "auto_small_object_relax_enabled": True,
    "yolo_weak_track_salvage_enabled": True,
    "static_object_suppression_enabled": False,
    "detection_ignore_masks": [],
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
    data["processor"] = _deep_merge(proc, RECOVERY_PROCESSOR)

    cfg_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"recovery patched {cfg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
