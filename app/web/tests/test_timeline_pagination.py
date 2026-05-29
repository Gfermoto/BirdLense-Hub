"""Timeline limit/offset contract (#514)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from routes.ui_timeline_helpers import (
    _timeline_item_matches_source,
    build_merged_timeline_items,
)


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


def test_timeline_source_filter_matcher():
    item_video = {"detections": [{"source": "video"}, {"source": "video"}]}
    item_audio = {"detections": [{"source": "audio"}]}
    item_mixed = {"detections": [{"source": "video"}, {"source": "audio"}]}

    assert _timeline_item_matches_source(item_video, "all") is True
    assert _timeline_item_matches_source(item_video, "video_only") is True
    assert _timeline_item_matches_source(item_video, "audio_only") is False
    assert _timeline_item_matches_source(item_video, "mixed") is False

    assert _timeline_item_matches_source(item_audio, "audio_only") is True
    assert _timeline_item_matches_source(item_audio, "video_only") is False

    assert _timeline_item_matches_source(item_mixed, "mixed") is True
    assert _timeline_item_matches_source(item_mixed, "video_only") is False
