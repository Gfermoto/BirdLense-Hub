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
    # Trigger transport mirrors integrations.scales.source; UI exposes a single source selector.
    "triggers.scales.source": {
        "category": "derived",
        "reason": "Processor resolves scales trigger transport from integrations.scales.source when unset; duplicate source pickers were removed from Settings.",
        "next_step": "Re-expose only if product needs different MQTT/ESPHome paths for live weight vs weight-trigger sampling.",
    },
    "integrations.scales.motion_trigger_enabled": {
        "category": "legacy",
        "reason": "Superseded by triggers.scales.enabled; trigger_config still reads this for YAML migration.",
        "next_step": "Remove key after migration period or document YAML-only.",
    },
    "integrations.scales.motion_trigger_min_delta_kg": {
        "category": "legacy",
        "reason": "Superseded by triggers.scales.motion_trigger_min_delta_kg with fallback in trigger_config.",
        "next_step": "YAML-only once old configs are rare.",
    },
    "integrations.scales.motion_trigger_debounce_seconds": {
        "category": "legacy",
        "reason": "Superseded by triggers.scales.motion_trigger_debounce_seconds with fallback in trigger_config.",
        "next_step": "YAML-only once old configs are rare.",
    },
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
        "next_step": "Upload/reset via System → Processor weights (#276); not in Settings form.",
    },
    "processor.models.classifier": {
        "category": "ops-only",
        "reason": "Model path is environment/deployment-specific.",
        "next_step": "Upload/reset via System → Processor weights (#276); not in Settings form.",
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
    "processor.birdnet_fifo_snapshot_enabled": {
        "category": "ops-only",
        "reason": "Processor writes BirdNET FIFO snapshot JSON for System diagnostics; not end-user Settings.",
        "next_step": "Keep config-level or tie to a single Diagnostics toggle if productized.",
    },
    "processor.birdnet_fifo_snapshot_interval_sec": {
        "category": "ops-only",
        "reason": "Snapshot write interval; tuning for diagnostics load only.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_fifo_snapshot_recent_limit": {
        "category": "ops-only",
        "reason": "Max recent FIFO rows in snapshot payload.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_fifo_snapshot_stale_sec": {
        "category": "ops-only",
        "reason": "Web UI stale threshold when reading snapshot from disk.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_fifo_persist_enabled": {
        "category": "ops-only",
        "reason": "Processor writes BirdNET FIFO rows to hub SQLite (#269); not Settings UI.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_fifo_sqlite_busy_ms": {
        "category": "ops-only",
        "reason": "SQLite busy_timeout for BirdNET FIFO writer thread.",
        "next_step": "Same as birdnet_fifo_persist_enabled.",
    },
    "processor.birdnet_fifo_hearing_active_hours": {
        "category": "ops-only",
        "reason": "Hearing active window for BirdNET FIFO diagnostics UI (species active 1/0); not Settings.",
        "next_step": "Same as birdnet_fifo_snapshot_enabled.",
    },
    "processor.birdnet_mqtt_observability_level": {
        "category": "ops-only",
        "reason": "Log verbosity for BirdNET MQTT path; operator tuning.",
        "next_step": "Optional advanced Processor logging block.",
    },
    "processor.birdnet_mqtt_observability_debug": {
        "category": "ops-only",
        "reason": "Extra BirdNET MQTT debug logging; not for general UI.",
        "next_step": "Same as birdnet_mqtt_observability_level.",
    },
    "processor.track_regen_parallel_auto_with_manual": {
        "category": "advanced",
        "reason": "Track regeneration parallelism when mixing auto and manual scope; heavy ops.",
        "next_step": "Expose under System/track regen advanced if users need it without YAML.",
    },
    "processor.single_stage_coco_animals_only_auto": {
        "category": "advanced",
        "reason": "COCO 80-class detect filter; deployment tuning.",
        "next_step": "Document in Settings advanced if single_stage becomes common in UI.",
    },
    # Merge internals (partially in UI: see Processor → Frigate fusion).
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
        "category": "library-ui",
        "reason": "go2rtc vs file replay; toggled in Library (PATCH), not Settings form.",
        "next_step": "Single entry: Library → file replay.",
    },
    "video.file_dir": {
        "category": "library-ui",
        "reason": "Test clip folder; edited in Library file replay card.",
        "next_step": "Keep Library as single UX entry.",
    },
    "video.file_loop": {
        "category": "library-ui",
        "reason": "Default playlist loop for file mode; set in Library when enabling replay.",
        "next_step": "Keep Library as single UX entry.",
    },
    "video.file_test_max_upload_mb": {
        "category": "library-ui",
        "reason": "Hub upload size cap for Library file replay; tunable in YAML.",
        "next_step": "Optional expose in Library advanced later.",
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
    "general.require_auth_for_video_stream",
    "integrations.scales.history_max_lines",
    "integrations.scales.homeassistant_entity_id",
    "integrations.scales.min_delta_kg_for_estimate",
    "integrations.scales.mqtt_tare_payload",
    "integrations.scales.unit",
    "motion.check_every_n_frames",
    "motion.esphome_sensor_id",
    "motion.esphome_url",
    "motion.frigate_min_trigger_score",
    "motion.mqtt_topic",
    "motion.opencv_diff_threshold",
    "motion.opencv_min_contour_area",
    "motion.source",
    "processor.binary_imgsz",
    "processor.birdnet_mqtt_bias_window_seconds",
    "processor.birdnet_mqtt_prior_half_life_hours",
    "processor.birdnet_mqtt_prior_min_confidence",
    "processor.birdnet_mqtt_prior_ttl_hours",
    "processor.birdnet_mqtt_prior_window_hours",
    "processor.blur_threshold",
    "processor.classification_scheduler",
    "processor.frigate_activity_hold_seconds",
    "processor.generic_bird_min_area_frac",
    "processor.generic_bird_min_best_frame_score",
    "processor.generic_bird_min_detector_conf",
    "processor.generic_bird_min_frames",
    "processor.inference_lores_px",
    "processor.key_frame_limit",
    "processor.max_blur_checks",
    "processor.max_classifications_per_frame",
    "processor.min_center_dist",
    "processor.min_seconds_between_recordings",
    "processor.track_regen_detection_strategy",
    "processor.track_regen_frame_step",
    "processor.track_regen_ignore_regional_species",
    "processor.track_regen_lores_px",
    "processor.track_regen_match_live_pipeline",
    "processor.track_regen_precise_detection_strategy",
    "processor.track_regen_precise_min_center_dist",
    "processor.track_regen_precise_timeout_sec",
    "processor.track_regen_video_timeout_sec",
    "species.catalog_allowlist_file",
    "species.catalog_strict_ingest",
    "species.tuning_target_species_ids",
    "video.file_path",
    "video.file_realtime_simulation",
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
