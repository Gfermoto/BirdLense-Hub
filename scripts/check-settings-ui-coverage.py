#!/usr/bin/env python3
"""Fail CI when new config keys are not wired into Settings UI.

Policy:
- Every terminal key from app/app_config/default_config.yaml must be either:
  1) mapped to a <form.Field name="..."> in SettingsForm.tsx, or
  2) explicitly listed in ALLOWED_NON_UI_KEYS with a reason.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "app" / "app_config" / "default_config.yaml"
SETTINGS_FORM_PATH = ROOT / "app" / "ui" / "src" / "pages" / "Settings" / "SettingsForm.tsx"


# Intentionally hidden from Settings UI.
# Keep this list short and explicit; every key must have
# - category: why it's non-UI today
# - reason: current rationale
# - next_step: when/how to revisit
ALLOWED_NON_UI_KEYS: dict[str, dict[str, str]] = {
    # Processor internals.
    "processor.detection_strategy": {
        "category": "advanced",
        "reason": "Deployment-level model strategy; unsafe for casual UI edits.",
        "next_step": "Expose behind Advanced/Expert mode after UX spec.",
    },
    "processor.models.single_stage": {
        "category": "ops-only",
        "reason": "Model path is environment/deployment-specific.",
        "next_step": "Keep config-level; expose only if model manager is introduced.",
    },
    "processor.models.binary": {
        "category": "ops-only",
        "reason": "Model path is environment/deployment-specific.",
        "next_step": "Keep config-level; expose only if model manager is introduced.",
    },
    "processor.models.classifier": {
        "category": "ops-only",
        "reason": "Model path is environment/deployment-specific.",
        "next_step": "Keep config-level; expose only if model manager is introduced.",
    },
    "processor.regional_species": {
        "category": "planned-ui",
        "reason": "Advanced ML tuning; currently config-level only.",
        "next_step": "Evaluate after #52 (i18n) and settings information architecture pass.",
    },
    "processor.included_bird_families": {
        "category": "planned-ui",
        "reason": "Advanced ML tuning; currently config-level only.",
        "next_step": "Evaluate after #52 (i18n) and settings information architecture pass.",
    },
    "processor.save_images": {
        "category": "advanced",
        "reason": "Storage/performance-sensitive low-level switch.",
        "next_step": "Consider exposing with explicit storage warning in UI.",
    },
    "processor.post_record_seconds": {
        "category": "advanced",
        "reason": "Recording tail (#157); tuned with max_inactive_seconds in YAML.",
        "next_step": "Optional Processor advanced field after operator feedback.",
    },
    "processor.birdnet_mqtt_auto_confidence": {
        "category": "advanced",
        "reason": "BirdNET MQTT classifier bias (#129); default off.",
        "next_step": "Optional toggle under MQTT/BirdNET when presets exist.",
    },
    "processor.birdnet_mqtt_bias_window_seconds": {
        "category": "advanced",
        "reason": "Companion to birdnet_mqtt_auto_confidence.",
        "next_step": "Expose with BirdNET bias UI.",
    },
    "processor.birdnet_mqtt_bias_delta": {
        "category": "advanced",
        "reason": "Companion to birdnet_mqtt_auto_confidence.",
        "next_step": "Expose with BirdNET bias UI.",
    },
    "processor.birdnet_mqtt_bias_floor": {
        "category": "advanced",
        "reason": "Companion to birdnet_mqtt_auto_confidence.",
        "next_step": "Expose with BirdNET bias UI.",
    },
    "processor.multi_camera_groups": {
        "category": "advanced",
        "reason": "Frigate multi-camera boost (#153); YAML list of groups.",
        "next_step": "Structured editor when multi-camera UX is designed.",
    },
    "processor.multi_camera_confidence_boost": {
        "category": "advanced",
        "reason": "Companion to multi_camera_groups.",
        "next_step": "Expose with multi-camera UI.",
    },
    "processor.single_stage_coco_animals_only_auto": {
        "category": "advanced",
        "reason": "COCO 80-class detect filter; deployment tuning.",
        "next_step": "Document in Settings advanced if single_stage becomes common in UI.",
    },
    # Motion fine tuning.
    "motion.frigate_camera_filter": {
        "category": "planned-ui",
        "reason": "Advanced routing; kept config-level for now.",
        "next_step": "Add multi-select camera picker when trigger UX is expanded.",
    },
    "motion.frigate_label_filter": {
        "category": "planned-ui",
        "reason": "Advanced routing; kept config-level for now.",
        "next_step": "Add tokenized label editor in MQTT/Frigate block.",
    },
    # Merge internals.
    "detection.merge_window_seconds": {
        "category": "advanced",
        "reason": "Advanced merge tuning; kept config-level for now.",
        "next_step": "Keep config-level until merge strategy presets are designed.",
    },
    "detection.dedup_window_seconds": {
        "category": "advanced",
        "reason": "Advanced merge tuning; kept config-level for now.",
        "next_step": "Keep config-level until merge strategy presets are designed.",
    },
    "detection.one_per_species": {
        "category": "advanced",
        "reason": "Advanced merge tuning; kept config-level for now.",
        "next_step": "Keep config-level until merge strategy presets are designed.",
    },
    "detection.source_priority": {
        "category": "advanced",
        "reason": "Advanced merge tuning; kept config-level for now.",
        "next_step": "Keep config-level until merge strategy presets are designed.",
    },
    "detection.species_mapping": {
        "category": "advanced",
        "reason": "Bulk mapping maintained as config dictionary.",
        "next_step": "Consider import/export UI when species tools are expanded.",
    },
    "detection.min_confidence_to_store": {
        "category": "planned-ui",
        "reason": "Advanced filtering; currently config-level only.",
        "next_step": "Evaluate as optional control in Processor -> Advanced.",
    },
    # Ops/security-sensitive/infra-generated values.
    "notifications.telegram_api_base": {
        "category": "ops-only",
        "reason": "Network/proxy endpoint; ops-level setting.",
        "next_step": "Keep config-level.",
    },
    "notifications.telegram_timeout": {
        "category": "ops-only",
        "reason": "Network resilience tuning; ops-level setting.",
        "next_step": "Keep config-level.",
    },
    "notifications.telegram_retries": {
        "category": "ops-only",
        "reason": "Network resilience tuning; ops-level setting.",
        "next_step": "Keep config-level.",
    },
    "notifications.compress_photo_over_kb": {
        "category": "advanced",
        "reason": "Low-level delivery optimization; config-level.",
        "next_step": "Consider exposing under Telegram advanced controls.",
    },
    "notifications.telegram_max_side_px": {
        "category": "advanced",
        "reason": "Low-level delivery optimization; config-level.",
        "next_step": "Consider exposing under Telegram advanced controls.",
    },
    "web_push.enabled": {
        "category": "backend-managed",
        "reason": "Derived by backend from subscriptions.",
        "next_step": "Keep backend-managed.",
    },
    "web_push.vapid_public_key": {
        "category": "backend-managed",
        "reason": "Generated/managed by backend.",
        "next_step": "Keep backend-managed.",
    },
    "web_push.vapid_private_key": {
        "category": "backend-managed",
        "reason": "Secret generated/managed by backend.",
        "next_step": "Keep backend-managed.",
    },
    # Runtime controls still config-level.
    "video.source": {
        "category": "advanced",
        "reason": "Runtime mode selection; hidden from basic UI flow.",
        "next_step": "Keep hidden unless file-source mode is productized in UI.",
    },
    "video.pre_record_seconds": {
        "category": "planned-ui",
        "reason": "Advanced recording behavior tuning.",
        "next_step": "Evaluate control placement in Video advanced section.",
    },
    "video.auto_reconnect": {
        "category": "planned-ui",
        "reason": "Advanced stream behavior tuning.",
        "next_step": "Evaluate control placement in Video advanced section.",
    },
    "retention.days": {
        "category": "planned-ui",
        "reason": "Retention policy managed outside current settings form.",
        "next_step": "Add dedicated retention block in System/Settings.",
    },
    "ebird.protocol": {
        "category": "planned-ui",
        "reason": "Protocol is currently fixed in product flow.",
        "next_step": "Expose when multi-protocol export flow is finalized.",
    },
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


def _build_report(config_keys: set[str], form_fields: set[str]) -> dict:
    rows = []
    category_stats: dict[str, int] = {}
    for key in sorted(config_keys):
        if key in form_fields:
            status = "ui"
            reason = ""
            category = ""
            next_step = ""
        elif key in ALLOWED_NON_UI_KEYS:
            status = "allowlisted_non_ui"
            meta = ALLOWED_NON_UI_KEYS[key]
            reason = meta["reason"]
            category = meta["category"]
            next_step = meta["next_step"]
            category_stats[category] = category_stats.get(category, 0) + 1
        else:
            status = "missing"
            reason = "No UI field and not allowlisted."
            category = ""
            next_step = ""
        rows.append(
            {
                "key": key,
                "status": status,
                "category": category,
                "reason": reason,
                "next_step": next_step,
            }
        )
    missing = [r["key"] for r in rows if r["status"] == "missing"]
    return {
        "summary": {
            "config_keys": len(config_keys),
            "ui_fields": len(form_fields),
            "allowlisted_non_ui": len(ALLOWED_NON_UI_KEYS),
            "missing": len(missing),
            "allowlist_by_category": category_stats,
        },
        "missing_keys": missing,
        "rows": rows,
    }


def _to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "## Settings UI Coverage Audit",
        "",
        f"- Config keys: **{s['config_keys']}**",
        f"- UI fields: **{s['ui_fields']}**",
        f"- Allowlisted non-UI keys: **{s['allowlisted_non_ui']}**",
        f"- Missing keys: **{s['missing']}**",
        "",
        "### Allowlist maturity categories",
        "",
    ]
    for category, count in sorted(s.get("allowlist_by_category", {}).items()):
        lines.append(f"- `{category}`: **{count}**")
    lines.extend([
        "",
        "| Key | Status | Category | Reason | Next step |",
        "|---|---|---|---|---|",
    ])
    for row in report["rows"]:
        status = {
            "ui": "UI",
            "allowlisted_non_ui": "Allowlisted",
            "missing": "Missing",
        }[row["status"]]
        reason = row["reason"] or "-"
        category = row.get("category") or "-"
        next_step = row.get("next_step") or "-"
        lines.append(
            f"| `{row['key']}` | {status} | `{category}` | {reason} | {next_step} |"
        )
    lines.append("")
    return "\n".join(lines)


def _validate_allowlist() -> list[str]:
    errors: list[str] = []
    for key, meta in ALLOWED_NON_UI_KEYS.items():
        if not isinstance(meta, dict):
            errors.append(f"{key}: metadata must be an object")
            continue
        for required in ("category", "reason", "next_step"):
            if not meta.get(required):
                errors.append(f"{key}: missing '{required}'")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-path",
        default="",
        help="Optional path to write JSON report.",
    )
    parser.add_argument(
        "--summary-path",
        default="",
        help="Optional path to write Markdown summary table.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Do not fail when missing keys exist.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    allowlist_errors = _validate_allowlist()
    if allowlist_errors:
        print("Settings UI coverage check FAILED: invalid allowlist metadata.")
        for err in allowlist_errors:
            print(f"  - {err}")
        if not args.no_strict:
            return 1

    cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    config_keys = {k for k in _collect_terminal_keys(cfg) if k}
    form_fields = _load_form_fields()
    report = _build_report(config_keys, form_fields)
    missing = report["missing_keys"]
    md = _to_markdown(report)

    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.summary_path:
        summary_path = Path(args.summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(md, encoding="utf-8")

    if missing:
        print("Settings UI coverage check FAILED.")
        print("These config keys are not in Settings UI and not allowlisted:")
        for key in missing:
            print(f"  - {key}")
        print("\nEither add form fields in SettingsForm.tsx or add explicit allowlist entries.")
        if not args.no_strict:
            return 1

    print(
        "Settings UI coverage OK: "
        f"{len(config_keys)} config keys, {len(form_fields)} UI fields, "
        f"{len(ALLOWED_NON_UI_KEYS)} allowlisted non-UI keys, "
        f"{len(missing)} missing."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
