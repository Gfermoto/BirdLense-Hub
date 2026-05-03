"""ML/CV operator helpers that work without new model weights."""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import joinedload

from app_config.app_config import app_config
from models import Video, VideoSpecies
from util import ensure_utc


def build_video_action_events_payload(session, video_id: int) -> tuple[dict[str, Any], int]:
    """Weak behavior labels from existing tracks and feeder-weight evidence (#379)."""
    video = session.get(Video, int(video_id))
    if not video:
        return {"error": "Video not found"}, 404

    rows = (
        session.query(VideoSpecies)
        .options(joinedload(VideoSpecies.species))
        .filter(VideoSpecies.video_id == video.id)
        .order_by(VideoSpecies.start_time.asc(), VideoSpecies.id.asc())
        .all()
    )
    if not rows:
        return {
            "schema": "video_action_events@v1",
            "video_id": video.id,
            "available": False,
            "message": "no_video_tracks",
            "events": [],
        }, 200

    video_start = ensure_utc(video.start_time)
    first = rows[0]
    last = rows[-1]
    events: list[dict[str, Any]] = []

    def _event(label: str, offset: float, confidence: float, evidence: dict[str, Any]) -> dict[str, Any]:
        return {
            "label": label,
            "source": "weak_label",
            "time_offset": round(float(offset), 3),
            "time": (video_start + timedelta(seconds=float(offset))).astimezone(timezone.utc).isoformat(),
            "confidence": round(max(0.0, min(float(confidence), 1.0)), 4),
            "evidence": evidence,
        }

    events.append(
        _event(
            "arrival",
            first.start_time,
            0.55,
            {
                "track_id": first.track_id,
                "species_name": getattr(first.species, "name", None),
                "reason": "first_track_start",
            },
        )
    )

    weight_delta = getattr(video, "scales_weight_delta_kg", None)
    if weight_delta is not None and abs(float(weight_delta)) > 0:
        mid = (float(first.start_time) + float(last.end_time)) / 2.0
        events.append(
            _event(
                "possible_feeding",
                mid,
                0.5,
                {
                    "reason": "feeder_weight_delta",
                    "scales_weight_delta_kg": float(weight_delta),
                    "track_count": len(rows),
                },
            )
        )

    events.append(
        _event(
            "departure",
            last.end_time,
            0.5,
            {
                "track_id": last.track_id,
                "species_name": getattr(last.species, "name", None),
                "reason": "last_track_end",
            },
        )
    )

    return {
        "schema": "video_action_events@v1",
        "video_id": video.id,
        "available": True,
        "events": events,
    }, 200


def build_active_learning_pool_preview(session, *, limit: int = 100) -> tuple[dict[str, Any], int]:
    """Preview uncertain review items as AL pool candidates (#369)."""
    limit = min(max(int(limit or 100), 1), 500)
    rows = (
        session.query(VideoSpecies)
        .options(joinedload(VideoSpecies.video), joinedload(VideoSpecies.species))
        .filter(VideoSpecies.manually_corrected.is_(False))
        .filter(
            (VideoSpecies.classifier_needs_review.is_(True))
            | (VideoSpecies.review_reason.isnot(None))
            | (VideoSpecies.confidence < 0.5)
        )
        .order_by(VideoSpecies.created_at.desc(), VideoSpecies.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for row in rows:
        items.append(
            {
                "video_species_id": row.id,
                "video_id": row.video_id,
                "video_path": getattr(row.video, "video_path", None),
                "species_name": getattr(row.species, "name", None),
                "track_id": row.track_id,
                "confidence": row.confidence,
                "review_reason": row.review_reason,
                "classifier_entropy": row.classifier_entropy,
                "classifier_top1_top2_margin": row.classifier_top1_top2_margin,
                "classifier_needs_review": bool(row.classifier_needs_review),
            }
        )
    return {
        "schema": "active_learning_pool_preview@v1",
        "count": len(items),
        "items": items,
    }, 200


def build_reid_summary(session) -> tuple[dict[str, Any], int]:
    """Read-only summary of offline Re-ID sidecar table (#374)."""
    try:
        exists = session.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reid_embedding'")
        ).scalar()
    except Exception:
        exists = None
    if not exists:
        return {
            "schema": "reid_summary@v1",
            "available": False,
            "embedding_count": 0,
            "recent": [],
        }, 200

    count = int(session.execute(text("SELECT COUNT(*) FROM reid_embedding")).scalar() or 0)
    try:
        rows = (
            session.execute(
                text(
                    "SELECT id, video_id, video_species_id, species_id, track_id "
                    "FROM reid_embedding ORDER BY id DESC LIMIT 20"
                )
            )
            .mappings()
            .all()
        )
    except Exception:
        rows = []
    return {
        "schema": "reid_summary@v1",
        "available": True,
        "embedding_count": count,
        "recent": [dict(r) for r in rows],
    }, 200


def build_ml_runtime_status() -> tuple[dict[str, Any], int]:
    """Operator-facing ML/CV runtime config state (#373/#372)."""
    return {
        "schema": "ml_runtime_status@v1",
        "video": {
            "encoding": app_config.get("video.encoding"),
            "capture_backend_config": app_config.get("video.capture_backend"),
        },
        "processor": {
            "inference_backend": app_config.get("processor.inference_backend"),
            "inference_device": app_config.get("processor.inference_device"),
            "classifier_inference_backend": app_config.get(
                "processor.classifier_inference_backend",
            )
            or app_config.get("processor.inference_backend"),
            "classifier_inference_device": app_config.get(
                "processor.classifier_inference_device",
            )
            or app_config.get("processor.inference_device"),
            "detector_weight_contract": app_config.get("processor.detector_weight_contract"),
            "binary_imgsz": app_config.get("processor.binary_imgsz"),
            "frame_processing_warn_ms": app_config.get("processor.frame_processing_warn_ms"),
        },
    }, 200
