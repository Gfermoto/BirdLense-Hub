"""Health, Web Push, cameras, component status, feed, weather, sun-times (#198)."""

import json
import os
import threading
from datetime import datetime, timezone, timedelta

from flask import request

from app_config.app_config import app_config
from app_config.cameras import cameras_for_api, get_valid_cameras
from auth import (
    contributor_or_admin_access,
    mcp_bearer_authorized,
    settings_check_access,
)
from models import ActivityLog, db
from services.cache import cache_get, cache_set
from services.api_json_validation import parse_request_json_dict
from services.component_status_service import build_component_status_payload_safe
from services.readiness_service import build_readiness_payload
from services.feed_service import dispense_feed, get_last_dispense
from services.web_push_service import (
    PushSubscriptionBodyError,
    enable_web_push_and_save,
    get_vapid_public_key,
    parse_push_subscription_body,
    upsert_push_subscription,
)
from util import fetch_sun_times, fetch_weather

from routes.ui_route_constants import CACHE_STATUS_SEC

_status_cache_lock = threading.Lock()


def register_ui_status_push_routes(app):
    def _bbox_to_polygon(bbox):
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return None
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox]
        except (TypeError, ValueError):
            return None
        if not (x2 > x1 and y2 > y1):
            return None
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    def _extract_runtime_overlays_from_trace(payload: dict) -> tuple[list, list]:
        trigger_polygons: list = []
        detector_polygons: list = []
        rc = payload.get("recording_context") if isinstance(payload, dict) else {}
        if not isinstance(rc, dict):
            rc = {}
        frigate_ev = rc.get("frigate_trigger_event")
        if isinstance(frigate_ev, dict):
            poly = _bbox_to_polygon(frigate_ev.get("frigate_bbox_norm"))
            if poly:
                trigger_polygons.append(poly)
        tracks = payload.get("persisted_tracks")
        if not isinstance(tracks, list):
            tracks = payload.get("accepted_tracks")
        if isinstance(tracks, list):
            for tr in tracks[:20]:
                if not isinstance(tr, dict):
                    continue
                frames = tr.get("frames") or []
                if isinstance(frames, list) and frames:
                    last = frames[-1]
                    bbox = last.get("bbox") if isinstance(last, dict) else None
                    poly = _bbox_to_polygon(bbox)
                    if poly:
                        detector_polygons.append(poly)
                else:
                    poly = _bbox_to_polygon(tr.get("bbox"))
                    if poly:
                        detector_polygons.append(poly)
        return trigger_polygons, detector_polygons

    def _parse_overlay_updated_at(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), timezone.utc)
            except (TypeError, ValueError, OSError):
                return None
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    """Маршруты без тяжёлых зависимостей от timeline/species/video."""

    @app.route("/api/ui/health", methods=["GET"])
    def health():
        return {"status": "ok"}

    @app.route("/api/ui/readiness", methods=["GET"])
    def readiness():
        payload, status = build_readiness_payload(db.session)
        return payload, status

    @app.route("/api/ui/push/vapid-public", methods=["GET"])
    def push_vapid_public():
        """Public VAPID key for Web Push subscription."""
        key = get_vapid_public_key()
        if not key:
            return {"error": "Web Push not available"}, 503
        return {"vapid_public_key": key}, 200

    @app.route("/api/ui/push/subscribe", methods=["POST"])
    def push_subscribe():
        """Register a Web Push subscription. Requires web_push.enabled and general.enable_notifications."""
        if not settings_check_access():
            return {"error": "Unauthorized"}, 401
        if not app_config.get("general.enable_notifications"):
            return {"error": "Notifications disabled"}, 400
        body, v_err = parse_request_json_dict(request)
        if v_err is not None:
            return v_err, 400
        try:
            endpoint, p256dh, auth = parse_push_subscription_body(body)
        except PushSubscriptionBodyError as exc:
            return {"error": str(exc)}, 400
        enable_web_push_and_save()
        ua = (request.headers.get("User-Agent") or "")[:512]
        kind = upsert_push_subscription(
            db.session,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=ua,
        )
        if kind == "updated":
            return {"message": "Subscription updated"}, 200
        return {"message": "Subscribed"}, 201

    @app.route("/api/ui/cameras", methods=["GET"])
    def list_cameras():
        """List cameras from effective camera config (slot-centric with legacy fallback)."""
        valid = get_valid_cameras(video_config=(app_config.get("video") or {}))
        return {"cameras": cameras_for_api(valid)}

    @app.route("/api/ui/status", methods=["GET"])
    def component_status():
        """Component status for UI indicators (Video/MQTT/YOLO)."""
        hit, cached = cache_get("component_status:v1")
        if hit:
            return cached
        with _status_cache_lock:
            hit2, cached2 = cache_get("component_status:v1")
            if hit2:
                return cached2
            payload = build_component_status_payload_safe(db.session)
            cache_set("component_status:v1", payload, CACHE_STATUS_SEC)
        return payload

    def _opencv_live_for_camera(camera_id: str) -> dict | None:
        row = ActivityLog.query.filter_by(type="opencv_live").order_by(ActivityLog.updated_at.desc()).first()
        if not row:
            return None
        try:
            payload = json.loads(row.data or "{}")
        except (TypeError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        by_camera = payload.get("by_camera")
        if not isinstance(by_camera, dict):
            return None
        cam = by_camera.get(camera_id)
        return cam if isinstance(cam, dict) else None

    @app.route("/api/ui/live/overlays", methods=["GET"])
    def live_overlays():
        camera_id = (request.args.get("camera_id") or "").strip()
        trigger_polygons: list = []
        detector_polygons: list = []
        source = "none"
        now_utc = datetime.now(timezone.utc)
        generated_at = now_utc.isoformat()
        detector_overlay_fresh = False
        detector_overlay_age_sec: float | None = None

        opencv_cam = _opencv_live_for_camera(camera_id) if camera_id else None
        detector_from_opencv_live = False
        if isinstance(opencv_cam, dict):
            updated_dt = _parse_overlay_updated_at(opencv_cam.get("updated_at"))
            if updated_dt is not None:
                detector_overlay_age_sec = max(
                    0.0,
                    (now_utc - updated_dt).total_seconds(),
                )
                generated_at = updated_dt.isoformat()
            raw_trigger = opencv_cam.get("trigger_polygons")
            if isinstance(raw_trigger, list):
                trigger_polygons = raw_trigger
            raw_detector = opencv_cam.get("detector_polygons")
            if isinstance(raw_detector, list):
                try:
                    ttl_cfg = float(
                        app_config.get(
                            "ui.live_detector_overlay_ttl_seconds",
                            4.0,
                        )
                        or 4.0
                    )
                except (TypeError, ValueError):
                    ttl_cfg = 4.0
                ttl_sec = max(0.5, ttl_cfg)
                is_fresh = detector_overlay_age_sec is None or detector_overlay_age_sec <= ttl_sec
                detector_polygons = raw_detector if is_fresh else []
                detector_from_opencv_live = True
                detector_overlay_fresh = is_fresh
            source = "opencv_live"

        trace_fallback_enabled = bool(app_config.get("ui.live_overlay_trace_fallback_enabled", False))
        if not detector_from_opencv_live and trace_fallback_enabled:
            rows = (
                ActivityLog.query.filter_by(type="decision_trace")
                .order_by(ActivityLog.created_at.desc())
                .limit(30)
                .all()
            )
            try:
                trace_ttl = float(app_config.get("ui.live_overlay_trace_fallback_ttl_seconds", 1.5) or 1.5)
            except (TypeError, ValueError):
                trace_ttl = 1.5
            trace_ttl = min(10.0, max(0.2, trace_ttl))
            for row in rows:
                created_at = row.created_at
                if created_at is not None:
                    created_at_utc = (
                        created_at.replace(tzinfo=timezone.utc)
                        if created_at.tzinfo is None
                        else created_at.astimezone(timezone.utc)
                    )
                    if (now_utc - created_at_utc).total_seconds() > trace_ttl:
                        continue
                try:
                    payload = json.loads(row.data or "{}")
                except (TypeError, ValueError):
                    continue
                if not isinstance(payload, dict):
                    continue
                rc = payload.get("recording_context") or {}
                if not isinstance(rc, dict):
                    rc = {}
                row_camera = str(payload.get("camera_id") or rc.get("triggered_camera") or "").strip()
                if camera_id and row_camera != camera_id:
                    continue
                trace_trigger, trace_detector = _extract_runtime_overlays_from_trace(payload)
                if trace_trigger and not trigger_polygons:
                    trigger_polygons = trace_trigger
                if trace_detector:
                    detector_polygons = trace_detector
                    source = "decision_trace"
                    break

        return {
            "camera_id": camera_id or None,
            "trigger_polygons": trigger_polygons,
            "detector_polygons": detector_polygons,
            "source": source,
            "generated_at": generated_at,
            "detector_overlay_fresh": detector_overlay_fresh,
            "detector_overlay_age_sec": detector_overlay_age_sec,
            "trace_fallback_enabled": trace_fallback_enabled,
            "opencv_last_decision_reason": (
                opencv_cam.get("last_decision_reason") if isinstance(opencv_cam, dict) else None
            ),
        }, 200

    @app.route("/api/ui/status/debug", methods=["GET"])
    def status_debug():
        """Диагностика: почему статус серый. Проверить после деплоя."""
        if not settings_check_access():
            return {"error": "Password required"}, 403
        last = ActivityLog.query.filter_by(type="heartbeat").order_by(ActivityLog.updated_at.desc()).first()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        return {
            "last_heartbeat": {
                "id": last.id if last else None,
                "updated_at": last.updated_at.isoformat() if last and last.updated_at else None,
                "data": last.data if last else None,
            }
            if last
            else None,
            "cutoff_utc": cutoff.isoformat(),
            "processor_secret_configured": bool(os.environ.get("PROCESSOR_SECRET", "").strip()),
            "api_url_base_configured": bool(os.environ.get("API_URL_BASE", "").strip()),
        }

    @app.route("/api/ui/feed/info", methods=["GET"])
    def feed_info():
        """Last dispense time, donate URL, feed source, optional scale weight. No auth required."""
        from services.feeder_scale import (
            get_feeder_scale_snapshot,
            scale_tare_available,
        )
        from app_config.scales_config import normalize_scales_source

        donate_url = (app_config.get("general.donate_url") or "").strip()
        feed_source = app_config.get("feed.source", "mqtt")
        scales_enabled = bool(app_config.get("integrations.scales.enabled"))
        scales_source = normalize_scales_source(app_config.get("integrations.scales.source"))
        scale = get_feeder_scale_snapshot()
        return {
            "last_dispense_at": get_last_dispense(),
            "donate_url": donate_url or None,
            "feed_source": feed_source,
            "scales_enabled": scales_enabled,
            "scales_source": scales_source if scales_enabled else None,
            "scale": scale,
            "scale_tare_available": scale_tare_available(),
        }, 200

    @app.route("/api/ui/feed/scale-tare", methods=["POST"])
    def feed_scale_tare():
        """Команда тары на весы. Доступ: админ или помощник; MCP Bearer — как раньше."""
        if not (contributor_or_admin_access() or mcp_bearer_authorized()):
            return {"error": "Password required"}, 403
        from services.feeder_scale import scale_tare_available, trigger_scale_tare

        if not scale_tare_available():
            return {"error": "Scale tare is not configured for the selected source"}, 400
        ok, msg = trigger_scale_tare()
        if ok:
            return {"ok": True, "message": msg}, 200
        return {"error": msg}, 500

    @app.route("/api/ui/feed/dispense", methods=["POST"])
    def feed_dispense():
        if not settings_check_access():
            return {"error": "Password required"}, 403
        success, message = dispense_feed()
        if success:
            return {"message": message}, 200
        return {"error": message}, 500

    @app.route("/api/ui/weather", methods=["GET"])
    def weather():
        weather_data = fetch_weather()
        return (
            {
                "main": weather_data.get("weather_main"),
                "description": weather_data.get("weather_description"),
                "temp": weather_data.get("weather_temp"),
                "humidity": weather_data.get("weather_humidity"),
                "pressure": weather_data.get("weather_pressure"),
                "clouds": weather_data.get("weather_clouds"),
                "wind_speed": weather_data.get("weather_wind_speed"),
                "source": app_config.get("weather.source", "openweather"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            if weather_data
            else {}
        )

    @app.route("/api/ui/sun-times", methods=["GET"])
    def sun_times():
        """Sunrise, sunset, dawn, dusk for date at configured location. date=YYYY-MM-DD."""
        date_param = request.args.get("date")
        if not date_param:
            return {"error": "date (YYYY-MM-DD) required"}, 400
        result = fetch_sun_times(date_param)
        return result if result else {}, 200
