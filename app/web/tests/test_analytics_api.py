"""Contract tests for /api/ui/analytics/* endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from models import Species, Video, VideoSpecies, db


def _auth_headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


def _seed(app):
    with app.app_context():
        sp = Species(name="Great Tit", active=True)
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        v = Video(
            processor_version="test",
            start_time=start,
            end_time=start + timedelta(seconds=40),
            video_path="/tmp/test.mp4",
        )
        db.session.add(sp)
        db.session.add(v)
        db.session.flush()
        vs = VideoSpecies(
            video_id=v.id,
            species_id=sp.id,
            start_time=1.0,
            end_time=8.0,
            confidence=0.87,
            source="video",
            detection_provider="yolo",
            track_id=7,
            frames=json.dumps(
                [
                    {"t": 1.0, "bbox": [0.1, 0.2, 0.2, 0.3]},
                    {"t": 1.2, "bbox": [0.2, 0.22, 0.3, 0.35]},
                ]
            ),
        )
        db.session.add(vs)
        db.session.commit()


def test_analytics_trajectories_contract(client, app):
    _seed(app)
    r = client.get("/api/ui/analytics/trajectories", headers=_auth_headers())
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert "items" in body
    assert body["count"] >= 1
    item = body["items"][0]
    assert "video_species_id" in item
    assert "points" in item
    assert len(item["points"]) >= 1


def test_analytics_heatmap_contract(client, app):
    _seed(app)
    r = client.get("/api/ui/analytics/heatmap?grid=8", headers=_auth_headers())
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["grid_size"] == 8
    assert isinstance(body["cells"], list)
    assert len(body["cells"]) == 8


def test_analytics_timeseries_contract(client, app):
    _seed(app)
    r = client.get(
        "/api/ui/analytics/visits-timeseries?bucket=hour",
        headers=_auth_headers(),
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["bucket"] == "hour"
    assert "items" in body


def test_analytics_quality_health_contract(client, app):
    _seed(app)
    r = client.get(
        "/api/ui/analytics/quality-health?hours=24",
        headers=_auth_headers(),
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert "health_kpis" in body
    assert "trigger_to_first_bbox_latency_p95_s" in body["health_kpis"]
    assert "finalize_duration_p95_ms" in body["health_kpis"]
    assert "ingest_bbox_contract_pruned_events" in body["health_kpis"]
    assert "ingest_bbox_contract_empty_events" in body["health_kpis"]
    assert "ingest_bbox_contract_pruned_rows_per_hour" in body["health_kpis"]
    assert (
        "ingest_bbox_contract_pruned_rows_per_hour_7d_baseline"
        in body["health_kpis"]
    )
    assert (
        "ingest_bbox_contract_pruned_rows_per_hour_delta_vs_7d"
        in body["health_kpis"]
    )
    assert "frigate_catches_missed_birds_sessions" in body["health_kpis"]
    assert "frigate_catches_missed_birds_rate" in body["health_kpis"]
    assert (
        "frigate_catches_missed_birds_by_trigger_source"
        in body["health_kpis"]
    )
    assert (
        "frigate_catches_missed_birds_by_trigger_source_rate"
        in body["health_kpis"]
    )
    assert (
        "frigate_catches_missed_birds_rate_7d_baseline"
        in body["health_kpis"]
    )
    assert (
        "frigate_catches_missed_birds_rate_delta_vs_7d"
        in body["health_kpis"]
    )
    assert "recent_events" in body
