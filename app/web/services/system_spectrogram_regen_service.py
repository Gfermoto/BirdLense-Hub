"""Фоновая перегенерация спектрограмм для UI system API (#293)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import routes.ui_system_jobs_state as job_state
from app_config.app_config import app_config
from models import Video, db
from util import recordings_dir


def _processor_src_dir() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "processor", "src"),
    )


def run_regenerate_spectrograms_worker(
    flask_app,
    force: bool,
    start_date: str | None,
    end_date: str | None,
    video_ids: list[int] | None = None,
) -> None:
    """Background task: regenerate spectrograms (mutates job_state._regenerate_status)."""
    ids_sorted = sorted({int(x) for x in (video_ids or []) if x is not None})
    active_request_video_id = ids_sorted[0] if len(ids_sorted) == 1 else None
    job_state._regenerate_status = {
        "status": "running",
        "result": None,
        "error": None,
        "progress": {
            "processed": 0,
            "total": 0,
            "generated": 0,
            "failed": 0,
            "skipped": 0,
            "active_request_video_id": active_request_video_id,
            "phase": "scanning",
        },
    }
    try:
        with flask_app.app_context():
            try:
                sys.path.insert(0, _processor_src_dir())
                from spectrogram import generate_spectrogram
            except ImportError:
                flask_app.logger.exception("Spectrogram import failed")
                job_state._regenerate_status = {
                    "status": "done",
                    "result": None,
                    "error": "Spectrogram generation failed",
                    "progress": None,
                }
                return

            base = os.path.dirname(os.path.dirname(recordings_dir()))
            px_per_sec = app_config.get("processor.spectrogram_px_per_sec") or 200
            spectrogram_filename = f"spectrogram_{px_per_sec}.jpg"

            query = Video.query
            if ids_sorted:
                query = query.filter(Video.id.in_(ids_sorted))
            elif not force:
                query = query.filter((Video.spectrogram_path.is_(None)) | (Video.spectrogram_path == ""))
            if start_date:
                try:
                    dt_start = datetime.strptime(start_date, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc,
                    )
                    query = query.filter(Video.start_time >= dt_start)
                except ValueError:
                    pass
            if end_date:
                try:
                    dt_end = datetime.strptime(end_date, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc,
                    ) + timedelta(days=1)
                    query = query.filter(Video.start_time < dt_end)
                except ValueError:
                    pass
            videos = query.order_by(Video.start_time.asc()).all()

            total = len(videos)
            job_state._regenerate_status["progress"]["total"] = total

            generated = 0
            failed = 0
            skipped = 0

            for video in videos:
                job_state._regenerate_status["progress"].update(
                    current_video=video.video_path,
                    current_video_id=video.id,
                    phase="spectrogram",
                )
                if not video.video_path:
                    skipped += 1
                    job_state._regenerate_status["progress"].update(
                        processed=generated + failed + skipped,
                        generated=generated,
                        failed=failed,
                        skipped=skipped,
                    )
                    continue
                full_video = os.path.join(base, video.video_path)
                if not os.path.isfile(full_video):
                    skipped += 1
                    job_state._regenerate_status["progress"].update(
                        processed=generated + failed + skipped,
                        generated=generated,
                        failed=failed,
                        skipped=skipped,
                    )
                    continue
                out_dir = os.path.dirname(full_video)
                out_path = os.path.join(out_dir, spectrogram_filename)

                if generate_spectrogram(full_video, out_path, px_per_sec):
                    rel_spectrogram = os.path.join(os.path.dirname(video.video_path), spectrogram_filename).replace(
                        "\\", "/"
                    )
                    video.spectrogram_path = rel_spectrogram
                    generated += 1
                else:
                    failed += 1

                job_state._regenerate_status["progress"].update(
                    processed=generated + failed + skipped,
                    generated=generated,
                    failed=failed,
                    skipped=skipped,
                )

            try:
                db.session.commit()
                flask_app.logger.info(
                    "Spectrograms: generated=%s, failed=%s, skipped=%s",
                    generated,
                    failed,
                    skipped,
                )
                result = {"generated": generated, "failed": failed, "skipped": skipped}
                if ids_sorted:
                    result["target_video_ids"] = list(ids_sorted)
                job_state._regenerate_status = {
                    "status": "done",
                    "result": result,
                    "error": None,
                    "progress": None,
                }
            except Exception as e:
                db.session.rollback()
                flask_app.logger.exception("Spectrogram commit failed: %s", e)
                job_state._regenerate_status = {
                    "status": "done",
                    "result": None,
                    "error": "Spectrogram generation failed",
                    "progress": None,
                }
    except Exception:
        flask_app.logger.exception("Regenerate spectrograms failed")
        job_state._regenerate_status = {
            "status": "done",
            "result": None,
            "error": "Spectrogram generation failed",
            "progress": None,
        }
