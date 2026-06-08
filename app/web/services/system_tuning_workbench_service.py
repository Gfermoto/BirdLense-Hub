"""Tuning workbench service: presets, guardrails, per-camera profiles, rollback."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import data_paths
from app_config.app_config import app_config
from services.settings_patch_service import (
    SettingsPatchValidationError,
    apply_settings_patch_and_refresh_caches,
)


_STATE_FILE = "diagnostics/tuning_workbench_state.v1.json"
_MAX_CAMERA_OVERRIDES = 24

_PRESET_OVERRIDES: dict[str, dict[str, Any]] = {
    "balanced": {
        "processor.min_confidence_binary": 0.16,
        "processor.min_confidence_to_process": 0.12,
        "processor.min_track_duration": 0.75,
        "processor.min_box_size_px": 14,
        "processor.binary_imgsz": 704,
        "processor.light_gate_enabled": True,
    },
    "high_recall": {
        "processor.min_confidence_binary": 0.12,
        "processor.min_confidence_to_process": 0.09,
        "processor.min_track_duration": 0.5,
        "processor.min_box_size_px": 12,
        "processor.binary_imgsz": 640,
        "processor.light_gate_enabled": False,
    },
    "low_fp": {
        "processor.min_confidence_binary": 0.22,
        "processor.min_confidence_to_process": 0.17,
        "processor.min_track_duration": 1.0,
        "processor.min_box_size_px": 16,
        "processor.binary_imgsz": 704,
        "processor.light_gate_enabled": True,
    },
    "night": {
        "processor.adaptive_profiles.enabled": True,
        "processor.adaptive_profiles.night.max_brightness": 70.0,
        "processor.adaptive_profiles.night.max_contrast": 42.0,
        "processor.adaptive_profiles.night.overrides.min_confidence_binary": 0.11,
        "processor.adaptive_profiles.night.overrides.min_confidence_binary_bird": 0.06,
        "processor.adaptive_profiles.night.overrides.min_confidence_to_process": 0.08,
        "processor.adaptive_profiles.night.overrides.min_box_size_px": 12,
        "processor.adaptive_profiles.night.overrides.min_track_duration": 0.45,
    },
    "feeder_closeup_ab": {
        "processor.min_confidence_binary": 0.13,
        "processor.min_confidence_to_process": 0.1,
        "processor.min_track_duration": 0.55,
        "processor.min_box_size_px": 10,
        "processor.binary_imgsz": 704,
        "processor.light_gate_enabled": True,
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path() -> Path:
    return Path(data_paths.data_dir()) / _STATE_FILE


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(payload: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _extract_camera_ids() -> list[str]:
    cams = app_config.get("video.cameras") or []
    out: list[str] = []
    if not isinstance(cams, list):
        return out
    for cam in cams:
        if not isinstance(cam, dict):
            continue
        cid = str(cam.get("id") or "").strip()
        if cid and cid not in out:
            out.append(cid)
    return out


def _camera_merged_overrides(camera_id: str) -> tuple[str, dict[str, Any]]:
    """Role preset + per-id overrides (same merge order as processor recording_session)."""
    cam = str(camera_id or "").strip()
    tuning_role = ""
    merged: dict[str, Any] = {}
    if not cam:
        return tuning_role, merged
    cams = app_config.get("video.cameras") or []
    if isinstance(cams, list):
        for row in cams:
            if not isinstance(row, dict):
                continue
            if str(row.get("id") or "").strip() != cam:
                continue
            tuning_role = str(row.get("tuning_role") or "").strip()
            break
    if tuning_role:
        role_raw = app_config.get(f"processor.camera_tuning_by_role.{tuning_role}")
        if isinstance(role_raw, dict):
            merged.update(copy.deepcopy(role_raw))
    camera_map = app_config.get("processor.camera_overrides")
    if isinstance(camera_map, dict):
        cam_overrides = camera_map.get(cam)
        if isinstance(cam_overrides, dict):
            merged.update(copy.deepcopy(cam_overrides))
    return tuning_role, merged


def _processor_effective_for_camera(camera_id: str | None) -> dict[str, Any]:
    proc = copy.deepcopy(app_config.get("processor") or {})
    if not camera_id:
        return proc
    _, merged = _camera_merged_overrides(str(camera_id))
    for key, value in merged.items():
        proc[key] = value
    return proc


def _estimate_profile_metrics(proc_cfg: dict[str, Any]) -> dict[str, float]:
    conf_binary = _safe_float(proc_cfg.get("min_confidence_binary"), 0.16)
    conf_process = _safe_float(proc_cfg.get("min_confidence_to_process"), 0.12)
    min_box = _safe_float(proc_cfg.get("min_box_size_px"), 14.0)
    min_track = _safe_float(proc_cfg.get("min_track_duration"), 0.75)
    imgsz = _safe_float(proc_cfg.get("binary_imgsz"), 704.0)
    light_gate_enabled = bool(proc_cfg.get("light_gate_enabled", True))

    recall_score = 73.0 - (conf_binary - 0.16) * 130.0 - (conf_process - 0.12) * 115.0
    recall_score += (14.0 - min_box) * 1.4 + (0.75 - min_track) * 20.0
    precision_score = 67.0 + (conf_binary - 0.16) * 120.0 + (conf_process - 0.12) * 110.0
    precision_score += (min_box - 14.0) * 1.0 + (min_track - 0.75) * 14.0
    runtime_cost = 52.0 + (imgsz - 704.0) * 0.06 + (0.5 if not light_gate_enabled else -4.5)
    return {
        "estimated_recall": round(_clamp(recall_score), 2),
        "estimated_precision": round(_clamp(precision_score), 2),
        "estimated_runtime_cost": round(_clamp(runtime_cost), 2),
    }


def _collect_guardrail_feedback(proc_cfg: dict[str, Any]) -> dict[str, list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    conf_binary = _safe_float(proc_cfg.get("min_confidence_binary"), 0.16)
    conf_process = _safe_float(proc_cfg.get("min_confidence_to_process"), 0.12)
    min_box = _safe_float(proc_cfg.get("min_box_size_px"), 14.0)
    min_track = _safe_float(proc_cfg.get("min_track_duration"), 0.75)
    imgsz = _safe_float(proc_cfg.get("binary_imgsz"), 704.0)
    if conf_binary < 0.03 or conf_binary > 0.6:
        errs.append("processor.min_confidence_binary must be in [0.03, 0.60]")
    if conf_process < 0.03 or conf_process > 0.6:
        errs.append("processor.min_confidence_to_process must be in [0.03, 0.60]")
    if min_box < 8 or min_box > 160:
        errs.append("processor.min_box_size_px must be in [8, 160]")
    if min_track < 0.2 or min_track > 6.0:
        errs.append("processor.min_track_duration must be in [0.2, 6.0]")
    if imgsz < 320 or imgsz > 1280:
        errs.append("processor.binary_imgsz must be in [320, 1280]")
    if conf_binary <= 0.1 and conf_process <= 0.1 and not bool(proc_cfg.get("light_gate_enabled", True)):
        warns.append("Risky combo: low confidence thresholds with disabled light gate can increase false positives.")
    if imgsz >= 960 and str(app_config.get("video.capture_backend") or "auto") == "opencv":
        warns.append("High detector image size with OpenCV capture can increase latency under load.")
    if min_track <= 0.4 and min_box <= 12:
        warns.append("Very short tracks with small boxes can increase jitter and fragmentation.")
    if conf_process < 0.08:
        warns.append("Low min_confidence_to_process can flood review queue.")
    return {"errors": errs, "warnings": warns}


def _to_nested_patch(flat: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        cur = out
        for token in parts[:-1]:
            cur = cur.setdefault(token, {})
        cur[parts[-1]] = value
    return out


def _profile_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    return {
        "recall_delta": round(after["estimated_recall"] - before["estimated_recall"], 2),
        "precision_delta": round(after["estimated_precision"] - before["estimated_precision"], 2),
        "runtime_cost_delta": round(
            after["estimated_runtime_cost"] - before["estimated_runtime_cost"],
            2,
        ),
    }


def _runtime_cost_guard_error(
    auto_eval: dict[str, Any],
    *,
    max_runtime_cost_delta: float | None,
) -> str | None:
    if max_runtime_cost_delta is None:
        return None
    if max_runtime_cost_delta < 0:
        return "max_runtime_cost_delta must be >= 0"
    delta = _safe_float((auto_eval.get("delta") or {}).get("runtime_cost_delta"), 0.0)
    if delta <= max_runtime_cost_delta:
        return None
    return (
        "Rollback guard triggered: runtime_cost_delta="
        f"{delta:.2f} > max_runtime_cost_delta={max_runtime_cost_delta:.2f}"
    )


def _load_raw_user_config() -> dict[str, Any]:
    import os
    import yaml

    path = app_config.user_config_file
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _write_raw_user_config(raw_cfg: dict[str, Any]) -> None:
    app_config._persist_raw_user_config(raw_cfg)
    app_config.reload()


def _presets_preview() -> list[dict[str, Any]]:
    baseline = _estimate_profile_metrics(_processor_effective_for_camera(None))
    out: list[dict[str, Any]] = []
    for preset_id, overrides in _PRESET_OVERRIDES.items():
        patch = _to_nested_patch(overrides)
        proc_next = copy.deepcopy(_processor_effective_for_camera(None))
        proc_patch = patch.get("processor") or {}
        if isinstance(proc_patch, dict):
            for key, value in proc_patch.items():
                proc_next[key] = value
        metrics = _estimate_profile_metrics(proc_next)
        out.append(
            {
                "id": preset_id,
                "title": preset_id.replace("_", " ").title(),
                "overrides": overrides,
                "estimated": metrics,
                "delta_vs_current": _profile_delta(baseline, metrics),
            }
        )
    return out


def build_tuning_workbench_payload() -> tuple[dict[str, Any], int]:
    camera_ids = _extract_camera_ids()
    proc_global = _processor_effective_for_camera(None)
    global_metrics = _estimate_profile_metrics(proc_global)
    global_guardrails = _collect_guardrail_feedback(proc_global)
    camera_rows: list[dict[str, Any]] = []
    camera_overrides = proc_global.get("camera_overrides")
    for camera_id in camera_ids:
        tuning_role, role_merged = _camera_merged_overrides(camera_id)
        eff = _processor_effective_for_camera(camera_id)
        per_metrics = _estimate_profile_metrics(eff)
        overrides = {}
        if isinstance(camera_overrides, dict) and isinstance(camera_overrides.get(camera_id), dict):
            overrides = copy.deepcopy(camera_overrides.get(camera_id))
        role_preset = {}
        if tuning_role:
            role_raw = app_config.get(f"processor.camera_tuning_by_role.{tuning_role}")
            if isinstance(role_raw, dict):
                role_preset = copy.deepcopy(role_raw)
        camera_rows.append(
            {
                "camera_id": camera_id,
                "tuning_role": tuning_role or None,
                "role_preset": role_preset,
                "overrides": overrides,
                "effective_keys": role_merged,
                "effective": per_metrics,
                "delta_vs_global": _profile_delta(global_metrics, per_metrics),
            }
        )
    state = _load_state()
    return {
        "schema": "tuning_workbench@v1",
        "generated_at": _utc_now_iso(),
        "global": {
            "estimated": global_metrics,
            "guardrails": global_guardrails,
        },
        "presets": _presets_preview(),
        "camera_profiles": camera_rows,
        "available_cameras": camera_ids,
        "last_change": state.get("last_change"),
    }, 200


def apply_tuning_preset(*, preset_id: str) -> tuple[dict[str, Any], int]:
    key = str(preset_id or "").strip().lower()
    if key not in _PRESET_OVERRIDES:
        return {"error": f"Unknown preset '{preset_id}'"}, 400
    before_proc = _processor_effective_for_camera(None)
    before_metrics = _estimate_profile_metrics(before_proc)
    raw_before = _load_raw_user_config()
    patch = _to_nested_patch(_PRESET_OVERRIDES[key])
    try:
        apply_settings_patch_and_refresh_caches(patch)
    except SettingsPatchValidationError as exc:
        return {"error": "Validation failed", "issues": exc.issues}, 400
    after_proc = _processor_effective_for_camera(None)
    after_metrics = _estimate_profile_metrics(after_proc)
    guardrails = _collect_guardrail_feedback(after_proc)
    auto_eval = {
        "baseline": before_metrics,
        "current": after_metrics,
        "delta": _profile_delta(before_metrics, after_metrics),
        "ok": len(guardrails["errors"]) == 0,
    }
    _save_state(
        {
            "schema": "tuning_workbench_state@v1",
            "updated_at": _utc_now_iso(),
            "rollback": {
                "had_processor": isinstance(raw_before.get("processor"), dict),
                "processor": copy.deepcopy(raw_before.get("processor") or {}),
            },
            "last_change": {
                "action": "apply_preset",
                "preset_id": key,
                "auto_eval": auto_eval,
                "guardrails": guardrails,
            },
        }
    )
    return {
        "ok": True,
        "applied_preset": key,
        "auto_eval": auto_eval,
        "guardrails": guardrails,
    }, 200


def upsert_camera_tuning_profile(
    *,
    camera_id: str,
    overrides: dict[str, Any] | None,
    experiment_tag: str | None = None,
    max_runtime_cost_delta: float | None = None,
) -> tuple[dict[str, Any], int]:
    cam = str(camera_id or "").strip()
    if not cam:
        return {"error": "camera_id is required"}, 400
    camera_ids = _extract_camera_ids()
    if cam not in camera_ids:
        return {"error": f"Unknown camera_id '{cam}'"}, 400
    clean_overrides: dict[str, Any] = {}
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            key = str(k or "").strip()
            if not key:
                continue
            clean_overrides[key] = v
    if len(clean_overrides) > _MAX_CAMERA_OVERRIDES:
        return {"error": "Too many per-camera override keys"}, 400
    before_eff = _processor_effective_for_camera(cam)
    before_metrics = _estimate_profile_metrics(before_eff)
    raw_before = _load_raw_user_config()

    if clean_overrides:
        try:
            apply_settings_patch_and_refresh_caches({"processor": {"camera_overrides": {cam: clean_overrides}}})
        except SettingsPatchValidationError as exc:
            return {"error": "Validation failed", "issues": exc.issues}, 400
    else:
        raw_user = _load_raw_user_config()
        proc = raw_user.get("processor")
        if not isinstance(proc, dict):
            proc = {}
            raw_user["processor"] = proc
        cam_map = proc.get("camera_overrides")
        if not isinstance(cam_map, dict):
            cam_map = {}
            proc["camera_overrides"] = cam_map
        cam_map.pop(cam, None)
        if not cam_map:
            proc.pop("camera_overrides", None)
        _write_raw_user_config(raw_user)
    after_eff = _processor_effective_for_camera(cam)
    after_metrics = _estimate_profile_metrics(after_eff)
    guardrails = _collect_guardrail_feedback(after_eff)
    auto_eval = {
        "baseline": before_metrics,
        "current": after_metrics,
        "delta": _profile_delta(before_metrics, after_metrics),
        "ok": len(guardrails["errors"]) == 0,
    }
    guard_error = _runtime_cost_guard_error(
        auto_eval,
        max_runtime_cost_delta=max_runtime_cost_delta,
    )
    if guard_error:
        _write_raw_user_config(raw_before)
        return {
            "error": guard_error,
            "camera_id": cam,
            "auto_eval": auto_eval,
        }, 409
    _save_state(
        {
            "schema": "tuning_workbench_state@v1",
            "updated_at": _utc_now_iso(),
            "rollback": {
                "had_processor": isinstance(raw_before.get("processor"), dict),
                "processor": copy.deepcopy(raw_before.get("processor") or {}),
            },
            "last_change": {
                "action": "upsert_camera_profile",
                "camera_id": cam,
                "experiment_tag": str(experiment_tag or "").strip() or None,
                "auto_eval": auto_eval,
                "guardrails": guardrails,
            },
        }
    )
    return {
        "ok": True,
        "camera_id": cam,
        "experiment_tag": str(experiment_tag or "").strip() or None,
        "auto_eval": auto_eval,
        "guardrails": guardrails,
    }, 200


def rollback_tuning_workbench_profile() -> tuple[dict[str, Any], int]:
    state = _load_state()
    rollback = state.get("rollback")
    if not isinstance(rollback, dict):
        return {"error": "Rollback snapshot is not available"}, 409
    raw_user = _load_raw_user_config()
    had_processor = bool(rollback.get("had_processor"))
    old_proc = rollback.get("processor") if isinstance(rollback.get("processor"), dict) else {}
    if had_processor:
        raw_user["processor"] = copy.deepcopy(old_proc)
    else:
        raw_user.pop("processor", None)
    _write_raw_user_config(raw_user)
    _save_state(
        {
            "schema": "tuning_workbench_state@v1",
            "updated_at": _utc_now_iso(),
            "last_change": {
                "action": "rollback",
                "restored_at": _utc_now_iso(),
            },
        }
    )
    return {"ok": True, "message": "Tuning profile rollback applied"}, 200
