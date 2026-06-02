"""Timeline limit/offset contract (#514)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from routes.ui_timeline_helpers import (
    _timeline_item_matches_trigger,
    build_merged_timeline_items,
)
from timeline_payloads import _infer_trigger_source_from_detections


def test_timeline_pagination_envelope(app):
    with app.app_context():
        from models import db

        start = datetime(2099, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(hours=23)
        out = build_merged_timeline_items(db.session, start, end, limit=10, offset=0)
        assert isinstance(out, dict)
        assert "items" in out
        assert "total" in out
        assert out["limit"] == 10
        assert out["offset"] == 0
        assert "has_more" in out


def test_timeline_trigger_filter_matcher():
    item_opencv = {"trigger_source": "opencv"}
    item_frigate = {"trigger_source": "frigate"}
    item_empty = {}

    assert _timeline_item_matches_trigger(item_opencv, "all") is True
    assert _timeline_item_matches_trigger(item_opencv, "opencv") is True
    assert _timeline_item_matches_trigger(item_opencv, "frigate") is False
    assert _timeline_item_matches_trigger(item_frigate, "frigate") is True
    assert _timeline_item_matches_trigger(item_empty, "unknown") is True


def test_infer_trigger_source_prefers_explicit_video_trigger():
    detections = [{"detection_provider": "yolo", "source": "video"}]
    assert _infer_trigger_source_from_detections(detections, preferred_trigger="frigate") == "frigate"


def test_infer_trigger_source_does_not_map_yolo_to_opencv():
    detections = [{"detection_provider": "yolo", "source": "video"}]
    assert _infer_trigger_source_from_detections(detections) == "opencv"
