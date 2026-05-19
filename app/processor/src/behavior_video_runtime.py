"""Video-tracklet behavior runtime (OpenVINO + shadow-safe canary for #459/#460)."""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any

import numpy as np

_log = logging.getLogger(__name__)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _tracklet_stats(video_detections: list[dict[str, Any]]) -> dict[str, float]:
    frame_rows = 0.0
    tracks = 0.0
    mean_span = 0.0
    moving_tracks = 0.0
    for row in video_detections:
        frames = row.get("frames") or []
        if not isinstance(frames, list) or not frames:
            continue
        tracks += 1.0
        frame_rows += float(len(frames))
        x0 = y0 = x1 = y1 = None
        x2 = y2 = x3 = y3 = None
        if isinstance(frames[0], dict):
            b = frames[0].get("bbox")
            if isinstance(b, list) and len(b) == 4:
                x0, y0, x1, y1 = [_safe_float(v) for v in b]
        if isinstance(frames[-1], dict):
            b = frames[-1].get("bbox")
            if isinstance(b, list) and len(b) == 4:
                x2, y2, x3, y3 = [_safe_float(v) for v in b]
        if None not in (x0, y0, x1, y1, x2, y2, x3, y3):
            c0x = (x0 + x1) * 0.5
            c0y = (y0 + y1) * 0.5
            c1x = (x2 + x3) * 0.5
            c1y = (y2 + y3) * 0.5
            drift = math.hypot(c1x - c0x, c1y - c0y)
            mean_span += drift
            if drift >= 0.08:
                moving_tracks += 1.0
    if tracks > 0:
        mean_span /= tracks
    return {
        "frame_rows": frame_rows,
        "tracks": tracks,
        "mean_span": mean_span,
        "moving_ratio": (moving_tracks / tracks) if tracks > 0 else 0.0,
    }


def _resolve_video_openvino_path(br: dict[str, Any], *, processor_cwd: str | None) -> Path | None:
    raw = str(br.get("video_openvino_path") or os.environ.get("BIRDLENSE_BEHAVIOR_VIDEO_OPENVINO_PATH") or "").strip()
    if not raw:
        raw = "models/behavior_v1_openvino"
    p = Path(raw)
    if p.is_file() and p.suffix.lower() in (".xml", ".onnx"):
        return p.resolve()
    if p.is_dir():
        for name in ("behavior_video_model.xml", "behavior_video_model.onnx"):
            cand = (p / name).resolve()
            if cand.is_file():
                return cand
        xmls = sorted(p.glob("*.xml"))
        if xmls:
            return xmls[0].resolve()
    roots: list[Path] = []
    if processor_cwd:
        roots.append(Path(processor_cwd))
    roots.append(Path(__file__).resolve().parents[1])
    for root in roots:
        cand = (root / raw).resolve()
        if cand.is_file():
            return cand
        if cand.is_dir():
            for name in ("behavior_video_model.xml",):
                cp = (cand / name).resolve()
                if cp.is_file():
                    return cp
            xs = sorted(cand.glob("*.xml"))
            if xs:
                return xs[0].resolve()
    return None


def _load_video_export_labels(br: dict[str, Any], *, processor_cwd: str | None) -> list[str]:
    raw = str(br.get("video_weights_path") or br.get("video_export_path") or "").strip()
    if not raw:
        return []
    p = Path(raw)
    if not p.is_file() and processor_cwd:
        cand = (Path(processor_cwd) / raw).resolve()
        if cand.is_file():
            p = cand
    if not p.is_file():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        if str(payload.get("schema") or "") != "behavior_video_export@v1":
            return []
        return [str(x) for x in (payload.get("labels") or []) if str(x)]
    except Exception:
        return []


def _predict_video_openvino(
    app_config: Any,
    video_detections: list[dict[str, Any]],
    *,
    duration_s: float,
    processor_cwd: str | None,
    video_path: str | None,
    br: dict[str, Any],
) -> tuple[str | None, float]:
    from behavior_openvino_runtime import BehaviorOpenvinoRuntime

    ov_path = _resolve_video_openvino_path(br, processor_cwd=processor_cwd)
    labels = _load_video_export_labels(br, processor_cwd=processor_cwd)
    if ov_path is None or not labels:
        return None, 0.0

    try:
        from shared.behavior_tracklet_crop import runtime_tracklet_rgb_features
    except ImportError:
        return None, 0.0

    feats = runtime_tracklet_rgb_features(
        video_detections,
        video_path=video_path,
        processor_cwd=processor_cwd,
    )
    if feats is None:
        return None, 0.0

    runtime = BehaviorOpenvinoRuntime()
    if not runtime.load_if_needed(ov_path, labels, app_config=app_config):
        return None, 0.0
    assert runtime._compiled is not None
    assert runtime._input_name is not None
    x = np.array([feats], dtype=np.float32)
    ov_out = runtime._compiled({runtime._input_name: x})
    raw_out = ov_out[runtime._compiled.outputs[runtime._output_idx]]
    logits = np.asarray(raw_out, dtype=np.float64).reshape(-1)
    if logits.shape[0] == 1 and len(labels) == 2:
        # Binary sklearn export: single logit for labels[1] (e.g. flying vs feeding).
        p_pos = 1.0 / (1.0 + np.exp(-float(logits[0])))
        probs = np.array([1.0 - p_pos, p_pos], dtype=np.float64)
    elif logits.shape[0] != len(labels):
        _log.warning(
            "behavior video openvino: logits dim %s != n_labels %s (path=%s)",
            logits.shape[0],
            len(labels),
            ov_path,
        )
        return None, 0.0
    else:
        logits = logits - np.max(logits)
        probs = np.exp(logits) / (np.sum(np.exp(logits)) + 1e-12)
    idx = int(np.argmax(probs))
    return labels[idx], float(probs[idx])


def _predict_video_rules(
    video_detections: list[dict[str, Any]],
    *,
    duration_s: float,
    model_kind: str,
    model_version: str,
) -> tuple[str | None, float, str, str]:
    if not video_detections:
        return None, 0.0, model_kind, model_version

    st = _tracklet_stats(video_detections)
    duration = max(1.0, _safe_float(duration_s, 0.0))
    fps_eff = st["frame_rows"] / duration
    motion = st["moving_ratio"]
    span = st["mean_span"]
    tracks = st["tracks"]

    if motion >= 0.55 or span >= 0.18:
        return "flying", min(0.95, 0.52 + motion * 0.42), model_kind, model_version
    if fps_eff >= 5.0 and tracks >= 2.0:
        return "feeding", min(0.93, 0.45 + min(1.0, fps_eff / 12.0) * 0.42), model_kind, model_version
    if span <= 0.03 and fps_eff <= 2.0:
        return "perched_idle", min(0.9, 0.5 + (1.0 - span) * 0.25), model_kind, model_version
    return "alert", min(0.86, 0.4 + (0.2 + motion) * 0.35), model_kind, model_version


def maybe_predict_video_behavior_video(
    app_config: Any,
    video_detections: list[dict[str, Any]],
    *,
    duration_s: float,
    processor_cwd: str | None = None,
    video_path: str | None = None,
) -> tuple[str | None, float, str, str]:
    """Return (label, confidence, model_kind, model_version) for shadow/runtime."""
    br = app_config.get("processor.behavior_recognition") or {}
    if not isinstance(br, dict) or not bool(br.get("enabled")):
        return None, 0.0, "video_v1_shadow", str(br.get("video_model_version") or "x3d-s-shadow-v0")

    model_kind = str(br.get("video_model_kind") or "video_v1").strip() or "video_v1"
    model_version = str(br.get("video_model_version") or "video-v1").strip() or "video-v1"

    ov_label, ov_conf = _predict_video_openvino(
        app_config,
        video_detections,
        duration_s=duration_s,
        processor_cwd=processor_cwd,
        video_path=video_path,
        br=br,
    )
    if ov_label and ov_conf > 0:
        return ov_label, ov_conf, model_kind, model_version

    # When OpenVINO is configured, avoid rule-proxy labels outside training taxonomy.
    if _resolve_video_openvino_path(br, processor_cwd=processor_cwd) is not None:
        return None, 0.0, model_kind, model_version

    return _predict_video_rules(
        video_detections,
        duration_s=duration_s,
        model_kind=model_kind if model_kind != "video_v1_shadow" else "video_v1_shadow",
        model_version=model_version,
    )
