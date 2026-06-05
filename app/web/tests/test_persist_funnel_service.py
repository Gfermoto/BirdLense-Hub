"""Tests for persist_funnel_service (#605)."""

from datetime import datetime, timezone
import json

from models import SessionRuntimeMetrics, db


def _add_metric(**kwargs):
    row = SessionRuntimeMetrics(
        camera_id=kwargs.get("camera_id", "cam1"),
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
        yolo_raw_boxes_total=kwargs.get("yolo_raw_boxes_total", 5),
        yolo_accepted_boxes_total=kwargs.get("yolo_accepted_boxes_total", 4),
        yolo_frames_with_tracks=kwargs.get("yolo_frames_with_tracks", 3),
        post_fusion_persisted=kwargs.get("post_fusion_persisted", 0),
        payload_json=kwargs.get("payload_json"),
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_persist_funnel_classifies_fusion_drop(app):
    with app.app_context():
        _add_metric(
            post_fusion_persisted=0,
            payload_json=json.dumps({"post_fusion_persisted": 0}),
        )
        from services.persist_funnel_service import build_persist_funnel_summary

        summary = build_persist_funnel_summary(db.session)
        assert summary["sessions_total"] == 1
        assert "decision_fusion_drop_tracks_gt_0_persisted_0" in summary["global_funnel"]
        assert summary["fusion_drop_sessions"] == 1


def test_persist_funnel_healthy_session(app):
    with app.app_context():
        _add_metric(post_fusion_persisted=2)
        from services.persist_funnel_service import build_persist_funnel_summary

        summary = build_persist_funnel_summary(db.session)
        assert summary["healthy_persist_count"] == 1
        assert summary["status"] == "ok"


def test_pipeline_funnel_api(client):
    res = client.get(
        "/api/ui/system/pipeline-funnel",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    assert payload.get("schema") == "persist_funnel_summary@v1"
    assert "by_camera" in payload


def test_readiness_includes_pipeline_funnel(client):
    res = client.get("/api/ui/readiness")
    assert res.status_code in (200, 503)
    payload = res.get_json() or {}
    assert "pipeline_funnel" in payload
    checks = payload.get("checks") or {}
    assert "pipeline_funnel" in checks
    assert "yolo_detector" in checks


def test_readiness_keeps_quality_degraded_separate_from_service_ready(client, monkeypatch):
    import services.readiness_service as rs

    monkeypatch.setenv("BIRDLENSE_ENV", "production")
    monkeypatch.setattr(
        rs,
        "_processor_heartbeat_readiness",
        lambda _session: {"status": "ok", "reason": "ok", "max_age_seconds": 180},
    )
    monkeypatch.setattr(
        rs,
        "build_persist_funnel_summary",
        lambda _session: {
            "status": "degraded",
            "sessions_total": 10,
            "healthy_persist_rate": 0.1,
            "fusion_drop_rate": 0.9,
            "fp_empty_opencv_rate": 0.0,
            "alerts": ["fusion_drop"],
            "top_root_causes": ["decision_fusion_drop_tracks_gt_0_persisted_0"],
        },
    )
    monkeypatch.setattr(
        rs,
        "build_component_status_payload_safe",
        lambda _session: {
            "web": "ok",
            "processor": "ok",
            "video": "ok",
            "mqtt": "ok",
            "esphome": "ok",
            "yolo": "unknown",
        },
    )
    monkeypatch.setattr(rs, "cache_get", lambda _key: (False, None))
    monkeypatch.setattr(rs, "cache_set", lambda *_args, **_kwargs: None)

    res = client.get("/api/ui/readiness")
    payload = res.get_json() or {}

    assert res.status_code == 200
    assert payload["ready"] is True
    assert payload["quality_ready"] is False
    assert payload["checks"]["pipeline_funnel"]["status"] == "degraded"
    assert payload["checks"]["yolo_detector"]["status"] == "unknown"
