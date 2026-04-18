"""Фоновые задачи fusion export/eval и refresh Telegram proxy (#293)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import routes.ui_system_jobs_state as job_state
from services.fusion_training_service import (
    latest_fusion_eval_report_path,
    latest_fusion_export_path,
    run_fusion_eval_job,
    run_fusion_export_job,
)
from services.telegram_proxy_service import (
    refresh_telegram_proxy as refresh_telegram_proxy_service,
)

if TYPE_CHECKING:
    from flask import Flask


def start_fusion_export_background(flask_app: Flask) -> tuple[dict, int]:
    with job_state._fusion_export_lock:
        if job_state._fusion_export_status["status"] == "running":
            return {
                "error": "Fusion export already in progress",
                "status": job_state._fusion_export_status,
            }, 409
        job_state._fusion_export_status.update(
            {
                "status": "running",
                "result": None,
                "error": None,
                "progress": None,
            }
        )

    def _run() -> None:
        try:
            with flask_app.app_context():
                result = run_fusion_export_job()
            with job_state._fusion_export_lock:
                job_state._fusion_export_status.update(
                    {
                        "status": "done",
                        "result": result,
                        "error": None,
                        "progress": None,
                    }
                )
        except Exception as e:
            with job_state._fusion_export_lock:
                job_state._fusion_export_status.update(
                    {
                        "status": "error",
                        "result": None,
                        "error": str(e),
                        "progress": None,
                    }
                )

    threading.Thread(target=_run, daemon=True).start()
    return {
        "message": "Fusion export started",
        "status": dict(job_state._fusion_export_status),
    }, 202


def fusion_export_status_snapshot() -> dict[str, Any]:
    with job_state._fusion_export_lock:
        return dict(job_state._fusion_export_status)


def fusion_export_download_file_or_error() -> tuple[Path | None, dict | None, int]:
    latest = latest_fusion_export_path()
    if not latest or not latest.exists():
        return None, {"error": "Fusion export not found"}, 404
    return latest, None, 200


def fusion_eval_download_file_or_error() -> tuple[Path | None, dict | None, int]:
    latest = latest_fusion_eval_report_path()
    if not latest or not latest.exists():
        return None, {"error": "Fusion eval report CSV not found; run Evaluate first."}, 404
    return latest, None, 200


def start_fusion_eval_background(
    flask_app: Flask,
    payload: dict | None,
) -> tuple[dict, int]:
    with job_state._fusion_eval_lock:
        if job_state._fusion_eval_status["status"] == "running":
            return {
                "error": "Fusion eval already in progress",
                "status": job_state._fusion_eval_status,
            }, 409
        job_state._fusion_eval_status.update(
            {
                "status": "running",
                "result": None,
                "error": None,
                "progress": None,
            }
        )
    data = payload or {}

    def _run() -> None:
        try:
            with flask_app.app_context():
                result = run_fusion_eval_job(
                    source_csv=data.get("source_csv"),
                    model_path=data.get("model_path"),
                    score_col=data.get("score_col"),
                    label_col=data.get("label_col", "valid_track_label"),
                    slice_fields=list(data.get("slice_fields") or []),
                )
            with job_state._fusion_eval_lock:
                job_state._fusion_eval_status.update(
                    {
                        "status": "done",
                        "result": result,
                        "error": None,
                        "progress": None,
                    }
                )
        except Exception as e:
            with job_state._fusion_eval_lock:
                job_state._fusion_eval_status.update(
                    {
                        "status": "error",
                        "result": None,
                        "error": str(e),
                        "progress": None,
                    }
                )

    threading.Thread(target=_run, daemon=True).start()
    return {
        "message": "Fusion eval started",
        "status": dict(job_state._fusion_eval_status),
    }, 202


def fusion_eval_status_snapshot() -> dict[str, Any]:
    with job_state._fusion_eval_lock:
        return dict(job_state._fusion_eval_status)


def start_telegram_proxy_refresh_background(flask_app: Flask) -> tuple[dict, int]:
    with job_state._telegram_proxy_refresh_lock:
        if job_state._telegram_proxy_refresh_status["status"] == "running":
            return {
                "error": "Telegram proxy refresh already in progress",
                "status": job_state._telegram_proxy_refresh_status,
            }, 409
        job_state._telegram_proxy_refresh_status.update(
            {
                "status": "running",
                "result": None,
                "error": None,
                "progress": None,
            }
        )

    def _run() -> None:
        try:
            with flask_app.app_context():
                result = refresh_telegram_proxy_service()
            with job_state._telegram_proxy_refresh_lock:
                job_state._telegram_proxy_refresh_status.update(
                    {
                        "status": "done",
                        "result": result,
                        "error": None,
                        "progress": None,
                    }
                )
        except Exception as e:
            with job_state._telegram_proxy_refresh_lock:
                job_state._telegram_proxy_refresh_status.update(
                    {
                        "status": "error",
                        "result": None,
                        "error": str(e),
                        "progress": None,
                    }
                )

    threading.Thread(target=_run, daemon=True).start()
    return {
        "message": "Telegram proxy refresh started",
        "status": dict(job_state._telegram_proxy_refresh_status),
    }, 202


def telegram_proxy_refresh_status_snapshot() -> dict[str, Any]:
    with job_state._telegram_proxy_refresh_lock:
        return dict(job_state._telegram_proxy_refresh_status)
