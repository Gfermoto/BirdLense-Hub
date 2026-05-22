#!/usr/bin/env python3
"""Apply TrapperAI v02.2024 production processor settings to user_config.yaml (idempotent)."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)

TRAPPER_PROCESSOR = {
    "inference_backend": "openvino",
    "inference_device": "intel:gpu",
    "openvino_binary_enabled": True,
    "classifier_inference_backend": "openvino",
    "classifier_inference_device": "intel:gpu",
    "models": {
        "binary": "models/detection/weights/trapper_ai_v02_2024.pt",
        "binary_openvino": "models/detection/weights/trapper_ai_v02_2024_openvino_model",
    },
    "detector_scope": ["Bird", "Eurasian Red Squirrel"],
    "detector_native_class_labels": True,
    "binary_predict_class_allowlist": [0, 5],
    "inference_lores_wh": [704, 576],
    "inference_lores_px": 704,
    "binary_imgsz": 704,
    "track_regen_lores_wh": [704, 576],
    "min_confidence_binary": 0.35,
    "min_confidence_binary_bird": 0.35,
    "min_confidence_binary_squirrel": 0.32,
    "min_confidence_binary_rodent": 0.32,
    "openvino_min_confidence_binary_bird": 0.35,
    "openvino_binary_track_ultralytics_conf": 0.30,
    "tracker": "models/tracker/bytetrack_birdlense_lowfps.yaml",
    "auto_unstick_enabled": False,
    "openvino_binary_bird_score_scale": 1.0,
    "min_box_size_px": 18,
    "min_center_dist": 0.01,
    "binary_track_iou": 0.62,
    "binary_track_max_det": 40,
    "generic_bird_min_detector_conf": 0.32,
    "auto_small_object_relax_enabled": False,
    "bird_skip_classifier_max_area_frac": 0.018,
    "species_confidence_overrides": {"Bird": 0.32},
    "min_confidence_to_process": 0.35,
    "scoring_default_low_threshold": 0.35,
    "scoring_default_high_threshold": 0.50,
    "detector_weight_contract": "off",
    "shadow_ensemble_enabled": False,
    "ultra_weak_box_salvage_enabled": False,
    "binary_rescue_enabled": False,
}

TRAPPER_DETECTION = {
    "yolo_weak_track_salvage_enabled": False,
    "yolo_weak_track_salvage_min_confidence": 0.35,
    "frigate_trigger_review_salvage_enabled": False,
    "absorb_generic_bird": False,
}

TRAPPER_VIDEO = {
    "capture_backend": "auto",
    "encoding": "intel",
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
    vid = data.setdefault("video", {})
    if not isinstance(vid, dict):
        vid = {}
        data["video"] = vid

    data["processor"] = _deep_merge(proc, TRAPPER_PROCESSOR)
    data["video"] = _deep_merge(vid, TRAPPER_VIDEO)

    det = data.setdefault("detection", {})
    if not isinstance(det, dict):
        det = {}
        data["detection"] = det
    data["detection"] = _deep_merge(det, TRAPPER_DETECTION)
    if isinstance(det, dict):
        try:
            store = float(det.get("min_confidence_to_store") or 0)
            proc_conf = float(data["processor"].get("min_confidence_to_process") or 0.32)
            if store > proc_conf:
                det["min_confidence_to_store"] = proc_conf
        except (TypeError, ValueError):
            pass

    tp = data["processor"].get("tracker_profiles")
    if not isinstance(tp, dict):
        tp = {}
        data["processor"]["tracker_profiles"] = tp
    tp["night"] = "models/tracker/bytetrack_birdlense_night.yaml"

    profiles = data["processor"].get("adaptive_profiles")
    if isinstance(profiles, dict):
        for name, prof in profiles.items():
            if name in ("enabled",) or not isinstance(prof, dict):
                continue
            overrides = prof.get("overrides")
            if isinstance(overrides, dict):
                if "binary_imgsz" in overrides:
                    overrides["binary_imgsz"] = 704
                overrides["min_confidence_binary"] = 0.38
                overrides["min_confidence_binary_bird"] = 0.38
                overrides["openvino_min_confidence_binary_bird"] = 0.38
                overrides["generic_bird_min_detector_conf"] = 0.35
                overrides["binary_predict_class_allowlist"] = [0, 5]

    cfg_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"trapper production patched {cfg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
