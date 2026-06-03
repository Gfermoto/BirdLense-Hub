"""Tests for parse_yolo_status_from_heartbeat (#605)."""

from datetime import datetime, timedelta, timezone

from services.status_service import parse_yolo_status_from_heartbeat


def test_yolo_ok_when_recent_last_yolo_ok():
    ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    assert parse_yolo_status_from_heartbeat({"last_yolo_ok_at": ts}) == "ok"


def test_yolo_degraded_when_stale():
    ts = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    assert parse_yolo_status_from_heartbeat({"last_yolo_ok_at": ts}) == "degraded"


def test_yolo_error_when_blind_alert():
    hb = {
        "last_yolo_ok_at": datetime.now(timezone.utc).isoformat(),
        "runtime_stats": {"gauges": {"yolo_blind_alert": 1, "yolo_blind_status": "blind"}},
    }
    assert parse_yolo_status_from_heartbeat(hb) == "error"


def test_yolo_unknown_without_data():
    assert parse_yolo_status_from_heartbeat(None) == "unknown"
