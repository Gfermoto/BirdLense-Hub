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
        "frigate_standalone_require_blind_yolo": True,
        "frigate_standalone_blind_score_threshold": 0.7,
        "yolo_blind_required_consecutive_sessions": 1,
        "yolo_blind_min_duration_seconds": 30,
        "yolo_blind_min_frames": 180,
        "yolo_blind_min_effective_fps": 2.0,
        "yolo_blind_score_threshold": 0.7,
        "yolo_blind_quickcheck_seconds": 2.0,
        "yolo_blind_quickcheck_min_confidence_binary": 0.05,
        "yolo_blind_quickcheck_min_confidence_binary_bird": 0.03,
        "yolo_blind_quickcheck_min_box_size_px": 10,
        "yolo_blind_min_frigate_only_frames": 120,
        "yolo_self_heal_restart_enabled": True,
        "yolo_self_heal_cooldown_seconds": 300,
        "yolo_self_heal_escalation_window_seconds": 900,
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
        "lowres_enhance_enabled": True,
        "lowres_enhance_max_input_px": 800,
        "lowres_sharpen_amount": 0.32,
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
    "min_track_duration": 0.25,
    "min_confidence_to_process": 0.20,
    "generic_bird_min_detector_conf": 0.10,
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


def _patch_env(env_path: Path) -> None:
    """Синхронизировать app/.env (docker compose читает только при create/recreate)."""
    if not env_path.is_file():
        print(f"skip env (missing): {env_path}")
        return
    updates = {
        "BIRDLENSE_INFERENCE_BACKEND": "openvino",
        "BIRDLENSE_INFERENCE_DEVICE": "intel:gpu",
        "BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND": "openvino",
        "BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE": "intel:gpu",
    }
    lines = env_path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key == "BIRDLENSE_SKIP_CONFIDENCE_FLOORS":
            continue
        if key in updates:
            if key in seen:
                continue
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in updates.items():
        if key not in seen:
            out.append(f"{key}={val}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"ok env {env_path} (recreate container: docker compose up -d --force-recreate birdlense)")


def apply(path: Path, *, repo_root: Path | None = None, env_path: Path | None = None) -> None:
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
    ep = env_path or (path.resolve().parents[1] / ".env")
    _patch_env(ep)


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
    ap.add_argument(
        "--env",
        default="",
        help="app/.env path (default: sibling of app_config parent/.env)",
    )
    args = ap.parse_args()
    cfg = Path(args.config).resolve()
    root = Path(args.repo_root).resolve()
    env = Path(args.env).resolve() if args.env else None
    apply(cfg, repo_root=root, env_path=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
