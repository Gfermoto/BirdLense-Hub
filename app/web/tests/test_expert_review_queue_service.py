"""SOTA-13: expert review queue integration."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app_config.app_config import app_config
from models import ExpertReviewQueue, Species, Video, VideoSpecies, db
from services.expert_review_queue_service import list_expert_queue, resolve_expert_task


@pytest.fixture
def _enable_reid_flags():
    app_config.set("processor.reid_gallery_enabled", True)
    app_config.set("processor.reid_track_clustering_enabled", True)
    app_config.set("processor.reid_expert_queue_enabled", True)
    yield
    app_config.set("processor.reid_gallery_enabled", False)
    app_config.set("processor.reid_track_clustering_enabled", False)
    app_config.set("processor.reid_expert_queue_enabled", False)


def test_list_disabled_by_default(app):
    payload = list_expert_queue(sync=False)
    assert payload.get("enabled") is False


def test_resolve_confirm_species(app, _enable_reid_flags):
    with app.app_context():
        sp = Species(name="Test Sparrow")
        db.session.add(sp)
        db.session.flush()
        now = datetime.now(timezone.utc)
        vid = Video(
            video_path="test.mp4",
            start_time=now,
            end_time=now,
            processor_version="test",
        )
        db.session.add(vid)
        db.session.flush()
        vs = VideoSpecies(
            video_id=vid.id,
            species_id=sp.id,
            start_time=0.0,
            end_time=1.0,
            confidence=0.4,
            source="video",
            classifier_needs_review=True,
        )
        db.session.add(vs)
        db.session.flush()
        task = ExpertReviewQueue(
            task_type="low_confidence",
            status="pending",
            video_species_id=vs.id,
            species_id=sp.id,
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        vs_id = vs.id

        out = resolve_expert_task(task_id=task_id, action="confirm_species", species_id=sp.id)
        assert out["action"] == "confirm_species"
        vs2 = db.session.get(VideoSpecies, vs_id)
        assert vs2 is not None
        assert vs2.manually_corrected is True
        assert vs2.classifier_needs_review is False
