#!/usr/bin/env python3
"""Detect risky processor config drift vs default_config (#585 / I2 / #626)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

# Keys where higher user value = stricter rejection / more missed birds (critical).
_STRICTER_IF_HIGHER = (
    "processor.detect_first_confirm_min_hits",
    "processor.detect_first_confirm_min_track_seconds",
    "processor.min_track_duration",
    "processor.track_static_reject_min_duration_sec",
    "processor.track_static_reject_min_duration_sparse_sec",
    "processor.track_static_reject_min_frames",
    "processor.track_static_reject_min_frames_sparse",
    "processor.track_static_reject_max_bbox_iou_first_last_min",
)

# Keys where lower user value = stricter (critical).
_STRICTER_IF_LOWER = (
    "processor.detect_first_window_seconds",
    "processor.track_static_reject_max_center_dispersion_norm",
    "processor.track_static_reject_max_relative_center_dispersion",
)

_CONF_KEYS = (
    "min_confidence_binary",
    "min_confidence_binary_bird",
    "min_confidence_to_process",
    "openvino_min_confidence_binary_bird",
)

# P0 forbidden merged values — block deploy/CI (#626).
_CRITICAL_FORBIDDEN: tuple[tuple[str, ...], Any, str] = (
    (("processor", "pipeline_mode"), "legacy", "use linear pipeline (#621)"),
    (("detection", "persist_mode"), "legacy", "use binary_track_first (#621)"),
    (
        ("detection", "frigate_standalone_when_no_yolo"),
        True,
        "Frigate must remain prior-only, not standalone detector (ADR #634)",
    ),
    (
        ("processor", "frigate_trigger_review_salvage_allow_without_yolo_tracks"),
        True,
        "Frigate must not persist without YOLO tracks (ADR #634 classifier hints)",
    ),
    (
        ("processor", "yolo_weak_track_salvage_enabled"),
        True,
        "weak salvage must not bypass YOLO+ByteTrack primary persist (ADR #634)",
    ),
)

_LEGACY_BOOL_WHEN_SCORING = (
    ("processor", "motion_verified_detection_enabled"),
    ("processor", "background_subtraction_enabled"),
    ("processor", "static_object_suppression_enabled"),
)

_DEPRECATED_SCALAR_WHEN_SCORING = (
    ("processor", "static_square_hard_reject_max_conf"),
    ("processor", "motion_global_max_mean_absdiff"),
)


def _dot_get(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _get_nested(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = data
    for part in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _merge_configs(default: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(REPO / "app"))
    from app_config.app_config import AppConfig

    return AppConfig.merge_dicts(default, user)


def _compare_scalar(
    *,
    path: str,
    default_val: Any,
    merged_val: Any,
    direction: str,
    tolerance: float = 0.0,
    severity: str = "critical",
) -> dict[str, Any] | None:
    d = _safe_float(default_val)
    m = _safe_float(merged_val)
    if d is None or m is None:
        return None
    if direction == "higher":
        risky = m > d + tolerance
    else:
        risky = m < d - tolerance
    if not risky:
        return None
    return {
        "path": path,
        "default": d,
        "merged": m,
        "direction": direction,
        "severity": severity,
    }


def _evaluate_critical_forbidden(merged: dict[str, Any], user: dict[str, Any]) -> list[dict[str, Any]]:
    drifts: list[dict[str, Any]] = []
    for path, forbidden, reason in _CRITICAL_FORBIDDEN:
        val = _get_nested(merged, path)
        if val is None:
            continue
        if isinstance(forbidden, str):
            match = str(val).strip().lower() == forbidden.lower()
        else:
            match = val is forbidden
        if not match:
            continue
        dot_path = ".".join(path)
        drifts.append(
            {
                "path": dot_path,
                "default": None,
                "merged": val,
                "direction": "forbidden_value",
                "severity": "critical",
                "reason": reason,
            }
        )

    scoring_on = bool(_get_nested(merged, ("processor", "scoring_engine_enabled")))
    if scoring_on:
        for section, key in _LEGACY_BOOL_WHEN_SCORING:
            if _get_nested(merged, (section, key)) is True:
                drifts.append(
                    {
                        "path": f"{section}.{key}",
                        "default": False,
                        "merged": True,
                        "direction": "legacy_reenabled",
                        "severity": "critical",
                        "reason": "conflicts with scoring_engine_enabled",
                    }
                )
        for section, key in _DEPRECATED_SCALAR_WHEN_SCORING:
            user_val = _get_nested(user, (section, key))
            if user_val is not None:
                drifts.append(
                    {
                        "path": f"{section}.{key}",
                        "default": None,
                        "merged": user_val,
                        "direction": "deprecated_scalar",
                        "severity": "critical",
                        "reason": "remove; use scoring_* thresholds",
                    }
                )
    return drifts


def evaluate_processor_config_drift(
    *,
    default: dict[str, Any],
    user: dict[str, Any],
) -> dict[str, Any]:
    merged = _merge_configs(default, user)
    drifts: list[dict[str, Any]] = []

    for path in _STRICTER_IF_HIGHER:
        item = _compare_scalar(
            path=path,
            default_val=_dot_get(default, path),
            merged_val=_dot_get(merged, path),
            direction="higher",
            severity="critical",
        )
        if item:
            drifts.append(item)

    for path in _STRICTER_IF_LOWER:
        tol = 0.012 if "dispersion" in path else 0.0
        item = _compare_scalar(
            path=path,
            default_val=_dot_get(default, path),
            merged_val=_dot_get(merged, path),
            direction="lower",
            tolerance=tol,
            severity="critical",
        )
        if item:
            drifts.append(item)

    default_conf = _safe_float(_dot_get(default, "processor.min_confidence_binary"))
    overrides = _dot_get(merged, "processor.camera_overrides")
    if isinstance(overrides, dict) and default_conf is not None:
        for camera_id, cam_cfg in sorted(overrides.items()):
            if not isinstance(cam_cfg, dict):
                continue
            for key in _CONF_KEYS:
                val = _safe_float(cam_cfg.get(key))
                if val is None:
                    continue
                if val > default_conf + 0.02:
                    drifts.append(
                        {
                            "path": f"processor.camera_overrides.{camera_id}.{key}",
                            "default": default_conf,
                            "merged": val,
                            "direction": "higher_than_global_binary",
                            "severity": "critical",
                            "camera_id": str(camera_id),
                        }
                    )

    drifts.extend(_evaluate_critical_forbidden(merged, user))

    critical = [d for d in drifts if d.get("severity") == "critical"]
    warn = [d for d in drifts if d.get("severity") == "warn"]

    return {
        "schema": "processor_config_drift@v2",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "drift_count": len(drifts),
        "critical_count": len(critical),
        "warn_count": len(warn),
        "drifts": drifts,
        "ok": len(drifts) == 0,
        "critical_ok": len(critical) == 0,
    }


def _to_md(report: dict[str, Any]) -> str:
    lines = [
        "# Processor Config Drift",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- drift_count: `{report.get('drift_count')}`",
        f"- critical_count: `{report.get('critical_count')}`",
        f"- warn_count: `{report.get('warn_count')}`",
        f"- ok: `{report.get('ok')}`",
        f"- critical_ok: `{report.get('critical_ok')}`",
        "",
        "## Drifts",
        "",
    ]
    for item in report.get("drifts") or []:
        reason = item.get("reason")
        suffix = f" reason={reason}" if reason else ""
        lines.append(
            f"- `[{item.get('severity')}]` `{item.get('path')}` "
            f"default={item.get('default')} merged={item.get('merged')} "
            f"({item.get('direction')}){suffix}"
        )
    if not (report.get("drifts") or []):
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--default-config",
        default="app/app_config/default_config.yaml",
    )
    parser.add_argument(
        "--user-config",
        default="app/app_config/user_config.yaml",
    )
    parser.add_argument(
        "--out-json",
        default="docs/reports/governance/processor_config_drift_latest.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/reports/governance/processor_config_drift_latest.md",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit 1 when any drift (critical or warn) is present.",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit 1 when critical drift is present (#626 deploy/CI gate).",
    )
    return parser.parse_args()


def main() -> int:
    args = _args()
    default_path = Path(args.default_config).expanduser()
    if not default_path.is_absolute():
        default_path = REPO / default_path
    user_path = Path(args.user_config).expanduser()
    if not user_path.is_absolute():
        user_path = REPO / user_path

    if not user_path.exists():
        print(json.dumps({"ok": True, "skipped": True, "reason": "no user_config"}))
        return 0

    report = evaluate_processor_config_drift(
        default=_load_yaml(default_path),
        user=_load_yaml(user_path),
    )

    out_json = Path(args.out_json).expanduser()
    if not out_json.is_absolute():
        out_json = REPO / out_json
    out_md = Path(args.out_md).expanduser()
    if not out_md.is_absolute():
        out_md = REPO / out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_to_md(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "critical_ok": report["critical_ok"],
                "drift_count": report["drift_count"],
                "critical_count": report["critical_count"],
                "json": str(out_json),
            }
        )
    )

    if args.fail_on_critical and not report["critical_ok"]:
        return 1
    if args.fail_on_drift and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
