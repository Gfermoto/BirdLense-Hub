"""Domain health snapshot strict-quality metrics."""

from datetime import datetime, timedelta, timezone

from models import Species, Video, VideoSpecies, db


def _auth_headers() -> dict[str, str]:
    # tests run with settings access allowed by default config
    return {"Content-Type": "application/json"}


def test_domain_health_includes_strict_quality_block(client):
    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    assert "strict_quality" in payload
    strict = payload["strict_quality"]
    assert "strict_quality_ready" in strict
    assert "duplicate_video_groups_ok" in strict
    assert "duplicate_detection_groups_ok" in strict
    assert "duplicate_video_groups" in (payload.get("metrics") or {})
    assert "duplicate_detection_groups" in (payload.get("metrics") or {})
    samples = payload.get("samples") or {}
    assert "binary_backend_counts_24h" in samples
    assert "inference_device_counts_24h" in samples


def test_domain_health_flags_duplicate_detection_groups(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        species = Species(name="DomainHealth Duplicate Finch")
        db.session.add(species)
        db.session.flush()
        video = Video(
            processor_version="pytest",
            start_time=now,
            end_time=now + timedelta(seconds=5),
            video_path="data/recordings/2026/05/03/150000/video.mp4",
            idempotency_key="pytest-domain-health-key",
        )
        db.session.add(video)
        db.session.flush()
        base = {
            "video_id": video.id,
            "species_id": species.id,
            "species_visit_id": None,
            "start_time": 0.0,
            "end_time": 2.0,
            "confidence": 0.91,
            "source": "video",
            "detection_provider": "yolo",
            "track_id": 7,
        }
        db.session.add(VideoSpecies(**base))
        db.session.add(VideoSpecies(**base))
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    metrics = payload.get("metrics") or {}
    strict = payload.get("strict_quality") or {}
    assert int(metrics.get("duplicate_detection_groups") or 0) >= 1
    assert strict.get("duplicate_detection_groups_ok") is False
    assert strict.get("strict_quality_ready") is False
