#!/usr/bin/env python3
"""Merged detector config guards — post-deploy / CI parity (#YOLO-blind circle-break)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SUBTYPE_BAD = re.compile(r"subtype\s*=\s*1\b", re.IGNORECASE)
_MAX_BIRD_OVERRIDE = 0.1


def _repo_layout() -> tuple[Path, Path, Path]:
    """Return (repo_root, default_config_path, user_config_path) for host or container."""
    here = Path(__file__).resolve()
    repo = here.parents[1]
    if (repo / "app_config").is_dir():
        return (
            repo,
            repo / "app_config/default_config.yaml",
            repo / "app_config/user_config.yaml",
        )
    return (
        repo,
        repo / "app/app_config/default_config.yaml",
        repo / "app/app_config/user_config.yaml",
    )


REPO, _DEFAULT, _USER = _repo_layout()


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _merge(default: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    app_root = REPO if (REPO / "app_config").is_dir() else REPO / "app"
    sys.path.insert(0, str(app_root))
    from app_config.app_config import AppConfig

    return AppConfig.merge_dicts(default, user)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _collect_rtsp_strings(cfg: dict[str, Any]) -> list[str]:
    out: list[str] = []
    video = cfg.get("video") or {}
    for cam in video.get("cameras") or []:
        if not isinstance(cam, dict):
            continue
        for key in ("detect_stream_name", "stream_name", "rtsp_url", "url"):
            val = cam.get(key)
            if isinstance(val, str) and val.strip():
                out.append(val.strip())
    proc = cfg.get("processor") or {}
    overrides = proc.get("camera_overrides") or {}
    if isinstance(overrides, dict):
        for cam_cfg in overrides.values():
            if not isinstance(cam_cfg, dict):
                continue
            for key in ("detect_stream_name", "stream_name"):
                val = cam_cfg.get(key)
                if isinstance(val, str) and val.strip():
                    out.append(val.strip())
    return out


def evaluate_detector_guards(
    *,
    default: dict[str, Any],
    user: dict[str, Any],
) -> dict[str, Any]:
    merged = _merge(default, user)
    proc = merged.get("processor") or {}
    default_proc = default.get("processor") or {}
    issues: list[dict[str, Any]] = []
    warns: list[dict[str, Any]] = []

    native_lores = _as_bool(proc.get("openvino_native_lores_imgsz"), default=False)
    if native_lores:
        issues.append(
            {
                "key": "processor.openvino_native_lores_imgsz",
                "merged": True,
                "severity": "critical",
                "reason": "704x704 Trapper IR breaks with native lores; keep false",
            }
        )

    default_native = _as_bool(default_proc.get("openvino_native_lores_imgsz"), default=False)
    if default_native:
        issues.append(
            {
                "key": "default_config.processor.openvino_native_lores_imgsz",
                "merged": True,
                "severity": "critical",
                "reason": "repo default_config must ship openvino_native_lores_imgsz: false",
            }
        )

    overrides = proc.get("species_confidence_overrides") or {}
    bird_val: float | None = None
    if isinstance(overrides, dict) and overrides.get("Bird") is not None:
        try:
            bird_val = float(overrides["Bird"])
        except (TypeError, ValueError):
            bird_val = None
    if bird_val is not None and bird_val > _MAX_BIRD_OVERRIDE:
        issues.append(
            {
                "key": "processor.species_confidence_overrides.Bird",
                "merged": bird_val,
                "severity": "critical",
                "reason": f"Bird override must be <= {_MAX_BIRD_OVERRIDE}",
            }
        )

    for text in _collect_rtsp_strings(merged):
        if _SUBTYPE_BAD.search(text):
            warns.append(
                {
                    "key": "video.rtsp.subtype",
                    "value": text[:120],
                    "severity": "warn",
                    "reason": "subtype=1 often mismatches Frigate detect (subtype=0) → YOLO blind",
                }
            )

    return {
        "schema": "merged_detector_guards@v1",
        "ok": len(issues) == 0,
        "critical_count": len(issues),
        "warn_count": len(warns),
        "issues": issues,
        "warnings": warns,
        "merged_snapshot": {
            "openvino_native_lores_imgsz": native_lores,
            "species_confidence_overrides.Bird": bird_val,
        },
    }


def _yolo_one_frame_smoke() -> dict[str, Any]:
    """Optional in-container smoke: one predict on bundled or latest recording frame."""
    import cv2

    weights = Path("/app/processor/models/detection/weights")
    if not weights.is_dir():
        weights = (
            REPO / "processor/models/detection/weights"
            if (REPO / "processor").is_dir()
            else REPO / "app/processor/models/detection/weights"
        )
    model_path: Path | None = None
    for cand in (
        weights / "trapper_ai_v02_2024_openvino_model",
        weights / "best_openvino_model",
        weights / "best.pt",
        weights / "yolo11n.pt",
    ):
        if cand.exists():
            model_path = cand
            break
    if model_path is None:
        return {"status": "skipped", "reason": "no_detector_weights"}

    frame = None
    test_images = [
        REPO / "app/processor/tests/fixtures/bird_frame.jpg",
        Path("/app/processor/tests/fixtures/bird_frame.jpg"),
    ]
    for img in test_images:
        if img.is_file():
            frame = cv2.imread(str(img))
            if frame is not None:
                break
    if frame is None:
        rec_root = Path("/app/data/recordings") if Path("/app/data").is_dir() else REPO / "app/data/recordings"
        if rec_root.is_dir():
            for mp4 in sorted(rec_root.rglob("video.mp4"), reverse=True)[:5]:
                cap = cv2.VideoCapture(str(mp4))
                ok, frame = cap.read()
                cap.release()
                if ok and frame is not None:
                    break
    if frame is None:
        return {"status": "skipped", "reason": "no_test_frame"}

    try:
        from ultralytics import YOLO

        model = YOLO(str(model_path))
        res = model.predict(frame, conf=0.08, imgsz=704, verbose=False)[0]
        boxes = len(res.boxes) if res.boxes is not None else 0
        return {
            "status": "ok" if boxes > 0 else "warn",
            "model": str(model_path.name),
            "boxes": boxes,
            "reason": "boxes>=1" if boxes > 0 else "zero_boxes_on_smoke_frame",
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Merged detector config guards")
    ap.add_argument("--default-config", type=Path, default=_DEFAULT)
    ap.add_argument("--user-config", type=Path, default=_USER)
    ap.add_argument("--yolo-smoke", action="store_true", help="optional one-frame detector smoke")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    default = _load_yaml(args.default_config)
    user = _load_yaml(args.user_config) if args.user_config.is_file() else {}
    report = evaluate_detector_guards(default=default, user=user)
    if args.yolo_smoke:
        report["yolo_smoke"] = _yolo_one_frame_smoke()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"merged_detector_guards: ok={report['ok']} critical={report['critical_count']} warn={report['warn_count']}")
        for item in report.get("issues") or []:
            print(f"  CRITICAL {item['key']}: {item.get('reason')}")
        for item in report.get("warnings") or []:
            print(f"  WARN {item['key']}: {item.get('reason')}")
        if "yolo_smoke" in report:
            ys = report["yolo_smoke"]
            print(f"  yolo_smoke: {ys.get('status')} ({ys.get('reason') or ys.get('error', '')})")

    fail = not report["ok"]
    if args.yolo_smoke:
        ys = report.get("yolo_smoke") or {}
        if ys.get("status") == "error":
            fail = True
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
