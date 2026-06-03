#!/usr/bin/env python3
"""Patch prod user_config for OpenVINO track density (standalone-first #591)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
UC = ROOT / "app" / "app_config" / "user_config.yaml"

PATCH = {
    "processor": {
        # track(conf) ниже post-filter Bird — больше кандидатов для ByteTrack id
        "openvino_binary_track_ultralytics_conf": 0.06,
        "auto_unstick_no_track_frames": 8,
        "auto_unstick_min_confidence_binary": 0.04,
        "auto_unstick_min_confidence_binary_bird": 0.025,
        "iou_id_fallback_live_enabled": True,
        "classifier_async_enabled": True,
    }
}


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else UC
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    proc = data.setdefault("processor", {})
    for key, val in PATCH["processor"].items():
        proc[key] = val
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"patched {path}")
    for key, val in PATCH["processor"].items():
        print(f"  processor.{key}: {val}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
