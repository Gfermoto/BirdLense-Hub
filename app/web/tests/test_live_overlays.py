import json
from datetime import datetime, timedelta, timezone

from models import ActivityLog, db


from app_config.app_config import app_config


def _mk_trace(camera_id: str = "BirdBox") -> dict:
    return {
        "camera_id": camera_id,
        "recording_context": {"triggered_camera": camera_id},
        "persisted_tracks": [
            {
                "frames": [
                    {
                        "bbox": [0.1, 0.2, 0.4, 0.5],
                    }
                ]
            }
        ],
    }


def test_live_overlays_default_disables_decision_trace_fallback(app, client):
    with app.app_context():
        db.session.add(ActivityLog(type="decision_trace", data=json.dumps(_mk_trace())))
        db.session.commit()

    prev = app_config.get("ui.live_overlay_trace_fallback_enabled")
    app_config.set("ui.live_overlay_trace_fallback_enabled", False)
    try:
        res = client.get("/api/ui/live/overlays", query_string={"camera_id": "BirdBox"})
        assert res.status_code == 200
        body = res.get_json()
        assert body["trace_fallback_enabled"] is False
        assert body["detector_polygons"] == []
        assert body["source"] == "none"
    finally:
        app_config.set("ui.live_overlay_trace_fallback_enabled", prev)


def test_live_overlays_can_use_decision_trace_fallback_when_enabled(app, client):
    with app.app_context():
        db.session.add(ActivityLog(type="decision_trace", data=json.dumps(_mk_trace())))
        db.session.commit()

    prev_enabled = app_config.get("ui.live_overlay_trace_fallback_enabled")
    prev_ttl = app_config.get("ui.live_overlay_trace_fallback_ttl_seconds")
    app_config.set("ui.live_overlay_trace_fallback_enabled", True)
    app_config.set("ui.live_overlay_trace_fallback_ttl_seconds", 30.0)
    try:
        res = client.get("/api/ui/live/overlays", query_string={"camera_id": "BirdBox"})
        assert res.status_code == 200
        body = res.get_json()
        assert body["trace_fallback_enabled"] is True
        assert len(body["detector_polygons"]) == 1
        assert body["source"] == "decision_trace"
    finally:
        app_config.set("ui.live_overlay_trace_fallback_enabled", prev_enabled)
        app_config.set("ui.live_overlay_trace_fallback_ttl_seconds", prev_ttl)


def test_live_overlays_drop_stale_opencv_detector_polygons(app, client):
    stale = datetime.now(timezone.utc) - timedelta(seconds=30)
    payload = {
        "by_camera": {
            "BirdBox": {
                "trigger_polygons": [],
                "detector_polygons": [
                    [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
                ],
                "updated_at": stale.timestamp(),
            }
        }
    }
    with app.app_context():
        db.session.add(ActivityLog(type="opencv_live", data=json.dumps(payload)))
        db.session.commit()

    prev_ttl = app_config.get("ui.live_detector_overlay_ttl_seconds")
    app_config.set("ui.live_detector_overlay_ttl_seconds", 4.0)
    try:
        res = client.get("/api/ui/live/overlays", query_string={"camera_id": "BirdBox"})
        assert res.status_code == 200
        body = res.get_json()
        assert body["source"] == "opencv_live"
        assert body["detector_overlay_fresh"] is False
        assert body["detector_polygons"] == []
        assert float(body["detector_overlay_age_sec"]) >= 4.0
    finally:
        app_config.set("ui.live_detector_overlay_ttl_seconds", prev_ttl)
