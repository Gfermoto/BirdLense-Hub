"""Product-facing recognition improvement flow built on top of fusion jobs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import routes.ui_system_jobs_state as job_state
from app_config.app_config import AppConfig, app_config
from data_paths import data_dir
from models import ActivityLog, db
from services.fusion_training_service import repo_root, run_fusion_eval_job, run_fusion_export_job
from services.processor_restart_service import write_processor_restart_flag

_MIN_CORRECTED_EXAMPLES = 10
_MIN_UNIQUE_VIDEOS = 5
_MIN_UNIQUE_SPECIES = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ml_dir() -> Path:
    path = Path(data_dir()) / "ml"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _models_dir() -> Path:
    path = _ml_dir() / "fusion"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _registry_path() -> Path:
    return _ml_dir() / "fusion_registry.json"


def _default_registry() -> dict[str, Any]:
    return {"active_model_id": None, "models": []}


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return _default_registry()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _default_registry()
    if not isinstance(parsed, dict):
        return _default_registry()
    models = parsed.get("models")
    if not isinstance(models, list):
        parsed["models"] = []
    parsed.setdefault("active_model_id", None)
    return parsed


def _save_registry(payload: dict[str, Any]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _active_runtime_mode() -> str:
    enabled = bool(app_config.get("detection.use_learned_fusion") or False)
    configured_path = str(app_config.get("detection.fusion_model_path") or "").strip()
    if not enabled:
        return "disabled"
    if configured_path and os.path.isfile(configured_path):
        return "trained"
    return "heuristic"


def _active_registry_model(registry: dict[str, Any]) -> dict[str, Any] | None:
    active_id = registry.get("active_model_id")
    if not active_id:
        return None
    for model in registry.get("models") or []:
        if isinstance(model, dict) and model.get("id") == active_id:
            return model
    return None


def _previous_registry_model(registry: dict[str, Any]) -> dict[str, Any] | None:
    active_id = registry.get("active_model_id")
    candidates = []
    for model in registry.get("models") or []:
        if not isinstance(model, dict):
            continue
        if model.get("id") == active_id:
            continue
        model_path = str(model.get("model_path") or "").strip()
        if model_path and os.path.isfile(model_path):
            candidates.append(model)
    candidates.sort(key=lambda item: str(item.get("activated_at") or item.get("created_at") or ""), reverse=True)
    return candidates[0] if candidates else None


def _model_label(model: dict[str, Any] | None, active_mode: str) -> str:
    if active_mode == "disabled":
        return "Disabled"
    if active_mode == "heuristic":
        return "Built-in heuristic"
    if model and model.get("label"):
        return str(model["label"])
    return "Trained model"


def _collect_feedback_stats() -> dict[str, Any]:
    rows = (
        db.session.query(ActivityLog)
        .filter(ActivityLog.type == "species_correction")
        .order_by(ActivityLog.created_at.desc())
        .all()
    )
    detection_ids: set[int] = set()
    video_ids: set[int] = set()
    species_names: set[str] = set()
    latest = None
    for row in rows:
        payload: dict[str, Any] = {}
        try:
            if row.data:
                payload = json.loads(row.data)
        except (TypeError, ValueError):
            payload = {}
        detection_id = payload.get("detection_id")
        if isinstance(detection_id, int):
            detection_ids.add(detection_id)
        video_id = payload.get("video_id")
        if isinstance(video_id, int):
            video_ids.add(video_id)
        species_name = str(payload.get("to_species_name") or payload.get("from_species_name") or "").strip()
        if species_name:
            species_names.add(species_name)
        if latest is None and row.created_at is not None:
            latest = row.created_at
    corrected_examples = len(detection_ids) or len(rows)
    unique_videos = len(video_ids)
    unique_species = len(species_names)
    ready = (
        corrected_examples >= _MIN_CORRECTED_EXAMPLES
        and unique_videos >= _MIN_UNIQUE_VIDEOS
        and unique_species >= _MIN_UNIQUE_SPECIES
    )
    return {
        "corrected_examples": corrected_examples,
        "unique_videos": unique_videos,
        "unique_species": unique_species,
        "ready_for_training": ready,
        "examples_until_ready": max(0, _MIN_CORRECTED_EXAMPLES - corrected_examples),
        "thresholds": {
            "corrected_examples": _MIN_CORRECTED_EXAMPLES,
            "unique_videos": _MIN_UNIQUE_VIDEOS,
            "unique_species": _MIN_UNIQUE_SPECIES,
        },
        "latest_feedback_at": latest.isoformat() if latest else None,
    }


def _persist_detection_config(*, enabled: bool, model_path: str) -> None:
    user = app_config.load_raw_user_config_dict()
    AppConfig._set_nested(user, "detection.use_learned_fusion", bool(enabled))
    AppConfig._set_nested(user, "detection.fusion_model_path", model_path)
    issues = app_config.validate_user_config_tree(user)
    if issues:
        raise RuntimeError(f"config_validation_failed: {'; '.join(issues[:3])}")
    app_config._persist_raw_user_config(user)
    app_config.reload()
    write_processor_restart_flag(data_dir())


def build_recognition_improvement_summary() -> dict[str, Any]:
    registry = _load_registry()
    active_mode = _active_runtime_mode()
    active_model = _active_registry_model(registry)
    previous_model = _previous_registry_model(registry)
    configured_path = str(app_config.get("detection.fusion_model_path") or "").strip()
    models = [m for m in registry.get("models") or [] if isinstance(m, dict)]
    latest_trained = None
    if models:
        latest_trained = sorted(
            models,
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )[0]
    return {
        "active_mode": active_mode,
        "settings": {
            "enabled": bool(app_config.get("detection.use_learned_fusion") or False),
            "alpha": float(app_config.get("detection.fusion_alpha") or 0.6),
        },
        "feedback": _collect_feedback_stats(),
        "model": {
            "label": _model_label(active_model, active_mode),
            "active_model_id": active_model.get("id") if active_model else None,
            "configured_path": configured_path,
            "trained_model_count": len(models),
            "last_trained_at": latest_trained.get("created_at") if latest_trained else None,
            "can_roll_back": previous_model is not None or active_mode == "trained",
        },
        "service_mode": {
            "registry_path": str(_registry_path()),
        },
    }


def _training_script_path() -> Path:
    return repo_root() / "scripts" / "train_fusion.py"


def _run_training_subprocess(*, source_csv: str, out_dir: Path) -> subprocess.CompletedProcess[str]:
    script_path = _training_script_path()
    if not script_path.exists():
        raise RuntimeError("train_script_missing")
    cmd = [
        sys.executable,
        str(script_path),
        "--data",
        str(source_csv),
        "--out-dir",
        str(out_dir),
        "--epochs",
        "5",
    ]
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def run_recognition_training_job() -> dict[str, Any]:
    export_result = run_fusion_export_job()
    source_csv = str(export_result.get("output_path") or "").strip()
    if not source_csv or not os.path.isfile(source_csv):
        raise RuntimeError("fusion_training_export_missing")

    model_id = datetime.now(timezone.utc).strftime("trained-%Y%m%d-%H%M%S")
    out_dir = _models_dir() / model_id
    out_dir.mkdir(parents=True, exist_ok=True)
    train_proc = _run_training_subprocess(source_csv=source_csv, out_dir=out_dir)

    model_file = out_dir / "fusion_state.pt"
    if not model_file.is_file():
        raise RuntimeError("fusion_training_model_missing")

    eval_result = run_fusion_eval_job(source_csv=source_csv, model_path=str(model_file))
    registry = _load_registry()
    previous_active = registry.get("active_model_id")
    for model in registry.get("models") or []:
        if isinstance(model, dict) and model.get("id") == previous_active:
            model["status"] = "previous"
    record = {
        "id": model_id,
        "label": model_id,
        "model_path": str(model_file),
        "created_at": _utc_now_iso(),
        "activated_at": _utc_now_iso(),
        "status": "active",
        "source_csv": source_csv,
        "export_rows": export_result.get("rows_written"),
        "train_stdout": (train_proc.stdout or "").strip()[-4000:],
        "train_stderr": (train_proc.stderr or "").strip()[-4000:],
        "eval": {
            "accuracy_at_0_5": eval_result.get("accuracy_at_0_5"),
            "ece": eval_result.get("ece"),
            "brier": eval_result.get("brier"),
            "source_csv": eval_result.get("source_csv"),
        },
    }
    registry.setdefault("models", []).append(record)
    registry["active_model_id"] = model_id
    _save_registry(registry)
    _persist_detection_config(enabled=True, model_path=str(model_file))

    summary = build_recognition_improvement_summary()
    summary["train_result"] = {
        "model_id": model_id,
        "export": export_result,
        "eval": eval_result,
    }
    return summary


def rollback_recognition_model() -> dict[str, Any]:
    registry = _load_registry()
    current_active_id = registry.get("active_model_id")
    previous_model = _previous_registry_model(registry)
    if previous_model is not None:
        next_path = str(previous_model.get("model_path") or "")
        registry["active_model_id"] = previous_model.get("id")
        for model in registry.get("models") or []:
            if not isinstance(model, dict):
                continue
            if model.get("id") == previous_model.get("id"):
                model["status"] = "active"
                model["activated_at"] = _utc_now_iso()
            elif current_active_id and model.get("id") == current_active_id:
                model["status"] = "previous"
        _save_registry(registry)
        _persist_detection_config(enabled=True, model_path=next_path)
    else:
        for model in registry.get("models") or []:
            if isinstance(model, dict) and model.get("id") == current_active_id:
                model["status"] = "previous"
        registry["active_model_id"] = None
        _save_registry(registry)
        _persist_detection_config(enabled=True, model_path="")
    return build_recognition_improvement_summary()


def start_recognition_training_background(flask_app) -> tuple[dict[str, Any], int]:
    with job_state._recognition_training_lock:
        if job_state._recognition_training_status["status"] == "running":
            return {
                "error": "Recognition training already in progress",
                "status": job_state._recognition_training_status,
            }, 409
        job_state._recognition_training_status.update(
            {"status": "running", "result": None, "error": None, "progress": None}
        )

    def _run() -> None:
        try:
            with flask_app.app_context():
                result = run_recognition_training_job()
            with job_state._recognition_training_lock:
                job_state._recognition_training_status.update(
                    {"status": "done", "result": result, "error": None, "progress": None}
                )
        except Exception as exc:
            with job_state._recognition_training_lock:
                job_state._recognition_training_status.update(
                    {"status": "error", "result": None, "error": str(exc), "progress": None}
                )

    threading.Thread(target=_run, daemon=True).start()
    return {
        "message": "Recognition improvement training started",
        "status": dict(job_state._recognition_training_status),
    }, 202


def recognition_training_status_snapshot() -> dict[str, Any]:
    with job_state._recognition_training_lock:
        return dict(job_state._recognition_training_status)
