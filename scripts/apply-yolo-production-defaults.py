#!/usr/bin/env python3
"""Согласованные пороги YOLO/OV для detect substream (704×576 ~7 FPS) + OpenVINO iGPU."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

POLICY = {
    "detection": {
        "merge_window_seconds": 12,
        "track_fragment_merge_enabled": True,
        "min_confidence_to_store": 0.08,
        "yolo_weak_track_salvage_enabled": True,
        "yolo_weak_track_salvage_min_confidence": 0.012,
    },
    "processor": {
        "inference_backend": "openvino",
        "inference_device": "intel:gpu",
        "classifier_inference_backend": "torch",
        "classifier_inference_device": "cpu",
        "tracker": "models/tracker/bytetrack_birdlense_unstick.yaml",
        "inference_lores_px": 640,
        "binary_imgsz": 640,
        "min_confidence_binary": 0.08,
        "min_confidence_binary_bird": 0.08,
        "min_confidence_binary_rodent": 0.12,
        "min_confidence_to_process": 0.20,
        "min_box_size_px": 14,
        "min_center_dist": 0.01,
        "binary_track_iou": 0.62,
        "openvino_binary_track_ultralytics_conf": 0.025,
        "openvino_binary_bird_score_scale": 8.5,
        "auto_unstick_no_track_frames": 28,
        "auto_unstick_min_confidence_binary": 0.05,
        "auto_unstick_min_confidence_binary_bird": 0.015,
        "generic_bird_min_detector_conf": 0.10,
        "generic_bird_min_frames": 2,
        "generic_bird_min_area_frac": 0.006,
        "generic_bird_min_best_frame_score": 5.0,
        "classifier_use_source_frame": True,
        "track_to_predict_fallback_enabled": True,
        "track_to_predict_fallback_confidence": 0.002,
        "iou_id_fallback_live_enabled": True,
    },
}

NIGHT_OVERRIDES = {
    "min_confidence_binary": 0.08,
    "min_confidence_binary_bird": 0.08,
    "min_box_size_px": 14,
    "min_center_dist": 0.01,
    "min_track_duration": 0.30,
    "min_confidence_to_process": 0.18,
}


def _deep_merge(base: dict, patch: dict) -> dict:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _maybe_enable_classifier_openvino(proc: dict, repo_root: Path) -> None:
    """Если IR классификатора есть — OV на том же iGPU, иначе torch/cpu."""
    rel = str(proc.get("models", {}).get("classifier_openvino") or "").strip()
    if not rel:
        rel = "models/classification/weights/best_openvino_model"
    ov_dir = (repo_root / "app" / "processor" / rel).resolve()
    xml = list(ov_dir.glob("*.xml")) if ov_dir.is_dir() else []
    if xml:
        proc["classifier_inference_backend"] = "openvino"
        proc["classifier_inference_device"] = proc.get("inference_device") or "intel:gpu"
        print(f"classifier_openvino: {ov_dir} -> openvino {proc['classifier_inference_device']}")
    else:
        print(f"classifier_openvino missing under {ov_dir}; keep torch/cpu")


def apply(path: Path, *, repo_root: Path | None = None) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _deep_merge(data, POLICY)
    proc = data.setdefault("processor", {})
    root = repo_root or path.resolve().parents[1]
    _maybe_enable_classifier_openvino(proc, root)
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
    ap.add_argument(
        "--repo-root",
        default=".",
        help="BirdLense repo root (for classifier_openvino probe)",
    )
    args = ap.parse_args()
    apply(Path(args.config).resolve(), repo_root=Path(args.repo_root).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
