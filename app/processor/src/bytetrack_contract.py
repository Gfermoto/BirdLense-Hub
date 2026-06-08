"""ByteTrack vs YOLO track(conf) contract checks (#607 F1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

import yaml

from processor_runtime_stats import inc_counter, set_gauge

_LOG = logging.getLogger(__name__)
_logged_keys: set[str] = set()


def inspect_bytetrack_conf_contract(
    tracker_yaml_path: str,
    track_conf: float,
    *,
    stream_fps: float = 0.0,
) -> dict[str, Any]:
    """Return tracker thresholds vs YOLO track(conf); log once per path+conf."""
    out: dict[str, Any] = {
        "tracker_path": tracker_yaml_path,
        "track_conf": round(float(track_conf), 4),
        "stream_fps": round(float(stream_fps), 2),
        "track_high_thresh": None,
        "new_track_thresh": None,
        "track_low_thresh": None,
        "track_buffer": None,
        "contract_ok": True,
        "risk": None,
    }
    path = Path(tracker_yaml_path)
    if not path.is_file():
        out["contract_ok"] = False
        out["risk"] = "tracker_yaml_missing"
        return out
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        out["contract_ok"] = False
        out["risk"] = f"yaml_read_failed:{exc}"
        return out
    if str(doc.get("tracker_type") or "").strip().lower() != "bytetrack":
        out["risk"] = "not_bytetrack"
        return out
    high = float(doc.get("track_high_thresh") or 0.1)
    new = float(doc.get("new_track_thresh") or high)
    low = float(doc.get("track_low_thresh") or 0.05)
    buf = int(doc.get("track_buffer") or 0)
    out["track_high_thresh"] = round(high, 4)
    out["new_track_thresh"] = round(new, 4)
    out["track_low_thresh"] = round(low, 4)
    out["track_buffer"] = buf
    ceiling = max(0.01, float(track_conf) - 0.04)
    if high >= float(track_conf) or new >= float(track_conf):
        out["contract_ok"] = False
        out["risk"] = "thresholds_gte_track_conf"
    elif high > ceiling or new > ceiling:
        out["contract_ok"] = False
        out["risk"] = "thresholds_above_recommended_ceiling"
    set_gauge("bytetrack_track_conf", float(track_conf))
    set_gauge("bytetrack_track_high_thresh", high)
    set_gauge("bytetrack_track_buffer", float(buf))
    return out


def log_bytetrack_conf_contract_once(
    tracker_yaml_path: str,
    track_conf: float,
    *,
    stream_fps: float = 0.0,
) -> dict[str, Any]:
    key = f"{tracker_yaml_path}|{track_conf:.3f}|{stream_fps:.1f}"
    info = inspect_bytetrack_conf_contract(
        tracker_yaml_path,
        track_conf,
        stream_fps=stream_fps,
    )
    if key in _logged_keys:
        return info
    _logged_keys.add(key)
    if info.get("contract_ok"):
        _LOG.info(
            "ByteTrack contract ok path=%s track_conf=%.3f high=%s new=%s buffer=%s fps=%.1f",
            tracker_yaml_path,
            float(track_conf),
            info.get("track_high_thresh"),
            info.get("new_track_thresh"),
            info.get("track_buffer"),
            float(stream_fps),
        )
    else:
        inc_counter("bytetrack_conf_contract_risk_total")
        _LOG.warning(
            "ByteTrack contract RISK path=%s track_conf=%.3f high=%s new=%s risk=%s "
            "(keep high/new ~0.04 below track conf)",
            tracker_yaml_path,
            float(track_conf),
            info.get("track_high_thresh"),
            info.get("new_track_thresh"),
            info.get("risk"),
        )
    return info
