"""Adaptive ByteTrack YAML for low-FPS streams (SOTA-10)."""

from __future__ import annotations

import hashlib
import logging
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
    # Slight tighten on low FPS; large bumps break small-motion association.
    return min(0.88, max(0.68, float(base_thresh) + 0.02))


def _track_conf_cap_from_config(cfg: Mapping[str, Any]) -> float | None:
    """Upper bound for ByteTrack high/new thresholds (must stay below YOLO track conf)."""
    cap: float | None = None
    for key in (
        "processor.min_confidence_binary",
        "processor.min_confidence_binary_bird",
    ):
        try:
            raw = cfg.get(key)
            if raw is None:
                continue
            val = float(raw)
        except (TypeError, ValueError):
            continue
        cap = min(cap, val) if cap is not None else val
    if cap is None:
        cap = 0.22
    backend = str(cfg.get("processor.inference_backend") or "").strip().lower()
    if backend == "openvino":
        raw = cfg.get("processor.openvino_binary_track_ultralytics_conf")
        if raw is not None:
            try:
                ov = float(raw)
                cap = min(cap, ov) if cap is not None else ov
            except (TypeError, ValueError):
                pass
    if cap is None:
        return None
    return max(0.05, min(0.45, float(cap)))


def clamp_bytetrack_track_thresholds(doc: dict[str, Any], track_conf_cap: float | None) -> None:
    """Ensure track_high_thresh/new_track_thresh < Ultralytics track(conf)."""
    if track_conf_cap is None or str(doc.get("tracker_type") or "").strip().lower() != "bytetrack":
        return
    ceiling = max(0.01, float(track_conf_cap) - 0.04)
    for key in ("track_high_thresh", "new_track_thresh"):
        try:
            cur = float(doc.get(key) or 0.1)
        except (TypeError, ValueError):
            cur = 0.1
        doc[key] = round(min(cur, ceiling), 4)
    try:
        low = float(doc.get("track_low_thresh") or 0.05)
    except (TypeError, ValueError):
        low = 0.05
    doc["track_low_thresh"] = round(min(low, doc["track_high_thresh"] * 0.75), 4)


def _tracker_doc_materialized(base_doc: dict[str, Any], doc: dict[str, Any]) -> bool:
    keys = (
        "track_buffer",
        "match_thresh",
        "track_high_thresh",
        "new_track_thresh",
        "track_low_thresh",
    )
    for key in keys:
        if base_doc.get(key) != doc.get(key):
            return True
    return False


def _materialize_adaptive_tracker(
    base_path: Path,
    doc: dict[str, Any],
    stream_fps: float,
    *,
    track_conf_cap: float | None,
) -> str:
    cache_root = Path(processor_package_root()) / "models" / "tracker" / _CACHE_DIR_NAME
    cache_root.mkdir(parents=True, exist_ok=True)
    cap_tag = f"{track_conf_cap:.3f}" if track_conf_cap is not None else "na"
    key = hashlib.sha256(
        f"{base_path}|fps={stream_fps:.3f}|buf={doc.get('track_buffer')}|mt={doc.get('match_thresh')}|cap={cap_tag}|"
        f"th={doc.get('track_high_thresh')}|{doc.get('new_track_thresh')}".encode()
    ).hexdigest()[:16]
    out_path = cache_root / f"bytetrack_adaptive_{key}.yaml"
    if not out_path.is_file():
        out_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return str(out_path.resolve())


def resolve_adaptive_tracker_path(
    base_tracker: str,
    stream_fps: float,
    runtime_cfg: Mapping[str, Any] | None = None,
) -> str:
    """Return tracker YAML path; clamp ByteTrack thresholds for any FPS when YOLO track conf is low."""
    resolved_base = resolve_tracker_config_path(base_tracker)
    cfg = runtime_cfg if runtime_cfg is not None else app_config.config or {}
    prefix = "processor."
    base_path = Path(resolved_base)
    if not base_path.is_file():
        return resolved_base

    try:
        base_doc = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        _LOG.warning("adaptive tracker: cannot read %s: %s", base_path, exc)
        return resolved_base

    if str(base_doc.get("tracker_type") or "").strip().lower() != "bytetrack":
        return resolved_base

    doc = dict(base_doc)
    track_conf_cap = _track_conf_cap_from_config(cfg)
    adaptive_enabled = _parse_bool(cfg, f"{prefix}tracker_adaptive_low_fps_enabled", True)
    low_fps_threshold = _parse_float(cfg, f"{prefix}tracker_low_fps_threshold", 10.0)

    if adaptive_enabled and stream_fps <= low_fps_threshold:
        remember_seconds = _parse_float(cfg, f"{prefix}tracker_remember_seconds", 8.0)
        min_buffer = _parse_int(cfg, f"{prefix}tracker_adaptive_min_buffer", 24)
        max_buffer = _parse_int(cfg, f"{prefix}tracker_adaptive_max_buffer", 120)
        buffer_frames = adaptive_track_buffer_frames(
            stream_fps,
            remember_seconds=remember_seconds,
            min_buffer=min_buffer,
            max_buffer=max_buffer,
        )
        base_thresh = float(doc.get("match_thresh") or 0.8)
        doc["track_buffer"] = int(buffer_frames)
        doc["match_thresh"] = round(
            adaptive_match_thresh(stream_fps, base_thresh, low_fps_threshold),
            3,
        )

    clamp_bytetrack_track_thresholds(doc, track_conf_cap)
    if not _tracker_doc_materialized(base_doc, doc):
        return resolved_base
    return _materialize_adaptive_tracker(
        base_path,
        doc,
        stream_fps,
        track_conf_cap=track_conf_cap,
    )
