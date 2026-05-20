#!/usr/bin/env python3
"""Fail if production configs re-enable deprecated cascade thresholds (SOTA 2.0)."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    raise SystemExit(1)

REPO = Path(__file__).resolve().parents[1]
CONFIG_PATHS = [
    REPO / "app" / "app_config" / "default_config.yaml",
    REPO / "app" / "app_config" / "user_config.yaml",
]

# Keys that must stay false when scoring_engine is enabled.
LEGACY_BOOL_KEYS = [
    ("processor", "motion_verified_detection_enabled"),
    ("processor", "background_subtraction_enabled"),
    ("processor", "static_object_suppression_enabled"),
]

# Forbidden in user_config when scoring is on (defaults may list for migration docs).
DEPRECATED_SCALAR_KEYS = [
    ("processor", "static_square_hard_reject_max_conf"),
    ("processor", "motion_global_max_mean_absdiff"),
]


def _get_nested(data: dict, path: tuple[str, str]) -> object:
    cur: object = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def main() -> int:
    errors: list[str] = []
    for path in CONFIG_PATHS:
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        scoring_on = bool(_get_nested(data, ("processor", "scoring_engine_enabled")))
        if not scoring_on:
            continue
        for section, key in LEGACY_BOOL_KEYS:
            val = _get_nested(data, (section, key))
            if val is True:
                errors.append(f"{path.name}: {section}.{key}=true conflicts with scoring_engine_enabled")
        if path.name != "default_config.yaml":
            for section, key in DEPRECATED_SCALAR_KEYS:
                if _get_nested(data, (section, key)) is not None:
                    errors.append(
                        f"{path.name}: deprecated {section}.{key} — remove; use scoring_* thresholds"
                    )
        det = data.get("detection") if isinstance(data.get("detection"), dict) else {}
        if det.get("frigate_standalone_when_no_yolo") is True:
            errors.append(
                f"{path.name}: detection.frigate_standalone_when_no_yolo=true — use Frigate as prior only"
            )
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print("legacy processor config check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
