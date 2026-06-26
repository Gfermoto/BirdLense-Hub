"""Canonical paths under ``models/behavior/`` + legacy aliases (#416, #458)."""

from __future__ import annotations

# Relative to app/processor/
META_WEIGHTS = "models/behavior/meta/behavior_logistic_export@v1.json"
VIDEO_DIR = "models/behavior/video"
VIDEO_WEIGHTS = "models/behavior/video/behavior_video_export.json"

_LEGACY_ALIASES: dict[str, str] = {
    "models/behavior/behavior_logistic_export@v1.json": META_WEIGHTS,
    "models/behavior/behavior_video_export.json": VIDEO_WEIGHTS,
    "models/behavior/behavior_video_model.onnx": f"{VIDEO_DIR}/behavior_video_model.onnx",
    "models/behavior": VIDEO_DIR,
}


def normalize_behavior_model_path(raw: str) -> str:
    """Map pre-refactor paths to ``meta/`` or ``video/`` layout."""
    p = (raw or "").strip()
    if not p:
        return p
    return _LEGACY_ALIASES.get(p.replace("\\", "/"), p)
