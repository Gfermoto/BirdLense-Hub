"""HTTP API процессора: приём видео/детекций, вебхуки, защита секретом и SSRF-гварды.

Доменная логика: ``services.processor_ingest`` — ``gateway``, ``video_ingest``
([#344](https://github.com/Gfermoto/BirdLense-Hub/issues/344)).
"""

import json
import os
import threading
from datetime import datetime, timezone

from flask import request

from models import ActivityLog, db, BirdFood, Video, Species
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
    log_ingest_activity,
)
from services.processor_ingest.video_ingest import prepare_processor_video
from recording_layout_paths import RECORDING_VIDEO_PATH_RE

# Path traversal protection (см. recording_layout_paths + SECURITY.md).
VIDEO_PATH_RE = RECORDING_VIDEO_PATH_RE


def _check_processor_secret():
    """Return True if request is from processor (has valid secret). In production, empty secret blocks access."""
    is_prod = os.environ.get("FLASK_ENV") == "production" or os.environ.get("BIRDLENSE_ENV") == "production"
    return check_processor_secret_token(
        request_token=request.headers.get("X-Processor-Token") or "",
        env_secret=os.environ.get("PROCESSOR_SECRET", ""),
        is_prod=is_prod,
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

        try:
            video = Video(
                processor_version=data["processor_version"],
                start_time=pv.start_time,
                end_time=pv.end_time,
                video_path=pv.video_path,
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
        detection = data.get("detection")
        image_path = data.get("image_path")
        image_base64 = data.get("image_base64")
        link = data.get("link") or "live"
        preview_source = data.get("preview_source") or "unknown"
        notification_eligible = bool(data.get("notification_eligible", True))
        suppress_reason = str(data.get("suppress_reason") or "").strip() or "notification_ineligible"
        image_bytes = None
        image_status = "missing"
        if not notification_eligible:
            app.logger.info(
                "notify/detections: suppressed %s (eligible=false, reason=%s, preview_source=%s)",
                detection,
                suppress_reason,
                preview_source,
            )
            log_ingest_activity(
                "notify_suppressed",
                {
                    "species": detection,
                    "preview_source": preview_source,
                    "suppress_reason": suppress_reason,
                    "telegram_delivery": "skipped",
                    "has_image": bool(image_base64 or image_path),
                },
            )
            return {"message": f"Successfully received notification of {detection}", "skipped": True}, 200
        if image_base64:
            try:
                import base64

                image_bytes = base64.b64decode(image_base64)
            except Exception as e:
                app.logger.warning("Failed to decode image_base64 for notify: %s", e)
                image_status = "decode_failed"
        if image_base64 and not image_bytes:
            app.logger.warning("notify/detections: image_base64 present but decode produced empty bytes")
            image_status = "decode_failed"
        elif not image_base64:
            app.logger.info(
                "notify/detections: no image for %s (preview_source=%s)",
                detection,
                preview_source,
            )
            image_status = "missing"
        else:
            app.logger.info(
                "notify/detections: image present for %s (preview_source=%s, bytes=%s)",
                detection,
                preview_source,
                len(image_bytes or b""),
            )
            image_status = "present"
        if not image_base64 and not image_path:
            app.logger.info(
                "notify/detections: skipped %s (no preview context, preview_source=%s)",
                detection,
                preview_source,
            )
            try:
                db.session.add(
                    ActivityLog(
                        type="notify_preview",
                        data=json.dumps(
                            {
                                "species": detection,
                                "preview_source": preview_source,
                                "has_image": False,
                                "image_status": image_status,
                                "telegram_delivery": "skipped",
                                "photo_requested": False,
                                "photo_available": False,
                                "photo_sent": False,
                                "fallback_reason": "no_preview_context",
                            }
                        ),
                    )
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
            return {"message": f"Successfully received notification of {detection}", "skipped": True}, 200
        excluded_species = app_config.get("general.notification_excluded_species", [])
        if detection not in excluded_species:
            lower = detection.lower()
            icon = (
                "chipmunk"
                if any(s in lower for s in ("rodent", "грызун", "squirrel", "chipmunk", "mouse", "мышь", "белка"))
                else "bird"
            )
            notify_result = (
                notify(
                    f"{detection} Detected",
                    tags=icon,
                    image_path=image_path,
                    image_bytes=image_bytes,
                    link=link,
                    timestamp=datetime.now(timezone.utc),
                    fallback_reason_hint="decode_failed" if image_status == "decode_failed" else None,
                )
                or {}
            )
            fallback_reason = notify_result.get("fallback_reason")
            if image_status == "decode_failed":
                fallback_reason = "decode_failed"
            try:
                db.session.add(
                    ActivityLog(
                        type="notify_preview",
                        data=json.dumps(
                            {
                                "species": detection,
                                "preview_source": preview_source,
                                "has_image": bool(image_bytes),
                                "image_status": image_status,
                                "telegram_delivery": notify_result.get("telegram_delivery", "unknown"),
                                "photo_requested": bool(notify_result.get("photo_requested", False)),
                                "photo_available": bool(notify_result.get("photo_available", False)),
                                "photo_sent": bool(notify_result.get("photo_sent", False)),
                                "fallback_reason": fallback_reason,
                            }
                        ),
                    )
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
        return {"message": f"Successfully received notification of {detection}"}, 200

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
        try:
            data, perr = parse_request_json_object_allow_empty(request)
            if perr is not None:
                return perr, 400
            activity_type = data.get("type")
            raw_data = data.get("data")
            activity_data = json.dumps(raw_data) if raw_data is not None else "{}"
            if len(activity_data) > 65536:
                return {"error": "Activity data too large (max 64 KB)"}, 400
            activity_id = data.get("id")
            if activity_id is not None:
                activity_id = int(activity_id)

            if not activity_type:
                return {"error": 'Field "type" is required'}, 400

            if activity_id is None:
                new_log = ActivityLog(type=activity_type, data=activity_data)
                db.session.add(new_log)
                db.session.commit()
                return {"message": "Activity log created successfully", "id": new_log.id}, 201
            else:
                log = db.session.get(ActivityLog, activity_id)
                if not log:
                    return {"error": "Activity log with this ID not found"}, 404
                log.type = activity_type
                log.data = activity_data
                log.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                return {"message": "Activity log updated successfully", "id": log.id}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception("activity_log failed: %s", e)
            return {"error": "Internal server error"}, 500
