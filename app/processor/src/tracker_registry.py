"""Tracker backend presets for ByteTrack / BoT-SORT (SOTA-12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from tracker_paths import resolve_tracker_config_path

# Ultralytics 8.x: tracker_type in YAML is bytetrack | botsort only.
SUPPORTED_TRACKER_TYPES = frozenset({"bytetrack", "botsort"})


@dataclass(frozen=True)
class TrackerPreset:
    """Named tracker profile resolved to Ultralytics tracker YAML."""

    id: str
    yaml_rel: str
    tracker_type: str
    description: str

    def resolve_path(self) -> str:
        return resolve_tracker_config_path(self.yaml_rel)


TRACKER_PRESETS: dict[str, TrackerPreset] = {
    "bytetrack_birdlense": TrackerPreset(
        id="bytetrack_birdlense",
        yaml_rel="models/tracker/bytetrack_birdlense.yaml",
        tracker_type="bytetrack",
        description="BirdLense ByteTrack (default live/regen)",
    ),
    "bytetrack_birdlense_lowfps": TrackerPreset(
        id="bytetrack_birdlense_lowfps",
        yaml_rel="models/tracker/bytetrack_birdlense.yaml",
        tracker_type="bytetrack",
        description="Alias → bytetrack_birdlense (adaptive low-FPS)",
    ),
    "botsort_birdlense": TrackerPreset(
        id="botsort_birdlense",
        yaml_rel="models/tracker/botsort_birdlense.yaml",
        tracker_type="botsort",
        description="BoT-SORT with BirdLense thresholds (no ReID)",
    ),
}


def list_tracker_presets() -> list[dict[str, str]]:
    return [
        {
            "id": p.id,
            "tracker_type": p.tracker_type,
            "yaml": p.yaml_rel,
            "description": p.description,
        }
        for p in TRACKER_PRESETS.values()
    ]


def resolve_tracker_preset(name: str | None) -> str:
    """Map preset id or yaml path to path/name for Ultralytics track()."""
    key = str(name or "").strip()
    if not key:
        key = "bytetrack_birdlense"
    preset = TRACKER_PRESETS.get(key)
    if preset is not None:
        return preset.resolve_path()
    return resolve_tracker_config_path(key)


def preset_for_config(cfg: Mapping[str, object] | None) -> TrackerPreset | None:
    raw = None
    if cfg is not None:
        raw = cfg.get("processor.tracker_preset") or cfg.get("processor.tracker")
    key = str(raw or "").strip()
    if not key:
        return TRACKER_PRESETS["bytetrack_birdlense"]
    if key in TRACKER_PRESETS:
        return TRACKER_PRESETS[key]
    for p in TRACKER_PRESETS.values():
        if key.endswith(p.yaml_rel) or key == p.yaml_rel:
            return p
    return None
