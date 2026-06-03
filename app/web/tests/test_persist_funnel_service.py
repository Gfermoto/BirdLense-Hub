"""Tests for persist_funnel_service (#605)."""

from datetime import datetime, timedelta, timezone
import json

from models import SessionRuntimeMetrics, db


def _add_metric(**kwargs):
    row = SessionRuntimeMetrics(
        camera_id=kwargs.get("camera_id", "cam1"),
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
