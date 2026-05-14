"""HTTP API процессора: приём видео/детекций, вебхуки, защита секретом и SSRF-гварды.

Доменная логика: ``services.processor_ingest`` — ``gateway``, ``video_ingest``,
``notify_ingest``, ``activity_log_ingest`` ([#344](https://github.com/Gfermoto/BirdLense-Hub/issues/344)).
"""

import os
import hashlib
import json
import threading
from datetime import timezone

from flask import request
from sqlalchemy.exc import IntegrityError

from models import db, BirdFood, Video, VideoSpecies, Species
from util import fetch_weather, notify, filter_feeder_species
from services.visit_processor import VisitProcessor
from app_config.app_config import app_config
from services.api_json_validation import (
    parse_request_json_array_allow_empty,
    parse_request_json_dict,
    parse_request_json_object_allow_empty,
)
from services.http_response_cache import bust_response_caches
from services.processor_ingest.gateway import (
    check_processor_secret_token,
    fire_webhook,
    is_safe_webhook_url,
)
from services.runtime_env import is_production_runtime
from services.processor_ingest.activity_log_ingest import upsert_activity_log_from_processor
from services.processor_ingest.notify_ingest import process_processor_notify_detections
from services.processor_ingest.video_ingest import prepare_processor_video
from recording_layout_paths import RECORDING_VIDEO_PATH_RE

# Path traversal protection (см. recording_layout_paths + SECURITY.md).
VIDEO_PATH_RE = RECORDING_VIDEO_PATH_RE


def _as_utc_naive(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _iso_utc_naive(dt) -> str:
    value = _as_utc_naive(dt)
    return value.isoformat() if value is not None else ""


def _build_clip_idempotency_key(*, processor_version: str, pv) -> str:
    seed = "|".join(
        [
            str(processor_version or "").strip(),
            str(pv.video_path or "").strip(),
            _iso_utc_naive(pv.start_time),
            _iso_utc_naive(pv.end_time),
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _canonical_float(value, *, ndigits: int = 6) -> float:
    try:
        return round(float(value or 0.0), ndigits)
    except (TypeError, ValueError):
        return 0.0


def _canonical_track_id(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _canonical_detection_row(row: dict) -> dict:
    def _canonical_frames(value):
        if value is None:
            return []
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return value
        return value

    return {
        "species_name": str(row.get("species_name") or row.get("species") or "").strip(),
        "source": str(row.get("source") or "").strip(),
        "detection_provider": str(row.get("detection_provider") or "").strip(),
        "track_id": _canonical_track_id(row.get("track_id")),
        "start_time": _canonical_float(row.get("start_time")),
        "end_time": _canonical_float(row.get("end_time")),
        "confidence": _canonical_float(row.get("confidence")),
        "classifier_entropy": _canonical_float(row.get("classifier_entropy")),
        "classifier_top1_top2_margin": _canonical_float(row.get("classifier_top1_top2_margin")),
        "classifier_needs_review": bool(row.get("classifier_needs_review", False)),
        "review_reason": str(row.get("review_reason") or "").strip(),
        "individual_nickname": str(row.get("individual_nickname") or "").strip(),
        "frames": _canonical_frames(row.get("frames")),
    }


def _build_species_payload_hash(*, species_list: list[dict]) -> str:
    normalized_rows = [_canonical_detection_row(row or {}) for row in (species_list or [])]
    normalized_rows.sort(
        key=lambda item: (
            item["species_name"],
            item["source"],
            item["detection_provider"],
            item["track_id"] if item["track_id"] is not None else -1,
            item["start_time"],
            item["end_time"],
            item["confidence"],
            item["classifier_entropy"],
            item["classifier_top1_top2_margin"],
            item["classifier_needs_review"],
            item["review_reason"],
            item["individual_nickname"],
            json.dumps(item["frames"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
    )
    payload = json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_payload_hash_for_existing_video(video_id: int) -> str:
    rows = (
        db.session.query(VideoSpecies, Species)
        .join(Species, Species.id == VideoSpecies.species_id)
        .filter(VideoSpecies.video_id == int(video_id))
        .order_by(VideoSpecies.id.asc())
        .all()
    )
    species_rows: list[dict] = []
    for detection, species in rows:
        species_rows.append(
            _canonical_detection_row(
                {
                    "species_name": str(species.name or "").strip(),
                    "source": detection.source,
                    "detection_provider": detection.detection_provider,
                    "track_id": detection.track_id,
                    "start_time": detection.start_time,
                    "end_time": detection.end_time,
                    "confidence": detection.confidence,
                    "classifier_entropy": detection.classifier_entropy,
                    "classifier_top1_top2_margin": detection.classifier_top1_top2_margin,
                    "classifier_needs_review": detection.classifier_needs_review,
                    "review_reason": detection.review_reason,
                    "individual_nickname": detection.individual_nickname,
                    "frames": detection.frames,
                }
            )
        )
    return _build_species_payload_hash(species_list=species_rows)


def _find_existing_video_for_idempotent_ingest(*, processor_version: str, pv, clip_key: str):
    """Return existing Video for identical clip key (path/time/version)."""
    existing_by_key = Video.query.filter_by(idempotency_key=clip_key, deleted_at=None).order_by(Video.id.desc()).first()
    if existing_by_key is not None:
        return existing_by_key
    # Legacy fallback for rows created before idempotency_key migration.
    existing = Video.query.filter_by(video_path=pv.video_path, deleted_at=None).order_by(Video.id.desc()).first()
    if not existing:
        return None
    same_version = str(existing.processor_version or "") == str(processor_version or "")
    same_start = _as_utc_naive(existing.start_time) == _as_utc_naive(pv.start_time)
    same_end = _as_utc_naive(existing.end_time) == _as_utc_naive(pv.end_time)
    if same_version and same_start and same_end:
        return existing
    return None


def _idempotency_conflict_response(*, app_logger, video_id: int, reason: str):
    conflict_reason = str(reason or "").strip() or "payload_hash_mismatch"
    app_logger.warning(
        "processor_ingest idempotency conflict: video_id=%s reason=%s",
        video_id,
        conflict_reason,
    )
    return {
        "error": "Idempotency conflict for existing clip key",
        "video_id": video_id,
        "conflict_reason": conflict_reason,
    }, 409


def _check_processor_secret():
    """Return True if request is from processor (has valid secret). In production, empty secret blocks access."""
    return check_processor_secret_token(
        request_token=request.headers.get("X-Processor-Token") or "",
        env_secret=os.environ.get("PROCESSOR_SECRET", ""),
        is_prod=is_production_runtime(),
    )


def register_routes(app):
    """Зарегистрировать маршруты ``/api/processor/*`` на переданном Flask-приложении."""

    @app.route("/api/processor/videos", methods=["POST"])
    def create_video():
        if not _check_processor_secret():
            return {"error": "Forbidden"}, 403
        data, perr = parse_request_json_dict(request)
        if perr is not None:
            return perr, 400
        if not data:
            return {"error": "JSON body required"}, 400
        min_conf = float(app_config.get("detection.min_confidence_to_store") or 0.05)
        prep = prepare_processor_video(data, min_confidence=min_conf)
        if prep[0] is False:
            return prep[1], prep[2]
        pv = prep[1]
        clip_key = _build_clip_idempotency_key(
            processor_version=data["processor_version"],
            pv=pv,
        )
        payload_hash = _build_species_payload_hash(species_list=pv.species_list)
        existing_video = _find_existing_video_for_idempotent_ingest(
            processor_version=data["processor_version"],
            pv=pv,
            clip_key=clip_key,
        )
        if existing_video is not None:
            existing_payload_hash = str(existing_video.ingest_payload_hash or "").strip()
            if not existing_payload_hash:
                existing_payload_hash = _build_payload_hash_for_existing_video(existing_video.id)
                existing_video.ingest_payload_hash = existing_payload_hash
                db.session.commit()
            if existing_payload_hash != payload_hash:
                return _idempotency_conflict_response(
                    app_logger=app.logger,
                    video_id=existing_video.id,
                    reason="payload_hash_mismatch",
                )
            return {
                "message": "Video already ingested.",
                "video_id": existing_video.id,
                "duplicate": True,
            }, 200

        try:
            video = Video(
                processor_version=data["processor_version"],
                start_time=pv.start_time,
                end_time=pv.end_time,
                video_path=pv.video_path,
                idempotency_key=clip_key,
                ingest_payload_hash=payload_hash,
                spectrogram_path=pv.spectrogram_path,
                **fetch_weather(),
            )
            raw_sw = data.get("scales_weight_delta_kg")
            if raw_sw is not None and app_config.get("integrations.scales.enabled"):
                try:
                    swf = float(raw_sw)
                    if swf >= 0 and swf <= 50:
                        video.scales_weight_delta_kg = swf
                except (TypeError, ValueError):
                    pass
            db.session.add(video)

            raw_bl = data.get("behavior_label")
            raw_bc = data.get("behavior_confidence")
            if isinstance(raw_bl, str) and raw_bl.strip():
                video.behavior_label = raw_bl.strip()[:32]
            if raw_bc is not None:
                try:
                    video.behavior_confidence = float(raw_bc)
                except (TypeError, ValueError):
                    pass

            # Add active bird foods
            active_bird_foods = BirdFood.query.filter_by(active=True).all()
            video.food.extend(active_bird_foods)

            visit_timeout = int(app_config.get("detection.dedup_window_seconds") or 60)
            visit_processor = VisitProcessor(db, app.logger, visit_timeout=visit_timeout)
            visit_processor.process_detections(video, pv.species_list)

            db.session.commit()
            bust_response_caches()

            # Webhook: fire-and-forget
            webhook_url = (app_config.get("webhook.url") or "").strip()
            if webhook_url and pv.species_list:
                if is_safe_webhook_url(webhook_url):
                    threading.Thread(
                        target=fire_webhook,
                        args=(webhook_url, pv.species_list, pv.start_time, app.logger),
                        daemon=True,
                    ).start()
                else:
                    app.logger.warning("Unsafe webhook.url blocked: %s", webhook_url)

            return {"message": "Video and associated data inserted successfully.", "video_id": video.id}, 201

        except IntegrityError:
            db.session.rollback()
            raced_video = (
                Video.query.filter_by(idempotency_key=clip_key, deleted_at=None).order_by(Video.id.desc()).first()
            )
            if raced_video is not None:
                existing_payload_hash = str(raced_video.ingest_payload_hash or "").strip()
                if not existing_payload_hash:
                    existing_payload_hash = _build_payload_hash_for_existing_video(raced_video.id)
                    raced_video.ingest_payload_hash = existing_payload_hash
                    db.session.commit()
                if existing_payload_hash != payload_hash:
                    return _idempotency_conflict_response(
                        app_logger=app.logger,
                        video_id=raced_video.id,
                        reason="payload_hash_mismatch_race",
                    )
                return {
                    "message": "Video already ingested.",
                    "video_id": raced_video.id,
                    "duplicate": True,
                }, 200
            return {"error": "Failed to process video"}, 500
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error processing video: {str(e)}")
            return {"error": "Failed to process video"}, 500

    @app.route("/api/processor/species/active", methods=["PUT"])
    def set_active_species():
        """Set which species are active (from YOLO regional list or config)."""
        if not _check_processor_secret():
            return {"error": "Forbidden"}, 403
        active_names, perr = parse_request_json_array_allow_empty(request)
        if perr is not None:
            return perr, 400
        if len(active_names) > 500:
            return {"error": "Too many species (max 500)"}, 400
        for name in active_names:
            if not isinstance(name, str) or len(name) > 100:
                return {"error": "Invalid species name"}, 400
        if not active_names:
            return {"message": "success", "active_feeder_names": []}, 200
        active_feeder_names = filter_feeder_species(active_names)

        db.session.query(Species).update({"active": False})
        for name in active_feeder_names:
            species = db.session.query(Species).filter_by(name=name).first()
            if species:
                species.active = True
            else:
                app.logger.warning(f'Unknown active species "{name}"')

        db.session.commit()
        return {"message": "success", "active_feeder_names": active_feeder_names}, 200

    @app.route("/api/processor/notify/detections", methods=["POST"])
    def notify_detections_route():
        if not _check_processor_secret():
            return {"error": "Forbidden"}, 403
        data, perr = parse_request_json_object_allow_empty(request)
        if perr is not None:
            return perr, 400
        excluded = app_config.get("general.notification_excluded_species", [])
        return process_processor_notify_detections(
            data,
            logger=app.logger,
            notify_fn=notify,
            excluded_species=excluded,
        )

    @app.route("/api/processor/notify/motion", methods=["POST"])
    def notify_motion_route():
        if not _check_processor_secret():
            return {"error": "Forbidden"}, 403
        return {"message": "Successfully received notification of motion"}, 200

    @app.route("/api/processor/activity_log", methods=["POST"])
    def add_or_update_activity_log():
        if not _check_processor_secret():
            app.logger.warning("activity_log: 403 Forbidden (PROCESSOR_SECRET mismatch)")
            return {"error": "Forbidden"}, 403
        data, perr = parse_request_json_object_allow_empty(request)
        if perr is not None:
            return perr, 400
        return upsert_activity_log_from_processor(data, logger=app.logger)
