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
# Keep this list short and explicit; every key must have a reason.
ALLOWED_NON_UI_KEYS: dict[str, str] = {
    # Processor internals.
    "processor.detection_strategy": "Deployment-level model strategy; unsafe for casual UI edits.",
    "processor.models.single_stage": "Model path is environment/deployment-specific.",
    "processor.models.binary": "Model path is environment/deployment-specific.",
    "processor.models.classifier": "Model path is environment/deployment-specific.",
    "processor.regional_species": "Advanced ML tuning; currently config-level only.",
    "processor.included_bird_families": "Advanced ML tuning; currently config-level only.",
    "processor.save_images": "Storage/performance-sensitive low-level switch.",
    # Motion fine tuning.
    "motion.frigate_camera_filter": "Advanced routing; kept config-level for now.",
    "motion.frigate_label_filter": "Advanced routing; kept config-level for now.",
    # Merge internals.
    "detection.merge_window_seconds": "Advanced merge tuning; kept config-level for now.",
    "detection.dedup_window_seconds": "Advanced merge tuning; kept config-level for now.",
    "detection.one_per_species": "Advanced merge tuning; kept config-level for now.",
    "detection.source_priority": "Advanced merge tuning; kept config-level for now.",
    "detection.species_mapping": "Bulk mapping maintained as config dictionary.",
    "detection.min_confidence_to_store": "Advanced filtering; currently config-level only.",
    # Ops/security-sensitive/infra-generated values.
    "notifications.telegram_api_base": "Network/proxy endpoint; ops-level setting.",
    "notifications.telegram_timeout": "Network resilience tuning; ops-level setting.",
    "notifications.telegram_retries": "Network resilience tuning; ops-level setting.",
    "notifications.compress_photo_over_kb": "Low-level delivery optimization; config-level.",
    "notifications.telegram_max_side_px": "Low-level delivery optimization; config-level.",
    "web_push.enabled": "Derived by backend from subscriptions.",
    "web_push.vapid_public_key": "Generated/managed by backend.",
    "web_push.vapid_private_key": "Secret generated/managed by backend.",
    # Runtime controls still config-level.
    "video.source": "Runtime mode selection; hidden from basic UI flow.",
    "video.pre_record_seconds": "Advanced recording behavior tuning.",
    "video.auto_reconnect": "Advanced stream behavior tuning.",
    "retention.days": "Retention policy managed outside current settings form.",
    "ebird.protocol": "Protocol is currently fixed in product flow.",
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
    for key in sorted(config_keys):
        if key in form_fields:
            status = "ui"
            reason = ""
        elif key in ALLOWED_NON_UI_KEYS:
            status = "allowlisted_non_ui"
            reason = ALLOWED_NON_UI_KEYS[key]
        else:
            status = "missing"
            reason = "No UI field and not allowlisted."
        rows.append({"key": key, "status": status, "reason": reason})
    missing = [r["key"] for r in rows if r["status"] == "missing"]
    return {
        "summary": {
            "config_keys": len(config_keys),
            "ui_fields": len(form_fields),
            "allowlisted_non_ui": len(ALLOWED_NON_UI_KEYS),
            "missing": len(missing),
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
        "| Key | Status | Reason |",
        "|---|---|---|",
    ]
    for row in report["rows"]:
        status = {
            "ui": "UI",
            "allowlisted_non_ui": "Allowlisted",
            "missing": "Missing",
        }[row["status"]]
        reason = row["reason"] or "-"
        lines.append(f"| `{row['key']}` | {status} | {reason} |")
    lines.append("")
    return "\n".join(lines)


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
