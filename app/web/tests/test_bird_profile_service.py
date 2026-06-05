"""Bird profile linking should not fan out across unrelated tracks."""

from __future__ import annotations

from datetime import datetime, timezone

from models import BirdProfile, Species, Video, VideoSpecies, db
from services.bird_profile_service import assign_profile_to_detection, clear_profile_from_detection


def test_assign_profile_updates_only_selected_detection(app):
    with app.app_context():
        species = Species(name="Profile Service Finch")
        db.session.add(species)
        db.session.flush()
        video = Video(
            processor_version="test",
            video_path="/tmp/profile-service.mp4",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        )
        db.session.add(video)
        db.session.flush()
        first = VideoSpecies(
            video_id=video.id,
            species_id=species.id,
            start_time=0.0,
            end_time=1.0,
            confidence=0.8,
            source="video",
            track_id=1,
        )
        second = VideoSpecies(
            video_id=video.id,
            species_id=species.id,
            start_time=2.0,
            end_time=3.0,
            confidence=0.7,
            source="video",
            track_id=2,
        )
        profile = BirdProfile(display_name="Finch A", species_id=species.id)
        db.session.add_all([first, second, profile])
        db.session.commit()

        payload = assign_profile_to_detection(detection_id=first.id, bird_profile_id=profile.id)
        db.session.refresh(first)
        db.session.refresh(second)

        assert payload["updated_count"] == 1
        assert first.bird_profile_id == profile.id
        assert first.individual_nickname == "Finch A"
        assert second.bird_profile_id is None
        assert second.individual_nickname is None

        clear_payload = clear_profile_from_detection(detection_id=first.id)
        db.session.refresh(first)
        db.session.refresh(second)

        assert clear_payload["updated_count"] == 1
        assert first.bird_profile_id is None
        assert first.individual_nickname is None
        assert second.bird_profile_id is None
