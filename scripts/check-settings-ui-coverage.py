#!/usr/bin/env python3
"""Fail CI when new config keys are not wired into Settings UI.

Policy:
- Every terminal key from app/app_config/default_config.yaml must be either:
  1) mapped to a <form.Field name="..."> under app/ui/src/pages/Settings/ (tsx), or
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
SETTINGS_UI_DIR = ROOT / "app" / "ui" / "src" / "pages" / "Settings"


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
    "processor.file_max_record_floor_seconds": {
        "category": "advanced",
        "reason": "video.source=file only: min wall-clock segment before session finalize.",
        "next_step": "Optional Processor advanced if users need tuning without YAML.",
    },
    "processor.keep_recording_when_no_detections": {
        "category": "advanced",
        "reason": "video.source=file: keep session mp4 when 0 detections; for offline crops, not main UI.",
        "next_step": "Optional Processor advanced toggle if file-test users grow.",
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

# Legacy terminal keys that are still config-level (not yet exposed in Settings UI).
# Keep explicit list to avoid silent drift while unblocking CI on existing scope.
AUTO_ALLOWLIST_META = {
    "category": "planned-ui",
    "reason": "Config-level key is intentionally not exposed in current Settings UI.",
    "next_step": "Expose in Settings UI or move to strict allowlist section with dedicated rationale.",
}
AUTO_ALLOWLIST_KEYS: set[str] = {
    "detection.cross_source_confidence_bonus",
    "ebird.country",
    "ebird.location_name",
    "ebird.species_mapping",
    "ebird.state",
    "feed.duration_seconds",
    "feed.esphome_switch_id",
    "feed.esphome_type",
    "feed.esphome_url",
    "feed.mqtt_topic",
    "feed.source",
    "gallery.enabled",
    "gallery.min_confidence",
    "gallery.only_manually_corrected",
    "gallery.upload_url",
    "general.birdnet_url",
    "general.contributor_password",
    "general.donate_url",
    "general.enable_notifications",
    "general.heimdall_url",
    "general.notification_excluded_species",
    "general.require_auth_for_video_stream",
    "general.settings_password",
    "integrations.scales.enabled",
    "integrations.scales.history_max_lines",
    "integrations.scales.homeassistant_entity_id",
    "integrations.scales.min_delta_kg_for_estimate",
    "integrations.scales.mqtt_command_topic",
    "integrations.scales.mqtt_tare_payload",
    "integrations.scales.mqtt_topic",
    "integrations.scales.source",
    "integrations.scales.unit",
    "mcp.enabled",
    "mcp.token",
    "motion.check_every_n_frames",
    "motion.esphome_sensor_id",
    "motion.esphome_url",
    "motion.frigate_label_exclude",
    "motion.mqtt_topic",
    "motion.source",
    "mqtt.birdnet_topic",
    "mqtt.broker",
    "mqtt.frigate_topic",
    "mqtt.ha_discovery",
    "mqtt.port",
    "mqtt.publish_topic",
    "mqtt.reconnect_max_delay",
    "mqtt.reconnect_min_delay",
    "notifications.base_url",
    "notifications.compress_photo_over_kb",
    "notifications.custom_emoji_id_bird",
    "notifications.custom_emoji_id_chipmunk",
    "notifications.custom_emoji_id_open_live",
    "notifications.disable_notification",
    "notifications.link_preview_large",
    "notifications.message_thread_id",
    "notifications.paid_media_forward_star_count",
    "notifications.paid_media_view_star_count",
    "notifications.protect_content",
    "notifications.send_photo",
    "notifications.telegram_api_base",
    "notifications.telegram_api_hash",
    "notifications.telegram_api_id",
    "notifications.telegram_bot_token",
    "notifications.telegram_chat_id",
    "notifications.telegram_max_side_px",
    "notifications.telegram_mtproto_host",
    "notifications.telegram_mtproto_port",
    "notifications.telegram_mtproto_secret",
    "notifications.telegram_proxy_type",
    "notifications.telegram_proxy_url",
    "notifications.telegram_retries",
    "notifications.telegram_timeout",
    "notifications.use_custom_emoji",
    "performance.cache_redis_enabled",
    "performance.redis_url",
    "processor.birdnet_mqtt_auto_confidence",
    "processor.birdnet_mqtt_bias_delta",
    "processor.birdnet_mqtt_bias_floor",
    "processor.dataset_min_confidence",
    "processor.ebird_regional_top_auto_confidence",
    "processor.ebird_regional_top_confidence_delta",
    "processor.ebird_regional_top_confidence_floor",
    "processor.inference_lores_px",
    "processor.max_inactive_seconds",
    "processor.max_record_seconds",
    "processor.min_confidence_binary",
    "processor.min_confidence_to_notify",
    "processor.min_confidence_to_process",
    "processor.min_track_duration",
    "processor.multi_camera_confidence_boost",
    "processor.multi_camera_groups",
    "processor.post_record_seconds",
    "processor.save_dataset_crops",
    "processor.spectrogram_px_per_sec",
    "processor.generate_spectrogram_always",
    "processor.tracker",
    "processor.track_regen_detection_strategy",
    "processor.track_regen_frame_step",
    "processor.track_regen_ignore_regional_species",
    "processor.track_regen_match_live_pipeline",
    "processor.track_regen_lores_px",
    "processor.track_regen_precise_detection_strategy",
    "processor.track_regen_precise_min_center_dist",
    "processor.track_regen_precise_timeout_sec",
    "processor.track_regen_video_timeout_sec",
    "secrets.ebird_api_key",
    "secrets.latitude",
    "secrets.longitude",
    "secrets.openweather_api_key",
    "secrets.xeno_canto_api_key",
    "species.catalog_allowlist_file",
    "species.catalog_strict_ingest",
    "species.tuning_target_species_ids",
    "ui.unknown_confidence_threshold",
    "video.cameras",
    "video.encoding",
    "video.go2rtc_url",
    "video.video_height",
    "video.video_width",
    "homeassistant.token",
    "homeassistant.url",
    "weather.ha_entity_id",
    "weather.source",
    "webhook.url",
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
    names: set[str] = set()
    for path in sorted(SETTINGS_UI_DIR.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        names.update(re.findall(r'form\.Field name="([^"]+)"', text))
    return names


def _build_report(config_keys: set[str], form_fields: set[str]) -> dict:
    rows = []
    category_stats: dict[str, int] = {}
    for key in sorted(config_keys):
        if key in form_fields:
            status = "ui"
            reason = ""
            category = ""
            next_step = ""
        elif key in ALLOWED_NON_UI_KEYS or key in AUTO_ALLOWLIST_KEYS:
            status = "allowlisted_non_ui"
            meta = ALLOWED_NON_UI_KEYS.get(key, AUTO_ALLOWLIST_META)
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
        print("\nEither add form fields under app/ui/src/pages/Settings/ or add explicit allowlist entries.")
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
