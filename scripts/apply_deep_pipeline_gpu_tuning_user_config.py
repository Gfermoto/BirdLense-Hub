#!/usr/bin/env python3
"""Apply deep-pipeline GPU tuning to user_config (prod overrides).

Source: tmp/deep_pipeline_today_full_gpu_stable.json + tuning plan (2026-05-29).
Run on VPS after deploy when user_config overrides shipped defaults:

  python3 scripts/apply_deep_pipeline_gpu_tuning_user_config.py
  cd app && docker compose up -d --force-recreate birdlense
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)

TUNING_PROCESSOR = {
    "birder_eu_min_confidence": 0.18,
    "min_confidence_binary_bird": 0.23,
    "openvino_min_confidence_binary_bird": 0.23,
    "openvino_binary_track_ultralytics_conf": 0.24,
    "bird_skip_classifier_max_area_frac": 0.015,
    "min_confidence_binary_rodent": 0.30,
    "track_regen_frame_step": 5,
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
    data["processor"] = _deep_merge(proc, TUNING_PROCESSOR)

    cfg_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"deep-pipeline GPU tuning patched {cfg_path}")
    for k, v in TUNING_PROCESSOR.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
