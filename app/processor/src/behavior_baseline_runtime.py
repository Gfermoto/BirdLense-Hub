"""Video-level behavior baseline: numpy softmax over sklearn-exported weights (#416)."""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any

import numpy as np

_log = logging.getLogger(__name__)

_EXPORT_SCHEMA = "behavior_logistic_export@v1"


def _softmax(logits: np.ndarray) -> np.ndarray:
    x = logits.astype(np.float64)
    x = x - np.max(x)
    e = np.exp(x)
    return e / (np.sum(e) + 1e-12)


def manifest_row_meta_features(row: dict[str, Any]) -> list[float]:
    """Same 3-vector as training from manifest video row."""
    frame_rows = float(row.get("frame_rows") or 0)
    subject_count = float(row.get("subject_count") or 0)
    species = row.get("species_names") or []
    nsp = float(len(species)) if isinstance(species, list) else 0.0
    return [
        math.log1p(max(0.0, frame_rows)),
        subject_count / 20.0,
        nsp / 10.0,
    ]


def runtime_meta_features(
    video_detections: list[dict[str, Any]],
    *,
    duration_s: float,
    max_detections: int = 50,
) -> list[float]:
    """Proxy aligned with manifest_row_meta_features (domain gap possible)."""
    dets = video_detections[: max(1, int(max_detections))]
    t_frames = 0.0
    for d in dets:
        frames = d.get("frames") or []
        if isinstance(frames, list):
            t_frames += float(len(frames))
        elif isinstance(frames, str) and frames:
            try:
                parsed = json.loads(frames)
                if isinstance(parsed, list):
                    t_frames += float(len(parsed))
            except json.JSONDecodeError:
                pass
    n_dets = float(len(dets))
    species = {str(d.get("species_name") or d.get("species") or "").strip().lower() for d in dets}
    species.discard("")
    return [
        math.log1p(max(0.0, t_frames)),
        n_dets / 20.0,
        float(len(species)) / 10.0,
    ]


def _resolve_weights_path(raw: str, *, processor_cwd: str | None) -> Path | None:
    p = (raw or "").strip()
    if not p:
        return None
    path = Path(p)
    if path.is_file():
        return path.resolve()
    roots = []
    if processor_cwd:
        roots.append(Path(processor_cwd))
    roots.append(Path(__file__).resolve().parents[1])
    for root in roots:
        cand = (root / p).resolve()
        if cand.is_file():
            return cand
    env = (os.environ.get("BIRDLENSE_BEHAVIOR_WEIGHTS_PATH") or "").strip()
    if env:
        pe = Path(env).expanduser()
        if pe.is_file():
            return pe.resolve()
    return None


def resolve_behavior_inference_backend(app_config: Any, *, processor_cwd: str | None) -> str:
    """logistic_json | openvino | auto (если есть IR/ONNX и метки из weights_path)."""
    raw_env = (os.environ.get("BIRDLENSE_BEHAVIOR_INFERENCE_BACKEND") or "").strip().lower()
    br_raw = app_config.get("processor.behavior_recognition") if app_config else None
    br = br_raw if isinstance(br_raw, dict) else {}
    raw_cfg = str(br.get("inference_backend") or "").strip().lower()
    raw = raw_env or raw_cfg or "auto"
    if raw in ("json", "logistic", "logistic_json"):
        return "logistic_json"
    if raw == "openvino":
        return "openvino"
    # auto
    try:
        from inference.selector import openvino_runtime_available

        from behavior_openvino_runtime import resolve_behavior_openvino_model_path
    except ImportError:
        return "logistic_json"
    if not openvino_runtime_available():
        return "logistic_json"
    ov_path = resolve_behavior_openvino_model_path(app_config, processor_cwd=processor_cwd)
    if ov_path is None:
        return "logistic_json"
    wpath = str(br.get("weights_path") or "").strip()
    if _export_labels_for_weights(wpath, processor_cwd=processor_cwd):
        return "openvino"
    return "logistic_json"


def _export_labels_for_weights(weights_path: str, *, processor_cwd: str | None) -> list[str]:
    resolved = _resolve_weights_path(weights_path, processor_cwd=processor_cwd)
    if resolved is None:
        return []
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if str(payload.get("schema") or "") != _EXPORT_SCHEMA:
            return []
        return [str(x) for x in (payload.get("labels") or []) if str(x)]
    except Exception:
        return []


class BehaviorBaselineRuntime:
    """Loads once; thread-safe enough for single-threaded processor."""

    def __init__(self) -> None:
        self._export: dict[str, Any] | None = None
        self._path: str | None = None

    def load_if_needed(self, weights_path: str, *, processor_cwd: str | None = None) -> bool:
        resolved = _resolve_weights_path(weights_path, processor_cwd=processor_cwd)
        if resolved is None:
            self._export = None
            self._path = None
            return False
        key = str(resolved)
        if self._export is not None and self._path == key:
            return True
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if str(payload.get("schema") or "") != _EXPORT_SCHEMA:
            _log.warning("behavior weights: bad schema in %s", key)
            self._export = None
            self._path = None
            return False
        self._export = payload
        self._path = key
        return True

    def predict_video(
        self,
        video_detections: list[dict[str, Any]],
        *,
        duration_s: float,
        max_detections: int = 50,
    ) -> tuple[str | None, float]:
        if not self._export or not video_detections:
            return None, 0.0
        labels = [str(x) for x in (self._export.get("labels") or []) if str(x)]
        coef = self._export.get("coef") or []
        intercept = self._export.get("intercept") or []
        if not labels or not coef or not intercept:
            return None, 0.0
        x = np.array(
            [runtime_meta_features(video_detections, duration_s=float(duration_s), max_detections=max_detections)],
            dtype=np.float64,
        )
        w = np.array(coef, dtype=np.float64)
        b = np.array(intercept, dtype=np.float64).reshape(-1)
        if w.ndim != 2 or w.shape[0] != len(labels) or w.shape[1] != x.shape[1] or b.shape[0] != len(labels):
            _log.warning(
                "behavior weights: shape mismatch coef=%s bias=%s x=%s labels=%s",
                getattr(w, "shape", None),
                b.shape,
                x.shape,
                len(labels),
            )
            return None, 0.0
        logits = (x @ w.T).reshape(-1) + b
        probs = _softmax(logits)
        idx = int(np.argmax(probs))
        return labels[idx], float(probs[idx])


_RUNTIME = BehaviorBaselineRuntime()


def maybe_predict_video_behavior(
    app_config: Any,
    video_detections: list[dict[str, Any]],
    *,
    duration_s: float,
    processor_cwd: str | None = None,
) -> tuple[str | None, float]:
    """Return (label, confidence) or (None, 0) if disabled / missing weights."""
    br = app_config.get("processor.behavior_recognition") or {}
    if not isinstance(br, dict) or not bool(br.get("enabled")):
        return None, 0.0
    path = str(br.get("weights_path") or "").strip()
    if not path:
        return None, 0.0

    try:
        max_det = int(br.get("max_runtime_detections") or 50)
    except (TypeError, ValueError):
        max_det = 50
    max_det = max(1, min(max_det, 500))

    backend = resolve_behavior_inference_backend(app_config, processor_cwd=processor_cwd)
    fallback_ov = bool(br.get("openvino_fallback_logistic", True))

    if backend == "openvino":
        try:
            from behavior_openvino_runtime import (
                maybe_predict_video_behavior_openvino,
                resolve_behavior_openvino_model_path,
            )
        except ImportError:
            maybe_predict_video_behavior_openvino = None  # type: ignore[misc,assignment]
            resolve_behavior_openvino_model_path = None  # type: ignore[misc,assignment]

        if maybe_predict_video_behavior_openvino and resolve_behavior_openvino_model_path:
            ov_path = resolve_behavior_openvino_model_path(app_config, processor_cwd=processor_cwd)
            labels_ov = _export_labels_for_weights(path, processor_cwd=processor_cwd)
            if ov_path is not None and labels_ov:
                bl, bc = maybe_predict_video_behavior_openvino(
                    app_config,
                    video_detections,
                    duration_s=float(duration_s),
                    processor_cwd=processor_cwd,
                    onnx_or_xml_path=ov_path,
                    labels=labels_ov,
                    max_detections=max_det,
                )
                if bl and bc > 0:
                    return bl, float(bc)
        if not fallback_ov:
            return None, 0.0

    if not _RUNTIME.load_if_needed(path, processor_cwd=processor_cwd):
        return None, 0.0
    return _RUNTIME.predict_video(video_detections, duration_s=float(duration_s), max_detections=max_det)
