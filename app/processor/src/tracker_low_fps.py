"""Adaptive ByteTrack YAML for low-FPS streams (SOTA-10)."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from app_config.app_config import app_config
from inference.binary_paths import processor_package_root
from tracker_paths import resolve_tracker_config_path

_LOG = logging.getLogger(__name__)
_CACHE_DIR_NAME = ".adaptive_tracker_cache"


def _parse_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _parse_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_int(cfg: Mapping[str, Any], key: str, default: int) -> int:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def adaptive_track_buffer_frames(
    stream_fps: float,
    *,
    remember_seconds: float,
    min_buffer: int,
    max_buffer: int,
) -> int:
    fps = float(stream_fps) if stream_fps > 0.5 else 7.0
    remember = max(1.0, float(remember_seconds))
    return max(int(min_buffer), min(int(max_buffer), int(round(fps * remember))))


def adaptive_match_thresh(stream_fps: float, base_thresh: float, low_fps_threshold: float) -> float:
    if stream_fps <= 0.5 or stream_fps > float(low_fps_threshold):
        return float(base_thresh)
    # Softer association when detections are sparse.
    return max(0.55, float(base_thresh) - 0.08)


def resolve_adaptive_tracker_path(
    base_tracker: str,
    stream_fps: float,
    runtime_cfg: Mapping[str, Any] | None = None,
) -> str:
    """Return tracker YAML path, optionally materializing FPS-scaled ByteTrack buffer."""
    resolved_base = resolve_tracker_config_path(base_tracker)
    cfg = runtime_cfg if runtime_cfg is not None else app_config.config or {}
    prefix = "processor."
    if not _parse_bool(cfg, f"{prefix}tracker_adaptive_low_fps_enabled", True):
        return resolved_base

    low_fps_threshold = _parse_float(cfg, f"{prefix}tracker_low_fps_threshold", 10.0)
    if stream_fps > low_fps_threshold:
        return resolved_base

    remember_seconds = _parse_float(cfg, f"{prefix}tracker_remember_seconds", 8.0)
    min_buffer = _parse_int(cfg, f"{prefix}tracker_adaptive_min_buffer", 24)
    max_buffer = _parse_int(cfg, f"{prefix}tracker_adaptive_max_buffer", 120)
    buffer_frames = adaptive_track_buffer_frames(
        stream_fps,
        remember_seconds=remember_seconds,
        min_buffer=min_buffer,
        max_buffer=max_buffer,
    )

    base_path = Path(resolved_base)
    if not base_path.is_file():
        return resolved_base

    try:
        doc = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        _LOG.warning("adaptive tracker: cannot read %s: %s", base_path, exc)
        return resolved_base

    if str(doc.get("tracker_type") or "").strip().lower() != "bytetrack":
        return resolved_base

    base_thresh = float(doc.get("match_thresh") or 0.8)
    doc["track_buffer"] = int(buffer_frames)
    doc["match_thresh"] = round(
        adaptive_match_thresh(stream_fps, base_thresh, low_fps_threshold),
        3,
    )

    cache_root = Path(processor_package_root()) / "models" / "tracker" / _CACHE_DIR_NAME
    cache_root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(
        f"{base_path}|fps={stream_fps:.3f}|buf={buffer_frames}|mt={doc['match_thresh']}".encode()
    ).hexdigest()[:16]
    out_path = cache_root / f"bytetrack_adaptive_{key}.yaml"
    if not out_path.is_file():
        out_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return str(out_path.resolve())
