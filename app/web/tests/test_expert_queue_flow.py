"""Expert queue: confirm must remove semantic_review_required items from queue=expert."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models import ActiveLearningCase, BirdProfile, Species, Video, VideoSpecies, db
from services.review_queue_service import fetch_review_queue_items


def _seed_semantic_case(app):
    with app.app_context():
        species = Species(name="Expert Queue Finch")
        db.session.add(species)
        db.session.flush()
        now = datetime.now(timezone.utc)
        video = Video(
            processor_version="test",
            video_path="/tmp/expert-queue.mp4",
            start_time=now - timedelta(minutes=5),
            end_time=now,
        )
        db.session.add(video)
        db.session.flush()
        profile = BirdProfile(display_name="Testy", species_id=species.id)
        db.session.add(profile)
        db.session.flush()
        vs = VideoSpecies(
            video_id=video.id,
            species_id=species.id,
            start_time=0.0,
            end_time=2.0,
            confidence=0.42,
            source="video",
            detection_provider="yolo",
            track_id=7,
            bird_profile_id=profile.id,
            classifier_needs_review=True,
            review_reason="semantic_review_required",
        )
        db.session.add(vs)
        db.session.flush()
        case = ActiveLearningCase(
            video_id=video.id,
            video_species_id=vs.id,
            reason_code="semantic_review_required",
            confidence=vs.confidence,
            status="semantic_review_required",
        )
        db.session.add(case)
        db.session.commit()
        end_ts = int(now.timestamp())
        start_ts = end_ts - 7200
        return {
            "detection_id": int(vs.id),
            "case_id": int(case.id),
            "start": str(start_ts),
            "end": str(end_ts),
        }


def test_expert_queue_confirm_removes_item(client, app):
    ctx = _seed_semantic_case(app)
    before = client.get(f"/api/ui/unknowns?queue=expert&start_time={ctx['start']}&end_time={ctx['end']}&limit=50")
    assert before.status_code == 200, before.get_data(as_text=True)
    ids_before = {int(row["id"]) for row in before.get_json()}
    assert ctx["detection_id"] in ids_before

    confirm = client.post(
        f"/api/ui/detections/{ctx['detection_id']}/confirm",
        json={"source": "unknowns"},
    )
    assert confirm.status_code == 200, confirm.get_data(as_text=True)

    after = client.get(f"/api/ui/unknowns?queue=expert&start_time={ctx['start']}&end_time={ctx['end']}&limit=50")
    assert after.status_code == 200, after.get_data(as_text=True)
    ids_after = {int(row["id"]) for row in after.get_json()}
    assert ctx["detection_id"] not in ids_after

    with app.app_context():
        vs = db.session.get(VideoSpecies, ctx["detection_id"])
        case = db.session.get(ActiveLearningCase, ctx["case_id"])
        assert vs is not None
        assert vs.classifier_needs_review is False
        assert vs.review_reason is None
        assert case is not None
        assert case.status == "approved"
        rows = fetch_review_queue_items(
            db.session,
            start_time=ctx["start"],
            end_time=ctx["end"],
            queue="expert",
            limit=50,
        )
        assert ctx["detection_id"] not in {int(r["id"]) for r in rows}
