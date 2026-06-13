#!/usr/bin/env python3
"""Remove prod user_config threshold band-aids; rely on default_config role presets + code.

Run on VPS (backs up first):
  python3 scripts/clean_prod_user_config_fullrestore.py
  cd app && docker compose up -d --force-recreate birdlense
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)

BACKUP_SUFFIX = "user_config.yaml.bak.20260611_fullrestore"

# Global processor keys that fight camera_tuning_by_role / threshold_resolution.
PROCESSOR_GLOBAL_REMOVE = frozenset(
    {
        "min_confidence_binary",
        "min_confidence_binary_bird",
        "min_confidence_binary_rodent",
        "min_confidence_binary_squirrel",
        "openvino_min_confidence_binary_bird",
        "openvino_binary_track_ultralytics_conf",
        "min_confidence_to_process",
        "scoring_default_low_threshold",
        "scoring_default_high_threshold",
        "static_scene_bird_min_confidence",
        "static_scene_bird_like_min_confidence",
        "track_regen_min_confidence_binary",
        "track_regen_min_confidence_binary_bird",
    }
)

NIGHT_OVERRIDE_REMOVE = frozenset(
    {
        "min_confidence_binary",
        "min_confidence_binary_bird",
        "min_confidence_to_process",
        "openvino_min_confidence_binary_bird",
        "generic_bird_min_detector_conf",
    }
)

ROLE_CONFIDENCE_REMOVE = frozenset(
    {
        "min_confidence_binary",
        "min_confidence_binary_bird",
        "min_confidence_to_process",
        "openvino_min_confidence_binary_bird",
        "openvino_binary_track_ultralytics_conf",
    }
)

FEEDER_CLOSE_ROLE_EXTRA_REMOVE = frozenset({"min_track_duration"})

FEEDER_FAR_ROLE_EXTRA_REMOVE = frozenset(
    {
        "min_confidence_binary_bird",
        "track_static_reject_enabled",
        "track_static_reject_max_center_dispersion_norm",
        "track_static_reject_max_relative_center_dispersion",
        "track_static_reject_min_duration_sec",
        "track_static_reject_min_frames",
        "track_static_reject_min_frames_sparse",
    }
)


def _cfg_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    local = root / "app" / "app_config" / "user_config.yaml"
    if local.is_file():
        return local
    remote = Path("/app/app_config/user_config.yaml")
    if remote.is_file():
        return remote
    raise FileNotFoundError("user_config.yaml not found")


def _strip_keys(mapping: dict, keys: frozenset[str]) -> list[str]:
    removed: list[str] = []
    for key in keys:
        if key in mapping:
            del mapping[key]
            removed.append(key)
    return removed


def clean(data: dict) -> list[str]:
    changes: list[str] = []
    proc = data.get("processor")
    if not isinstance(proc, dict):
        return changes

    for key in _strip_keys(proc, PROCESSOR_GLOBAL_REMOVE):
        changes.append(f"processor.{key}")

    adaptive = proc.get("adaptive_profiles")
    if isinstance(adaptive, dict):
        night = adaptive.get("night")
        if isinstance(night, dict):
            overrides = night.get("overrides")
            if isinstance(overrides, dict):
                for key in _strip_keys(overrides, NIGHT_OVERRIDE_REMOVE):
                    changes.append(f"processor.adaptive_profiles.night.overrides.{key}")

    roles = proc.get("camera_tuning_by_role")
    if isinstance(roles, dict):
        close = roles.get("feeder_close")
        if isinstance(close, dict):
            for key in _strip_keys(close, ROLE_CONFIDENCE_REMOVE):
                changes.append(f"processor.camera_tuning_by_role.feeder_close.{key}")
            for key in _strip_keys(close, FEEDER_CLOSE_ROLE_EXTRA_REMOVE):
                changes.append(f"processor.camera_tuning_by_role.feeder_close.{key}")
        far = roles.get("feeder_far")
        if isinstance(far, dict):
            for key in _strip_keys(far, ROLE_CONFIDENCE_REMOVE):
                changes.append(f"processor.camera_tuning_by_role.feeder_far.{key}")
            for key in _strip_keys(far, FEEDER_FAR_ROLE_EXTRA_REMOVE):
                changes.append(f"processor.camera_tuning_by_role.feeder_far.{key}")

    return changes


def main() -> int:
    path = _cfg_path()
    backup = path.with_name(BACKUP_SUFFIX)
    if not backup.is_file():
        shutil.copy2(path, backup)
        print(f"backup: {backup}")
    else:
        print(f"backup exists: {backup}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    changes = clean(data)
    if not changes:
        print("nothing to remove (already clean)")
        return 0

    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"cleaned {path} ({len(changes)} keys):")
    for line in sorted(changes):
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
