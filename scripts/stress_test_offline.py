#!/usr/bin/env python3
"""
Offline stress tests for SOTA 2.0 ScoringEngine (silence + storm).

Exit 0 when all scenarios pass; 1 otherwise. Optional auto-tune loop (--auto-tune).

CI mode (default): synthetic silence + golden storm probes (no mp4 required).
Full mode: pass --silence-video / --storm-video or --fetch-prod-clips.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
PROC_SRC = REPO / "app" / "processor" / "src"
GOLDEN_SYNTH = REPO / "app" / "data" / "datasets" / "golden_v2" / "manifest.synthetic.json"
DEFAULT_WEIGHTS = REPO / "app" / "processor" / "models" / "detection" / "weights" / "best.pt"
STRESS_DIR = REPO / "app" / "data" / "stress_clips"

MIN_STORM_RECALL = float(os.environ.get("STRESS_MIN_STORM_RECALL", "1.0"))
MAX_SILENCE_ACCEPTED = int(os.environ.get("STRESS_MAX_SILENCE_ACCEPTED", "0"))


@dataclass
class StressResult:
    scenario: str
    passed: bool
    accepted_boxes: int
    frames_sampled: int
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "passed": self.passed,
            "accepted_boxes": self.accepted_boxes,
            "frames_sampled": self.frames_sampled,
            **self.detail,
        }


def _import_engine():
    sys.path.insert(0, str(PROC_SRC))
    import numpy as np
    from scoring_engine import ScoringEngine, ScoringEngineConfig

    return np, ScoringEngine, ScoringEngineConfig


def _default_cfg(ScoringEngineConfig, **overrides):
    base = dict(
        enabled=True,
        calibration_frames=60,
        weight_conf=0.45,
        weight_motion=0.25,
        weight_shape=0.15,
        weight_background=0.15,
        default_low_threshold=0.38,
        default_high_threshold=0.52,
        review_band_width=0.14,
    )
    base.update(overrides)
    return ScoringEngineConfig(**base)


def _box_from_xyxy(xyxy: tuple[float, float, float, float], conf: float, track_id: int, frame_shape) -> dict:
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = xyxy
    area = max(1.0, (x2 - x1) * (y2 - y1))
    return {
        "detector_label": "Bird",
        "conf": conf,
        "track_id": track_id,
        "crop_coords": (int(x1), int(y1), int(x2), int(y2)),
        "box_area_norm": area / float(w * h),
    }


def _yolo_bird_boxes(frame, model, conf: float, bird_class_ids: set[int]) -> list[dict]:
    pred_kw = {"imgsz": 640, "conf": conf, "verbose": False}
    res = model.predict(frame, **pred_kw)
    out: list[dict] = []
    if not res or not res[0].boxes:
        return out
    b = res[0].boxes
    xyxy = b.xyxy.cpu().numpy()
    cls = b.cls.int().cpu().tolist()
    confs = b.conf.cpu().tolist()
    for i, c in enumerate(cls):
        if int(c) not in bird_class_ids:
            continue
        x1, y1, x2, y2 = (float(v) for v in xyxy[i])
        out.append(_box_from_xyxy((x1, y1, x2, y2), float(confs[i]), i + 1, frame.shape))
    return out


def run_silence_synthetic(ScoringEngine, ScoringEngineConfig, np, *, cfg: ScoringEngineConfig) -> StressResult:
    """Static scene + phantom low-conf boxes every frame (wind/shadow FP simulation)."""
    import cv2

    eng = ScoringEngine(cfg)
    frame = np.full((480, 640, 3), 118, dtype=np.uint8)
    accepted = 0
    frames = 400
    phantoms = [
        (0.32, 200, 200, 280, 280),
        (0.36, 100, 120, 200, 220),
        (0.34, 400, 300, 500, 400),
    ]
    for fi in range(frames):
        boxes = [
            _box_from_xyxy((x1, y1, x2, y2), conf, tid + 1, frame.shape)
            for tid, (conf, x1, y1, x2, y2) in enumerate(phantoms)
        ]
        kept = eng.filter_boxes(boxes, frame_bgr=frame, frame_index=fi)
        for b in kept:
            if str(b.get("detector_label")) == "Bird" and not b.get("scoring_review_only"):
                accepted += 1
    passed = accepted <= MAX_SILENCE_ACCEPTED
    return StressResult(
        "silence_synthetic",
        passed,
        accepted,
        frames,
        {"mode": "phantom_boxes", "calibrated": eng.calibration.calibrated},
    )


def run_silence_video(
    path: Path,
    ScoringEngine,
    ScoringEngineConfig,
    np,
    *,
    cfg: ScoringEngineConfig,
    model=None,
    frame_step: int = 15,
    max_frames: int = 800,
    yolo_conf: float = 0.12,
) -> StressResult:
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return StressResult("silence_video", False, -1, 0, {"error": f"cannot_open:{path}"})
    eng = ScoringEngine(cfg)
    accepted = 0
    sampled = 0
    fi = 0
    bird_ids = {0}
    while sampled < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if fi % frame_step:
            fi += 1
            continue
        fi += 1
        sampled += 1
        boxes: list[dict] = []
        if model is not None:
            boxes = _yolo_bird_boxes(frame, model, yolo_conf, bird_ids)
        else:
            h, w = frame.shape[:2]
            boxes = [
                _box_from_xyxy((w * 0.4, h * 0.4, w * 0.55, h * 0.55), 0.33, 1, frame.shape),
            ]
        kept = eng.filter_boxes(boxes, frame_bgr=frame, frame_index=sampled)
        for b in kept:
            if str(b.get("detector_label")) == "Bird" and not b.get("scoring_review_only"):
                accepted += 1
    cap.release()
    passed = accepted <= MAX_SILENCE_ACCEPTED
    return StressResult(
        "silence_video",
        passed,
        accepted,
        sampled,
        {"video": str(path), "yolo": model is not None},
    )


def run_storm_golden(ScoringEngine, ScoringEngineConfig, np) -> StressResult:
    """Storm = bird clips from synthetic manifest (probe accept)."""
    data = json.loads(GOLDEN_SYNTH.read_text(encoding="utf-8"))
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cfg = _default_cfg(ScoringEngineConfig, weight_conf=1.0, weight_motion=0.0, weight_shape=0.0, weight_background=0.0)
    birds = [c for c in data.get("clips") or [] if c.get("is_bird")]
    found = 0
    missed = 0
    for clip in birds:
        eng = ScoringEngine(cfg)
        for i in range(max(8, cfg.calibration_frames)):
            eng.filter_boxes([], frame_bgr=frame, frame_index=i)
        ok = False
        for i, probe in enumerate(clip.get("probes") or []):
            box = _box_from_xyxy(
                (80, 80, 180, 180),
                float(probe.get("raw_conf", 0.55)),
                i + 1,
                frame.shape,
            )
            kept = eng.filter_boxes([box], frame_bgr=frame, frame_index=100 + i)
            accepted = [
                b
                for b in kept
                if str(b.get("detector_label")) == "Bird" and not b.get("scoring_review_only")
            ]
            if accepted:
                ok = True
                break
        if ok:
            found += 1
        else:
            missed += 1
    recall = found / len(birds) if birds else 1.0
    passed = recall >= MIN_STORM_RECALL
    return StressResult(
        "storm_golden",
        passed,
        found,
        len(birds),
        {"recall": round(recall, 4), "missed": missed},
    )


def run_storm_video(
    path: Path,
    ScoringEngine,
    ScoringEngineConfig,
    np,
    *,
    cfg: ScoringEngineConfig,
    model,
    frame_step: int = 5,
    max_frames: int = 600,
    yolo_conf: float = 0.2,
) -> StressResult:
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return StressResult("storm_video", False, 0, 0, {"error": f"cannot_open:{path}"})
    eng = ScoringEngine(cfg)
    bird_ids = {0}
    yolo_frames = 0
    accepted_frames = 0
    sampled = 0
    fi = 0
    while sampled < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if fi % frame_step:
            fi += 1
            continue
        fi += 1
        sampled += 1
        boxes = _yolo_bird_boxes(frame, model, yolo_conf, bird_ids)
        if not boxes:
            eng.filter_boxes([], frame_bgr=frame, frame_index=sampled)
            continue
        yolo_frames += 1
        kept = eng.filter_boxes(boxes, frame_bgr=frame, frame_index=sampled)
        if any(
            str(b.get("detector_label")) == "Bird" and not b.get("scoring_review_only") for b in kept
        ):
            accepted_frames += 1
    cap.release()
    recall = accepted_frames / yolo_frames if yolo_frames else 0.0
    passed = yolo_frames > 0 and recall >= MIN_STORM_RECALL
    return StressResult(
        "storm_video",
        passed,
        accepted_frames,
        sampled,
        {"yolo_frames": yolo_frames, "recall": round(recall, 4)},
    )


TUNE_GRID: list[dict[str, float]] = [
    {},
    {"default_low_threshold": 0.40, "default_high_threshold": 0.54},
    {"default_low_threshold": 0.42, "default_high_threshold": 0.56},
    {"default_low_threshold": 0.44, "default_high_threshold": 0.58},
    {"review_band_width": 0.10},
    {"weight_motion": 0.20, "weight_conf": 0.50},
]


def _run_all(
    *,
    silence_video: Path | None,
    storm_video: Path | None,
    use_yolo: bool,
    cfg_overrides: dict[str, float],
) -> list[StressResult]:
    np, ScoringEngine, ScoringEngineConfig = _import_engine()
    cfg = _default_cfg(ScoringEngineConfig, **cfg_overrides)
    model = None
    if use_yolo and DEFAULT_WEIGHTS.is_file():
        try:
            from ultralytics import YOLO
        except ImportError:
            YOLO = None  # type: ignore
        if YOLO is not None:
            model = YOLO(str(DEFAULT_WEIGHTS), task="detect")

    results = [run_silence_synthetic(ScoringEngine, ScoringEngineConfig, np, cfg=cfg)]
    results.append(run_storm_golden(ScoringEngine, ScoringEngineConfig, np))
    if silence_video and silence_video.is_file():
        results.append(
            run_silence_video(
                silence_video,
                ScoringEngine,
                ScoringEngineConfig,
                np,
                cfg=cfg,
                model=model,
            )
        )
    if storm_video and storm_video.is_file() and model is not None:
        results.append(
            run_storm_video(
                storm_video,
                ScoringEngine,
                ScoringEngineConfig,
                np,
                cfg=cfg,
                model=model,
            )
        )
    return results


def _fetch_prod_clip(remote_path: str, local_name: str) -> Path | None:
    host = os.environ.get("STRESS_SSH_HOST", "root@185.218.111.196")
    port = os.environ.get("STRESS_SSH_PORT", "2222")
    remote = f"/root/BirdLense/app/{remote_path.lstrip('/')}"
    STRESS_DIR.mkdir(parents=True, exist_ok=True)
    dest = STRESS_DIR / local_name
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    cmd = ["scp", "-P", port, f"{host}:{remote}", str(dest)]
    try:
        subprocess.run(cmd, check=True, timeout=120, capture_output=True)
        return dest if dest.is_file() else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silence-video", type=Path, default=None)
    parser.add_argument("--storm-video", type=Path, default=None)
    parser.add_argument("--fetch-prod-clips", action="store_true")
    parser.add_argument("--auto-tune", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--no-yolo", action="store_true")
    args = parser.parse_args()

    silence = args.silence_video
    storm = args.storm_video
    if args.fetch_prod_clips:
        storm = _fetch_prod_clip(
            "data/recordings/2026/05/18/074247/video.mp4",
            "storm_bird.mp4",
        )
        # Prefer a modest empty-feeder clip; skip multi-GB downloads in CI.
        silence = _fetch_prod_clip(
            "data/recordings/2026/05/20/083339/video.mp4",
            "silence_noise.mp4",
        )
        if silence is None or silence.stat().st_size > 80_000_000:
            silence = None

    use_yolo = not args.no_yolo and DEFAULT_WEIGHTS.is_file()
    grids = TUNE_GRID if args.auto_tune else [{}]
    report: dict[str, Any] = {"format": "stress_test_offline@v1", "attempts": []}

    for overrides in grids:
        results = _run_all(
            silence_video=silence,
            storm_video=storm,
            use_yolo=use_yolo,
            cfg_overrides=overrides,
        )
        ok = all(r.passed for r in results)
        attempt = {"cfg_overrides": overrides, "ok": ok, "scenarios": [r.to_dict() for r in results]}
        report["attempts"].append(attempt)
        if ok:
            report["ok"] = True
            report["winning_cfg"] = overrides
            break
    else:
        report["ok"] = False

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
