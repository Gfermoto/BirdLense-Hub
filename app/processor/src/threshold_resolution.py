"""Central threshold hierarchy: global → role → camera → adaptive (cannot raise above role/camera)."""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Acceptance floors: lower = more sensitive. Adaptive/night must not raise above role/camera.
THRESHOLD_ACCEPTANCE_KEYS: frozenset[str] = frozenset(
    {
        "min_confidence_binary",
        "min_confidence_binary_bird",
        "min_confidence_binary_rodent",
        "min_confidence_binary_squirrel",
        "openvino_min_confidence_binary_bird",
        "openvino_binary_track_ultralytics_conf",
        "min_confidence_to_process",
        "min_confidence_to_store",
        "scoring_default_low_threshold",
        "scoring_relaxed_min_confidence",
        "generic_bird_min_detector_conf",
        "auto_unstick_min_confidence_binary",
        "auto_unstick_min_confidence_binary_bird",
        "detect_first_frigate_assist_min_confidence",
        "static_scene_bird_min_confidence",
        "static_scene_bird_like_min_confidence",
    }
)

# OpenVINO caps pair with base bird/binary keys — effective = min(base, cap), never max().
OPENVINO_CAP_PAIRS: tuple[tuple[str, str], ...] = (
    ("min_confidence_binary_bird", "openvino_min_confidence_binary_bird"),
    ("min_confidence_binary", "openvino_min_confidence_binary_bird"),
)


def _parse_optional_float(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip().lower() in ("", "null", "none"):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def resolve_camera_tuning_role(app_config: Any, camera_id: str | None) -> str | None:
    cam = str(camera_id or "").strip()
    if not cam:
        return None
    try:
        from app_config.cameras import get_valid_cameras
    except ImportError:
        return None
    video = app_config.get("video") if hasattr(app_config, "get") else {}
    cameras = get_valid_cameras(video_config=(video or {}))
    for row in cameras:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "").strip()
        legacy_id = str(row.get("legacy_id") or "").strip()
        if cam not in {row_id, legacy_id}:
            continue
        role = str(row.get("tuning_role") or "").strip()
        return role or None
    return None


def _role_preset_dict(app_config: Any, role: str | None) -> dict[str, Any]:
    if not role:
        return {}
    raw = app_config.get(f"processor.camera_tuning_by_role.{role}")
    return dict(raw) if isinstance(raw, dict) else {}


def _camera_override_dict(app_config: Any, camera_id: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    legacy = app_config.get(f"detection.camera_overrides.{camera_id}")
    if isinstance(legacy, dict):
        merged.update(dict(legacy))
    raw = app_config.get(f"processor.camera_overrides.{camera_id}")
    if isinstance(raw, dict):
        merged.update(dict(raw))
    return merged


def _global_processor_value(app_config: Any, key: str) -> float | None:
    return _parse_optional_float(app_config.get(f"processor.{key}"))


def resolve_effective_threshold(
    app_config: Any,
    key: str,
    *,
    camera_id: str | None = None,
    inference_backend: str | None = None,
    adaptive_overrides: Mapping[str, Any] | None = None,
) -> float | None:
    """Single entry: global → role → camera; adaptive cannot raise acceptance keys."""
    short = key.split(".", 1)[1] if key.startswith("processor.") else key
    role = resolve_camera_tuning_role(app_config, camera_id)
    role_preset = _role_preset_dict(app_config, role)
    cam_over = _camera_override_dict(app_config, str(camera_id or "").strip()) if camera_id else {}

    effective: float | None = None
    if short in cam_over:
        effective = _parse_optional_float(cam_over[short])
    if effective is None and short in role_preset:
        effective = _parse_optional_float(role_preset[short])
    if effective is None:
        effective = _global_processor_value(app_config, short)

    if effective is None:
        return None

    # Adaptive (night profile): min() — never raise above role/camera-resolved value.
    if adaptive_overrides and short in adaptive_overrides:
        adv = _parse_optional_float(adaptive_overrides[short])
        if adv is not None and short in THRESHOLD_ACCEPTANCE_KEYS:
            effective = min(float(effective), adv)

    if (inference_backend or "").strip().lower() == "openvino":
        for base_key, cap_key in OPENVINO_CAP_PAIRS:
            if short != base_key:
                continue
            cap = _parse_optional_float(
                cam_over.get(cap_key)
                if cap_key in cam_over
                else role_preset.get(cap_key)
                if cap_key in role_preset
                else app_config.get(f"processor.{cap_key}")
            )
            if cap is not None:
                cap = max(0.001, min(0.99, float(cap)))
                effective = min(float(effective), cap)
            break

    return effective


def _recording_path_match_candidates(video_path: str) -> list[str]:
    """Suffixes for matching ``video.video_path`` rows (relative/absolute layouts)."""
    raw = str(video_path or "").strip().replace("\\", "/")
    if not raw:
        return []
    out: list[str] = []
    for candidate in (raw, raw.lstrip("/")):
        if candidate and candidate not in out:
            out.append(candidate)
        if "/data/recordings/" in candidate:
            tail = candidate.split("/data/recordings/", 1)[1]
            for variant in (tail, f"recordings/{tail}", f"data/recordings/{tail}"):
                if variant not in out:
                    out.append(variant)
        base = os.path.basename(candidate)
        if base and base not in out:
            out.append(base)
    return out


def _default_sqlite_db_path(app_config: Any) -> str | None:
    env = (os.environ.get("BIRDLENSE_DB_PATH") or "").strip()
    if env and os.path.isfile(env):
        return env
    try:
        from session_state_repository import _db_path

        p = str(_db_path())
        if os.path.isfile(p):
            return p
    except ImportError:
        pass
    try:
        from processor_support import get_data_dir

        p = os.path.join(get_data_dir(), "db", "birdlense.db")
        if os.path.isfile(p):
            return p
    except ImportError:
        pass
    proc_root = Path(__file__).resolve().parents[1]
    for rel in ("data/db/birdlense.db", "../data/db/birdlense.db"):
        p = (proc_root / rel).resolve()
        if p.is_file():
            return str(p)
    return None


def resolve_camera_id_for_recording_path(
    app_config: Any,
    video_path: str,
    *,
    db_path: str | None = None,
) -> str | None:
    """Resolve camera id for offline regen/smoke so role presets match live."""
    path = str(video_path or "").strip()
    if not path:
        return None
    db = str(db_path or _default_sqlite_db_path(app_config) or "").strip()
    if db and os.path.isfile(db):
        try:
            conn = sqlite3.connect(db, timeout=5.0)
            try:
                cur = conn.cursor()
                for suffix in _recording_path_match_candidates(path):
                    row = cur.execute(
                        "SELECT camera_id FROM video "
                        "WHERE camera_id IS NOT NULL AND TRIM(camera_id) != '' "
                        "AND (video_path = ? OR video_path LIKE ? OR video_path LIKE ?) "
                        "ORDER BY id DESC LIMIT 1",
                        (suffix, f"%/{suffix}", f"%{suffix}"),
                    ).fetchone()
                    if row and row[0]:
                        cam = str(row[0]).strip()
                        if cam:
                            return cam
            finally:
                conn.close()
        except sqlite3.Error:
            logger.debug("resolve_camera_id_for_recording_path: sqlite lookup failed", exc_info=True)
    try:
        from app_config.cameras import get_valid_cameras

        cameras = get_valid_cameras(video_config=(app_config.get("video") or {}))
        ids = [str(c.get("id") or "").strip() for c in cameras if str(c.get("id") or "").strip()]
        if len(ids) == 1:
            return ids[0]
    except ImportError:
        pass
    return None


def build_camera_processor_overrides(app_config: Any, camera_id: str | None) -> dict[str, Any]:
    """Per-camera runtime overrides: role preset → legacy detection → processor.camera_overrides."""
    cam = str(camera_id or "").strip()
    if not cam:
        return {}
    merged: dict[str, Any] = {}
    try:
        from app_config.cameras import get_valid_cameras
    except ImportError:
        get_valid_cameras = None  # type: ignore

    if get_valid_cameras is not None:
        cameras = get_valid_cameras(video_config=(app_config.get("video") or {}))
        if isinstance(cameras, list):
            for row in cameras:
                if not isinstance(row, dict):
                    continue
                if str(row.get("id") or "").strip() != cam:
                    continue
                zones = row.get("detection_interest_zones")
                if zones is not None:
                    merged["detection_interest_zones"] = zones
                    merged["detection_interest_zones_required"] = bool(zones)
                break

    role = resolve_camera_tuning_role(app_config, cam)
    role_preset = _role_preset_dict(app_config, role)
    if role_preset:
        merged.update(role_preset)
    merged.update(_camera_override_dict(app_config, cam))
    return merged


def merge_adaptive_profile_overrides(
    camera_overrides: Mapping[str, Any],
    adaptive_overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge adaptive under camera: role/camera wins non-acceptance keys; acceptance uses min()."""
    out = dict(adaptive_overrides or {})
    for key, raw in dict(camera_overrides or {}).items():
        if key not in THRESHOLD_ACCEPTANCE_KEYS:
            out[key] = raw
            continue
        base = _parse_optional_float(raw)
        if base is None:
            continue
        adv = _parse_optional_float(out.get(key))
        out[key] = min(float(base), float(adv)) if adv is not None else base
    return out
