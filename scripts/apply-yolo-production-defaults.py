#!/usr/bin/env python3
"""Применить согласованные YOLO/OV пороги к user_config.yaml (площадка или локально)."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

POLICY = {
    "detection": {
        "merge_window_seconds": 12,
        "track_fragment_merge_enabled": True,
    },
    "processor": {
        "inference_backend": "openvino",
        "inference_device": "intel:gpu",
        "classifier_inference_backend": "torch",
        "classifier_inference_device": "cpu",
        "tracker": "models/tracker/bytetrack_birdlense_unstick.yaml",
        "min_confidence_binary": 0.08,
        "min_confidence_binary_bird": 0.08,
        "min_confidence_binary_rodent": 0.12,
        "min_box_size_px": 20,
        "min_center_dist": 0.01,
        "binary_track_iou": 0.62,
        "openvino_binary_track_ultralytics_conf": 0.025,
        "openvino_binary_bird_score_scale": 8.5,
        "auto_unstick_no_track_frames": 60,
        "classifier_use_source_frame": True,
    },
}

NIGHT_OVERRIDES = {
    "min_confidence_binary": 0.08,
    "min_confidence_binary_bird": 0.08,
    "min_box_size_px": 20,
    "min_center_dist": 0.01,
    "min_track_duration": 0.35,
    "min_confidence_to_process": 0.26,
}


def _deep_merge(base: dict, patch: dict) -> dict:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def apply(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _deep_merge(data, POLICY)
    proc = data.setdefault("processor", {})
    ap = proc.setdefault("adaptive_profiles", {})
    night = ap.setdefault("night", {})
    overrides = night.setdefault("overrides", {})
    overrides.update(NIGHT_OVERRIDES)
    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"ok {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default="app/app_config/user_config.yaml",
        help="Path to user_config.yaml",
    )
    args = ap.parse_args()
    apply(Path(args.config).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
