"""Unified async job registry for long-running UI operations (SOTA-22 / #513)."""

from __future__ import annotations

from typing import Any, Callable

from flask import Flask

import routes.ui_system_jobs_state as job_state
from services.species_registry_admin_service import (
    repair_catalog_cards_status_snapshot,
    start_metadata_enrichment,
    start_repair_catalog_cards,
)
from services.system_admin_api_service import (
    start_single_video_track_regeneration,
)
from services.system_fusion_telegram_jobs_service import (
    start_fusion_eval_background,
    start_fusion_export_background,
    start_telegram_proxy_refresh_background,
)

JobStartFn = Callable[[Flask, dict[str, Any]], tuple[dict[str, Any], int]]

_JOB_SPECS: dict[str, dict[str, Any]] = {
    "track_regen": {
        "label": "Track regeneration (YOLO+ByteTrack)",
        "state_attr": "_regenerate_tracks_status",
        "lock_attr": "_regenerate_tracks_lock",
        "cancel_attr": "_regenerate_tracks_cancel_requested",
        "password_required": False,
        "admin_track_regen": True,
    },
    "catalog_repair": {
        "label": "Catalog card repair",
        "state_attr": "_catalog_cards_status",
        "lock_attr": "_catalog_cards_lock",
        "password_required": True,
    },
    "species_metadata": {
        "label": "Species metadata enrichment",
        "state_attr": "_species_metadata_status",
        "lock_attr": "_species_metadata_lock",
        "password_required": True,
    },
    "fusion_export": {
        "label": "Fusion training export",
        "state_attr": "_fusion_export_status",
        "lock_attr": "_fusion_export_lock",
        "password_required": True,
    },
    "fusion_eval": {
        "label": "Fusion calibration eval",
        "state_attr": "_fusion_eval_status",
        "lock_attr": "_fusion_eval_lock",
        "password_required": True,
    },
    "telegram_proxy_refresh": {
        "label": "Telegram proxy refresh",
        "state_attr": "_telegram_proxy_refresh_status",
        "lock_attr": "_telegram_proxy_refresh_lock",
        "password_required": True,
    },
}


def list_job_types() -> list[str]:
    return sorted(_JOB_SPECS.keys())


def normalize_job_payload(job_id: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    """Stable job document for GET /jobs and GET /jobs/{id}."""
    spec = _JOB_SPECS[job_id]
    state = getattr(job_state, spec["state_attr"])
    out: dict[str, Any] = {
        "id": job_id,
        "type": job_id,
        "label": spec["label"],
        "status": state.get("status") or "idle",
        "result": state.get("result"),
        "error": state.get("error"),
        "progress": state.get("progress"),
        "cancel_requested": bool(getattr(job_state, spec.get("cancel_attr", ""), False)),
    }
    return out


def list_jobs_payload() -> dict[str, Any]:
    return {"jobs": [normalize_job_payload(jid, None) for jid in list_job_types()]}


def get_job_payload(job_id: str) -> tuple[dict[str, Any], int]:
    if job_id not in _JOB_SPECS:
        return {"error": f"Unknown job id: {job_id}"}, 404
    return normalize_job_payload(job_id, None), 200


def _start_track_regen(flask_app: Flask, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    video_id = payload.get("video_id")
    if video_id is not None:
        try:
            vid = int(video_id)
        except (TypeError, ValueError):
            return {"error": "video_id must be int"}, 400
        return start_single_video_track_regeneration(flask_app, vid, payload)
    return {
        "error": "Bulk track_regen: pass video_id (single-video regen). Use processor/UI batch entry for multi-video.",
    }, 400


def _start_catalog_repair(flask_app: Flask, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    return start_repair_catalog_cards(flask_app, payload)


def _start_species_metadata(flask_app: Flask, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    return start_metadata_enrichment(flask_app, payload)


def _start_fusion_export(flask_app: Flask, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    del payload
    return start_fusion_export_background(flask_app)


def _start_fusion_eval(flask_app: Flask, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    return start_fusion_eval_background(flask_app, payload)


def _start_telegram_proxy(flask_app: Flask, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    del payload
    return start_telegram_proxy_refresh_background(flask_app)


_STARTERS: dict[str, JobStartFn] = {
    "track_regen": _start_track_regen,
    "catalog_repair": _start_catalog_repair,
    "species_metadata": _start_species_metadata,
    "fusion_export": _start_fusion_export,
    "fusion_eval": _start_fusion_eval,
    "telegram_proxy_refresh": _start_telegram_proxy,
}


def start_job(flask_app: Flask, job_type: str, payload: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    if job_type not in _JOB_SPECS:
        return {"error": f"Unknown job type: {job_type}", "allowed": list_job_types()}, 400
    starter = _STARTERS[job_type]
    spec = _JOB_SPECS[job_type]
    cancel_attr = spec.get("cancel_attr")
    if cancel_attr:
        setattr(job_state, cancel_attr, False)
    body, code = starter(flask_app, payload or {})
    if code in (200, 202):
        body = {**body, "job_id": job_type, "job": normalize_job_payload(job_type, None)}
    return body, code


def request_job_cancel(job_id: str) -> tuple[dict[str, Any], int]:
    spec = _JOB_SPECS.get(job_id)
    if not spec:
        return {"error": f"Unknown job id: {job_id}"}, 404
    cancel_attr = spec.get("cancel_attr")
    if not cancel_attr:
        return {"error": f"Job {job_id} does not support cancel"}, 400
    state = getattr(job_state, spec["state_attr"])
    if state.get("status") != "running":
        return {"error": "Job is not running", "job": normalize_job_payload(job_id, None)}, 409
    setattr(job_state, cancel_attr, True)
    return {"ok": True, "job_id": job_id, "job": normalize_job_payload(job_id, None)}, 200


def catalog_repair_job_snapshot() -> dict[str, Any]:
    """Extra fields for catalog repair (schedule + coverage)."""
    snap = repair_catalog_cards_status_snapshot()
    base = normalize_job_payload("catalog_repair", None)
    base.update(snap)
    return base
