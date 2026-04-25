"""Уведомления по детекциям с эндпоинта процессора (Telegram и лог preview)."""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from models import ActivityLog, db

from services.processor_ingest.gateway import log_ingest_activity


def process_processor_notify_detections(
    data: dict,
    *,
    logger: logging.Logger,
    notify_fn: Callable[..., dict[str, Any] | None],
    excluded_species: Sequence[str] | None,
) -> tuple[dict, int]:
    """Логика ``POST /api/processor/notify/detections`` после парсинга JSON."""
    detection = data.get("detection")
    image_path = data.get("image_path")
    image_base64 = data.get("image_base64")
    link = data.get("link") or "live"
    preview_source = data.get("preview_source") or "unknown"
    notification_eligible = bool(data.get("notification_eligible", True))
    suppress_reason = str(data.get("suppress_reason") or "").strip() or "notification_ineligible"
    image_bytes: bytes | None = None
    image_status = "missing"
    excluded = list(excluded_species or [])

    if not notification_eligible:
        logger.info(
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
            image_bytes = base64.b64decode(image_base64)
        except Exception as e:
            logger.warning("Failed to decode image_base64 for notify: %s", e)
            image_status = "decode_failed"
    if image_base64 and not image_bytes:
        logger.warning("notify/detections: image_base64 present but decode produced empty bytes")
        image_status = "decode_failed"
    elif not image_base64:
        logger.info(
            "notify/detections: no image for %s (preview_source=%s)",
            detection,
            preview_source,
        )
        image_status = "missing"
    else:
        logger.info(
            "notify/detections: image present for %s (preview_source=%s, bytes=%s)",
            detection,
            preview_source,
            len(image_bytes or b""),
        )
        image_status = "present"

    if not image_base64 and not image_path:
        logger.info(
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

    if detection not in excluded:
        lower = (detection or "").lower()
        icon = (
            "chipmunk"
            if any(s in lower for s in ("rodent", "грызун", "squirrel", "chipmunk", "mouse", "мышь", "белка"))
            else "bird"
        )
        notify_result = (
            notify_fn(
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


__all__ = ["process_processor_notify_detections"]
