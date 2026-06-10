"""Tests for readiness_service helpers (#605 / re-review)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models import ActivityLog, db
from services.readiness_service import (
    _build_yolo_detector_check,
    _processor_bootstrap_phase,
    _processor_heartbeat_readiness,
)


def test_yolo_detector_idle_inference_ready_without_motion(app):
    hb = {
        "yolo_inference_ready": True,
        "yolo_inference_ready_at": datetime.now(timezone.utc).isoformat(),
    }
    check = _build_yolo_detector_check(hb, "unknown")
    assert check["status"] == "ok"
    assert "last_motion_age_sec" not in check
    assert "between_session_blind" not in check


def test_yolo_detector_inference_backend_effective_from_heartbeat(app):
    hb = {
        "yolo_inference_ready": True,
        "inference_backend_requested": "auto",
        "inference_backend_effective": "torch",
        "inference_auto_torch_fallback": True,
    }
    check = _build_yolo_detector_check(hb, "ok")
    assert check["inference_backend_effective"] == "torch"
    assert check["inference_backend_requested"] == "auto"
    assert check["status"] == "degraded"
    assert check["inference_auto_torch_fallback"] is True


def test_yolo_detector_between_session_blind_with_recent_motion(app):
    hb = {
        "yolo_inference_ready": True,
        "last_motion_age_sec": 12.0,
        "runtime_stats": {
            "gauges": {
                "yolo_blind_alert": 1,
                "yolo_blind_status": "blind",
            }
        },
    }
    check = _build_yolo_detector_check(hb, "ok")
    assert check["status"] == "error"
    assert check["last_motion_age_sec"] == 12.0
    assert check["between_session_blind"] is True


def test_processor_bootstrap_phase_only_before_inference_ready(app):
    assert _processor_bootstrap_phase({"status": "bootstrap"}, age_seconds=30.0) is True
    assert (
        _processor_bootstrap_phase(
            {"status": "up", "yolo_inference_ready": True},
            age_seconds=30.0,
        )
        is False
    )
    assert (
        _processor_bootstrap_phase(
            {"status": "config_error", "bootstrap_error": "bad cfg"},
            age_seconds=30.0,
        )
        is False
    )


def test_processor_heartbeat_marks_bootstrap_phase(app, monkeypatch):
    import services.readiness_service as rs

    monkeypatch.setattr(rs, "_is_test_runtime", lambda: False)
    monkeypatch.setenv("BIRDLENSE_ENV", "production")

    with app.app_context():
        row = ActivityLog(
            type="heartbeat",
            data='{"status":"bootstrap"}',
            updated_at=datetime.now(timezone.utc),
        )
        db.session.add(row)
        db.session.commit()
        check = _processor_heartbeat_readiness(db.session)

    assert check["status"] == "ok"
    assert check["bootstrap_phase"] is True
