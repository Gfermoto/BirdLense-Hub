#!/usr/bin/env python3
"""Enable SOTA 2.0 ScoringEngine on prod user_config (location-agnostic)."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)

SOTA20_PROCESSOR = {
    "scoring_engine_enabled": True,
    "frame_decision_trace_enabled": True,
    "motion_verified_detection_enabled": False,
    "background_subtraction_enabled": False,
    "scene_adaptive_conf_enabled": False,
    "static_object_suppression_enabled": False,
    "min_confidence_binary_bird": 0.28,
    "openvino_min_confidence_binary_bird": 0.28,
}

SOTA20_DETECTION = {
    "frigate_standalone_when_no_yolo": False,
    "min_confidence_to_store": 0.32,
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
    data["processor"] = _deep_merge(proc, SOTA20_PROCESSOR)
    det = data.setdefault("detection", {})
    if isinstance(det, dict):
        data["detection"] = _deep_merge(det, SOTA20_DETECTION)
    cfg_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"SOTA 2.0 patched {cfg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
