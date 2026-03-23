#!/usr/bin/env python3
"""Fail CI when new config keys are not wired into Settings UI.

Policy:
- Every terminal key from app/app_config/default_config.yaml must be either:
  1) mapped to a <form.Field name="..."> in SettingsForm.tsx, or
  2) explicitly listed in ALLOWED_NON_UI_KEYS with a reason.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "app" / "app_config" / "default_config.yaml"
SETTINGS_FORM_PATH = ROOT / "app" / "ui" / "src" / "pages" / "Settings" / "SettingsForm.tsx"


# Intentionally hidden from Settings UI.
# Keep this list short and explicit; add reason in the comment above key block.
ALLOWED_NON_UI_KEYS = {
    # Processor internals: model paths/strategy are deployment-level and can break runtime if edited casually.
    "processor.detection_strategy",
    "processor.models.single_stage",
    "processor.models.binary",
    "processor.models.classifier",
    "processor.regional_species",
    "processor.included_bird_families",
    "processor.save_images",
    # Motion fine-tuning kept as config-level for now.
    "motion.frigate_camera_filter",
    "motion.frigate_label_filter",
    # Merge internals not yet presented in UI as separate controls.
    "detection.merge_window_seconds",
    "detection.dedup_window_seconds",
    "detection.one_per_species",
    "detection.source_priority",
    "detection.species_mapping",
    "detection.min_confidence_to_store",
    # Ops/security-sensitive/infra-generated values.
    "notifications.telegram_api_base",
    "notifications.telegram_timeout",
    "notifications.telegram_retries",
    "notifications.compress_photo_over_kb",
    "notifications.telegram_max_side_px",
    "web_push.enabled",
    "web_push.vapid_public_key",
    "web_push.vapid_private_key",
    # Runtime control still config-level.
    "video.source",
    "video.pre_record_seconds",
    "video.auto_reconnect",
    "retention.days",
    "ebird.protocol",
}

TERMINAL_MAP_KEYS = {
    # Mapping dictionaries are edited as one textarea in UI.
    "detection.species_mapping",
    "ebird.species_mapping",
}


def _collect_terminal_keys(obj: object, prefix: str = "") -> list[str]:
    """Collect dot-keys; treat scalar/list and selected map keys as terminal."""
    if isinstance(obj, dict):
        if prefix in TERMINAL_MAP_KEYS:
            return [prefix] if prefix else []
        keys: list[str] = []
        for k, v in obj.items():
            next_prefix = f"{prefix}.{k}" if prefix else str(k)
            keys.extend(_collect_terminal_keys(v, next_prefix))
        return keys
    if isinstance(obj, list):
        return [prefix] if prefix else []
    return [prefix] if prefix else []


def _load_form_fields() -> set[str]:
    text = SETTINGS_FORM_PATH.read_text(encoding="utf-8")
    return set(re.findall(r'form\.Field name="([^"]+)"', text))


def main() -> int:
    cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    config_keys = {k for k in _collect_terminal_keys(cfg) if k}
    form_fields = _load_form_fields()
    missing = sorted(config_keys - form_fields - ALLOWED_NON_UI_KEYS)

    if missing:
        print("Settings UI coverage check FAILED.")
        print("These config keys are not in Settings UI and not allowlisted:")
        for key in missing:
            print(f"  - {key}")
        print("\nEither add form fields in SettingsForm.tsx or add explicit allowlist entries.")
        return 1

    print(
        "Settings UI coverage OK: "
        f"{len(config_keys)} config keys, {len(form_fields)} UI fields, "
        f"{len(ALLOWED_NON_UI_KEYS)} allowlisted non-UI keys."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
