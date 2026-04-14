"""Regression tests for stabilization work across system maintenance and overview."""

from datetime import datetime, timezone

import data_paths as data_paths_mod
import services.broken_videos_inventory_service as broken_videos_inventory_mod
from services.http_response_cache import bust_response_caches


class TestSystemMaintenanceEndpoints:
    def test_clean_orphaned_visits_preview_and_apply(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            sp_visit = Species(name="Preview Visit Species")
            sp_detection = Species(name="Preview Detection Species")
            db.session.add_all([sp_visit, sp_detection])
            db.session.flush()

            orphan = SpeciesVisit(
                species_id=sp_visit.id,
                start_time=datetime(2026, 3, 24, 10, 0, 0),
                end_time=datetime(2026, 3, 24, 10, 5, 0),
                max_simultaneous=1,
            )
            linked = SpeciesVisit(
                species_id=sp_visit.id,
                start_time=datetime(2026, 3, 24, 11, 0, 0),
                end_time=datetime(2026, 3, 24, 11, 5, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 24, 11, 0, 0),
                end_time=datetime(2026, 3, 24, 11, 1, 0),
                video_path="data/recordings/2026/03/24/110000/video.mp4",
            )
            db.session.add_all([orphan, linked, video])
            db.session.flush()

            detection = VideoSpecies(
                video_id=video.id,
                species_id=sp_detection.id,
                species_visit_id=linked.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.95,
                source="video",
            )
            db.session.add(detection)
            db.session.commit()

            sp_detection_id = sp_detection.id
            orphan_id = orphan.id
            linked_id = linked.id
            detection_id = detection.id

        preview = client.post("/api/ui/system/clean-orphaned-visits", json={"dry_run": True})
        assert preview.status_code == 200
        assert preview.json["dry_run"] is True
        assert preview.json["orphaned"] == 1
        assert preview.json["synced_would_update"] == 1

        with app.app_context():
            assert db.session.get(SpeciesVisit, orphan_id) is not None
            persisted = db.session.get(VideoSpecies, detection_id)
            assert persisted is not None
            assert persisted.species_visit_id == linked_id
            assert persisted.species_id == sp_detection_id

        apply = client.post("/api/ui/system/clean-orphaned-visits", json={"dry_run": False})
        assert apply.status_code == 200
        assert apply.json["dry_run"] is False
        assert apply.json["orphaned"] == 1
        assert apply.json["synced"] == 1

        with app.app_context():
            assert db.session.get(SpeciesVisit, orphan_id) is None
            persisted = db.session.get(VideoSpecies, detection_id)
            linked = db.session.get(SpeciesVisit, linked_id)
            assert persisted is not None
            assert linked is not None
            assert persisted.species_id == linked.species_id

    def test_realign_visit_times_preview_and_apply(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            species = Species(name="Realign Species")
            db.session.add(species)
            db.session.flush()

            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 24, 9, 0, 0),
                end_time=datetime(2026, 3, 24, 9, 30, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 24, 9, 10, 0),
                end_time=datetime(2026, 3, 24, 9, 12, 0),
                video_path="data/recordings/2026/03/24/091000/video.mp4",
            )
            db.session.add_all([visit, video])
            db.session.flush()

            detection = VideoSpecies(
                video_id=video.id,
                species_id=species.id,
                species_visit_id=visit.id,
                start_time=15.0,
                end_time=45.0,
                confidence=0.97,
                source="video",
            )
            db.session.add(detection)
            db.session.commit()
            visit_id = visit.id

        preview = client.post("/api/ui/system/realign-visit-times", json={"dry_run": True})
        assert preview.status_code == 200
        assert preview.json["dry_run"] is True
        assert preview.json["updated"] == 1

        with app.app_context():
            visit = db.session.get(SpeciesVisit, visit_id)
            assert visit.start_time == datetime(2026, 3, 24, 9, 0, 0)
            assert visit.end_time == datetime(2026, 3, 24, 9, 30, 0)

        apply = client.post("/api/ui/system/realign-visit-times", json={"dry_run": False})
        assert apply.status_code == 200
        assert apply.json["dry_run"] is False
        assert apply.json["updated"] == 1

        with app.app_context():
            visit = db.session.get(SpeciesVisit, visit_id)
            assert visit.start_time == datetime(2026, 3, 24, 9, 10, 15)
            assert visit.end_time == datetime(2026, 3, 24, 9, 10, 45)

    def test_split_large_gap_visits_preview_and_apply(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            species = Species(name="Gap Split Species")
            db.session.add(species)
            db.session.flush()

            broken_visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 25, 7, 13, 0),
                end_time=datetime(2026, 4, 1, 8, 47, 26),
                max_simultaneous=1,
            )
            early_video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 25, 7, 13, 0),
                end_time=datetime(2026, 3, 25, 7, 13, 30),
                video_path="data/recordings/2026/03/25/071300/video.mp4",
            )
            late_video = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 1, 8, 47, 0),
                end_time=datetime(2026, 4, 1, 8, 47, 30),
                video_path="data/recordings/2026/04/01/084700/video.mp4",
            )
            db.session.add_all([broken_visit, early_video, late_video])
            db.session.flush()

            early_detection = VideoSpecies(
                video_id=early_video.id,
                species_id=species.id,
                species_visit_id=broken_visit.id,
                start_time=0.0,
                end_time=12.6,
                confidence=0.97,
                source="video",
            )
            late_detection = VideoSpecies(
                video_id=late_video.id,
                species_id=species.id,
                species_visit_id=broken_visit.id,
                start_time=14.0,
                end_time=26.3,
                confidence=0.98,
                source="video",
            )
            db.session.add_all([late_detection, early_detection])
            db.session.commit()
            species_id = species.id
            broken_visit_id = broken_visit.id
            late_detection_id = late_detection.id

        preview = client.post("/api/ui/system/split-large-gap-visits", json={"dry_run": True})
        assert preview.status_code == 200
        assert preview.json["dry_run"] is True
        assert preview.json["affected_visits"] == 1
        assert preview.json["created_visits"] == 1
        assert preview.json["reassigned_detections"] == 1

        with app.app_context():
            assert SpeciesVisit.query.count() == 1

        apply = client.post("/api/ui/system/split-large-gap-visits", json={"dry_run": False})
        assert apply.status_code == 200
        assert apply.json["dry_run"] is False
        assert apply.json["affected_visits"] == 1
        assert apply.json["created_visits"] == 1
        assert apply.json["reassigned_detections"] == 1

        with app.app_context():
            visits = SpeciesVisit.query.filter_by(species_id=species_id).order_by(SpeciesVisit.start_time.asc()).all()
            assert len(visits) == 2
            assert visits[0].id == broken_visit_id
            assert visits[0].start_time == datetime(2026, 3, 25, 7, 13, 0)
            assert visits[0].end_time == datetime(2026, 3, 25, 7, 13, 12, 600000)
            assert visits[1].start_time == datetime(2026, 4, 1, 8, 47, 14)
            assert visits[1].end_time == datetime(2026, 4, 1, 8, 47, 26, 300000)

            late_detection = db.session.get(VideoSpecies, late_detection_id)
            assert late_detection is not None
            assert late_detection.species_visit_id == visits[1].id


class TestOverviewDayOverlap:
    def test_overview_counts_visit_that_crosses_midnight(self, app, client):
        from app_config.app_config import app_config
        from observer_time import _observer_timezone_name_cached
        from models import Species, SpeciesVisit, db

        app_config.set("secrets.latitude", "55.7558")
        app_config.set("secrets.longitude", "37.6176")
        _observer_timezone_name_cached.cache_clear()

        with app.app_context():
            species = Species(name="Midnight Species")
            db.session.add(species)
            db.session.flush()
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 24, 23, 50, 0),
                end_time=datetime(2026, 3, 25, 0, 10, 0),
                max_simultaneous=2,
            )
            db.session.add(visit)
            db.session.commit()

        bust_response_caches()

        start = int(datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        end = int(datetime(2026, 3, 25, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        response = client.get("/api/ui/overview", query_string={"start_time": start, "end_time": end})

        assert response.status_code == 200
        body = response.get_json()
        assert body["stats"]["uniqueSpecies"] == 1
        assert body["stats"]["totalDetections"] == 1
        assert body["stats"]["busiestHour"] == 3
        assert body["topSpecies"][0]["detections"][3] == 1
        assert body["lastDetection"]["species_name"] == "Midnight Species"

    def test_overview_date_uses_observer_local_day_and_local_hour(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, db

        with app.app_context():
            app_config.set("secrets.latitude", "55.7558")
            app_config.set("secrets.longitude", "37.6176")
            species = Species(name="Local Time Species")
            db.session.add(species)
            db.session.flush()
            db.session.add(
                SpeciesVisit(
                    species_id=species.id,
                    start_time=datetime(2026, 3, 24, 21, 30, 0),
                    end_time=datetime(2026, 3, 24, 21, 40, 0),
                    max_simultaneous=3,
                ),
            )
            db.session.commit()

        bust_response_caches()

        response = client.get("/api/ui/overview", query_string={"date": "2026-03-25"})

        assert response.status_code == 200
        body = response.get_json()
        assert body["stats"]["uniqueSpecies"] == 1
        assert body["stats"]["busiestHour"] == 0
        assert body["topSpecies"][0]["detections"][0] == 1

    def test_overview_date_counts_overlapping_video_duration_and_local_temperature(
        self,
        app,
        client,
    ):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set("secrets.latitude", "55.7558")
            app_config.set("secrets.longitude", "37.6176")
            species = Species(name="Overlap Video Species")
            db.session.add(species)
            db.session.flush()
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 24, 21, 2, 0),
                end_time=datetime(2026, 3, 24, 21, 4, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 24, 20, 55, 0),
                end_time=datetime(2026, 3, 24, 21, 5, 0),
                video_path="data/recordings/2026/03/24/205500/video.mp4",
                weather_temp=5.5,
            )
            db.session.add_all([visit, video])
            db.session.flush()
            db.session.add(
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=visit.id,
                    start_time=0.0,
                    end_time=5.0,
                    confidence=0.9,
                    source="video",
                    detection_provider="yolo",
                ),
            )
            db.session.commit()

        bust_response_caches()

        response = client.get("/api/ui/overview", query_string={"date": "2026-03-25"})

        assert response.status_code == 200
        body = response.get_json()
        assert body["stats"]["videoDuration"] == 600
        assert body["hourlyTemperature"][0] == 5.5

    def test_overview_detection_by_provider_counts_distinct_visits(
        self,
        app,
        client,
    ):
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            species = Species(name="Provider Count Species")
            db.session.add(species)
            db.session.flush()
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 25, 8, 0, 0),
                end_time=datetime(2026, 3, 25, 8, 10, 0),
                max_simultaneous=5,
            )
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 25, 8, 0, 0),
                end_time=datetime(2026, 3, 25, 8, 0, 30),
                video_path="data/recordings/2026/03/25/080000/video.mp4",
            )
            db.session.add_all([visit, video])
            db.session.flush()
            db.session.add_all(
                [
                    VideoSpecies(
                        video_id=video.id,
                        species_id=species.id,
                        species_visit_id=visit.id,
                        start_time=0.0,
                        end_time=3.0,
                        confidence=0.9,
                        source="video",
                        detection_provider="yolo",
                    ),
                    VideoSpecies(
                        video_id=video.id,
                        species_id=species.id,
                        species_visit_id=visit.id,
                        start_time=4.0,
                        end_time=6.0,
                        confidence=0.88,
                        source="video",
                        detection_provider="yolo",
                    ),
                    VideoSpecies(
                        video_id=video.id,
                        species_id=species.id,
                        species_visit_id=visit.id,
                        start_time=7.0,
                        end_time=9.0,
                        confidence=0.82,
                        source="video",
                        detection_provider="frigate",
                    ),
                ]
            )
            db.session.commit()

        bust_response_caches()

        start = int(datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        end = int(datetime(2026, 3, 25, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        response = client.get("/api/ui/overview", query_string={"start_time": start, "end_time": end})

        assert response.status_code == 200
        body = response.get_json()
        assert body["stats"]["detectionByProvider"]["yolo"] == 1
        assert body["stats"]["detectionByProvider"]["frigate"] == 1


class TestObserverLocalRanges:
    def test_observer_local_night_covers_early_morning_of_selected_date(self, app):
        from app_config.app_config import app_config
        from util import observer_local_range

        with app.app_context():
            app_config.set("secrets.latitude", "55.7558")
            app_config.set("secrets.longitude", "37.6176")
            start_dt, end_dt = observer_local_range("2026-03-25", time_of_day="night")

        assert start_dt == datetime(2026, 3, 24, 21, 0, 0)
        assert end_dt == datetime(2026, 3, 25, 2, 59, 59, 999999)


class TestReviewQueueBulkDelete:
    def test_unknowns_expose_explicit_review_state(self, app, client):
        from app_config.app_config import app_config
        from models import Species, Video, VideoSpecies, db

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            try:
                generic = Species(name="Bird")
                other = Species(name="Review Queue Other")
                db.session.add_all([generic, other])
                db.session.flush()

                video = Video(
                    processor_version="test",
                    start_time=datetime(2026, 3, 24, 12, 0, 0),
                    end_time=datetime(2026, 3, 24, 12, 0, 30),
                    video_path="data/recordings/2026/03/24/120000/video.mp4",
                )
                db.session.add(video)
                db.session.flush()
                db.session.add(
                    VideoSpecies(
                        video_id=video.id,
                        species_id=generic.id,
                        start_time=0.0,
                        end_time=2.0,
                        confidence=0.11,
                        source="video",
                        detection_provider="yolo",
                    ),
                )
                db.session.commit()
            finally:
                app_config.set("general.settings_password", old_admin or "")
                app_config.set("general.contributor_password", old_contrib or "")

        response = client.get(
            "/api/ui/unknowns",
            query_string={"date": "2026-03-24", "time_of_day": "all", "limit": 10},
        )
        assert response.status_code == 200
        assert response.json
        row = response.json[0]
        assert row["review_state"] == "pending"
        assert row["review_reason"] == "generic_bird"
        assert row["review_source"] == "unknowns"

    def test_review_queue_bulk_delete_preview_and_apply(self, app, client, tmp_path, monkeypatch):
        from app_config.app_config import app_config
        import util as util_mod
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        def _fake_full_path(video_path: str | None):
            if not video_path:
                return None
            return str(tmp_path / video_path)

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            generic = Species(name="Bird")
            sparrow = Species(name="Review Queue Sparrow")
            db.session.add_all([generic, sparrow])
            db.session.flush()

            visit_1 = SpeciesVisit(
                species_id=generic.id,
                start_time=datetime(2026, 3, 24, 12, 0, 0),
                end_time=datetime(2026, 3, 24, 12, 5, 0),
                max_simultaneous=1,
            )
            visit_2 = SpeciesVisit(
                species_id=sparrow.id,
                start_time=datetime(2026, 3, 24, 13, 0, 0),
                end_time=datetime(2026, 3, 24, 13, 5, 0),
                max_simultaneous=1,
            )
            video_1 = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 24, 12, 0, 0),
                end_time=datetime(2026, 3, 24, 12, 0, 30),
                video_path="data/recordings/2026/03/24/120000/video.mp4",
            )
            video_2 = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 24, 13, 0, 0),
                end_time=datetime(2026, 3, 24, 13, 0, 30),
                video_path="data/recordings/2026/03/24/130000/video.mp4",
            )
            db.session.add_all([visit_1, visit_2, video_1, video_2])
            db.session.flush()

            det_1 = VideoSpecies(
                video_id=video_1.id,
                species_id=generic.id,
                species_visit_id=visit_1.id,
                start_time=0.0,
                end_time=2.0,
                confidence=0.11,
                source="video",
                detection_provider="yolo",
            )
            det_2 = VideoSpecies(
                video_id=video_1.id,
                species_id=sparrow.id,
                species_visit_id=visit_1.id,
                start_time=3.0,
                end_time=5.0,
                confidence=0.16,
                source="video",
                detection_provider="frigate",
            )
            det_3 = VideoSpecies(
                video_id=video_2.id,
                species_id=generic.id,
                species_visit_id=visit_2.id,
                start_time=0.0,
                end_time=2.0,
                confidence=0.08,
                source="video",
                detection_provider="yolo",
            )
            db.session.add_all([det_1, det_2, det_3])
            db.session.commit()

            for rel_path in (
                "data/recordings/2026/03/24/120000/video.mp4",
                "data/recordings/2026/03/24/130000/video.mp4",
            ):
                full = tmp_path / rel_path
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_bytes(b"video-data")

            det_1_id = det_1.id
            det_2_id = det_2.id
            det_3_id = det_3.id
            video_1_id = video_1.id
            video_2_id = video_2.id
            visit_1_id = visit_1.id
            visit_2_id = visit_2.id

        monkeypatch.setattr(util_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(data_paths_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(
            broken_videos_inventory_mod,
            "full_path_for_video",
            _fake_full_path,
        )

        preview = client.post(
            "/api/ui/system/review-queue/delete-preview",
            json={
                "date": "2026-03-24",
                "time_of_day": "all",
                "unknown_ids": [det_1_id, det_2_id, det_3_id],
            },
        )
        assert preview.status_code == 200
        preview_body = preview.get_json()
        assert preview_body["unknown_count"] == 3
        assert preview_body["video_count"] == 2
        assert preview_body["confirmation_phrase"] == "permanent_full"
        assert sorted(preview_body["video_ids"]) == [video_1_id, video_2_id]
        assert preview_body["videos"][0]["unknown_count"] >= 1

        apply = client.post(
            "/api/ui/system/review-queue/delete",
            json={
                "date": "2026-03-24",
                "time_of_day": "all",
                "unknown_ids": [det_1_id, det_2_id, det_3_id],
                "confirm_text": "permanent_full",
            },
        )
        assert apply.status_code == 200
        apply_body = apply.get_json()
        assert apply_body["deletedCount"] == 2
        assert sorted(apply_body["deletedVideoIds"]) == [video_1_id, video_2_id]
        assert apply_body["confirmation_phrase"] == "permanent_full"

        with app.app_context():
            assert db.session.get(Video, video_1_id) is None
            assert db.session.get(Video, video_2_id) is None
            assert db.session.get(VideoSpecies, det_1_id) is None
            assert db.session.get(VideoSpecies, det_2_id) is None
            assert db.session.get(VideoSpecies, det_3_id) is None
            assert db.session.get(SpeciesVisit, visit_1_id) is None
            assert db.session.get(SpeciesVisit, visit_2_id) is None
            assert not (tmp_path / "data/recordings/2026/03/24/120000").exists()
            assert not (tmp_path / "data/recordings/2026/03/24/130000").exists()

        app_config.set("general.settings_password", old_admin or "")
        app_config.set("general.contributor_password", old_contrib or "")

    def test_review_queue_bulk_delete_denies_guest_when_passwords_configured(
        self, app, client
    ):
        from app_config.app_config import app_config

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        with app.app_context():
            app_config.set("general.settings_password", "admin-secret")
            app_config.set("general.contributor_password", "contrib-secret")

        try:
            response = client.post(
                "/api/ui/system/review-queue/delete-preview",
                json={
                    "date": "2026-03-24",
                    "time_of_day": "all",
                    "unknown_ids": [1],
                },
            )
            assert response.status_code == 403
        finally:
            app_config.set("general.settings_password", old_admin or "")
            app_config.set("general.contributor_password", old_contrib or "")

    def test_review_queue_bulk_delete_preview_allows_contributor_session(
        self, app, client
    ):
        """Оператор (contributor) может вызывать предпросмотр — не только admin_track_regen."""
        from app_config.app_config import app_config

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        with app.app_context():
            app_config.set("general.settings_password", "admin-secret")
            app_config.set("general.contributor_password", "contrib-secret")

        try:
            with client.session_transaction() as sess:
                sess["access_role"] = "contributor"
            response = client.post(
                "/api/ui/system/review-queue/delete-preview",
                json={
                    "date": "2026-03-24",
                    "time_of_day": "all",
                    "unknown_ids": [999999],
                },
            )
            assert response.status_code == 400
            assert "not present" in (response.get_json() or {}).get("error", "")
        finally:
            app_config.set("general.settings_password", old_admin or "")
            app_config.set("general.contributor_password", old_contrib or "")

    def test_broken_video_diagnostics_list_delete_preview_and_apply(self, app, client, tmp_path, monkeypatch):
        from app_config.app_config import app_config
        import util as util_mod
        from models import Species, SpeciesVisit, Video, VideoSpecies, db, ActivityLog

        def _fake_full_path(video_path: str | None):
            if not video_path:
                return None
            return str(tmp_path / video_path)

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            sp = Species(name="Diag Sparrow")
            db.session.add(sp)
            db.session.flush()

            visit = SpeciesVisit(
                species_id=sp.id,
                start_time=datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 1, 10, 5, 0, tzinfo=timezone.utc),
                max_simultaneous=1,
            )
            v_ok = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 1, 10, 0, 30, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/01/100000/video.mp4",
            )
            v_broken = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 1, 11, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 1, 11, 0, 30, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/01/110000/video.mp4",
            )
            db.session.add_all([visit, v_ok, v_broken])
            db.session.flush()

            det_ok = VideoSpecies(
                video_id=v_ok.id,
                species_id=sp.id,
                species_visit_id=visit.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.9,
                source="video",
            )
            det_broken = VideoSpecies(
                video_id=v_broken.id,
                species_id=sp.id,
                species_visit_id=visit.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.5,
                source="video",
            )
            db.session.add_all([det_ok, det_broken])
            db.session.commit()

            ok_path = tmp_path / "data/recordings/2026/04/01/100000/video.mp4"
            ok_path.parent.mkdir(parents=True, exist_ok=True)
            ok_path.write_bytes(b"ok")

            v_ok_id = v_ok.id
            v_broken_id = v_broken.id
            det_broken_id = det_broken.id

        monkeypatch.setattr(util_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(data_paths_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(
            broken_videos_inventory_mod,
            "full_path_for_video",
            _fake_full_path,
        )

        listed = client.get("/api/ui/system/diagnostics/broken-videos?limit=20")
        assert listed.status_code == 200
        body = listed.get_json()
        assert body["bucket"] == "broken_video_row"
        ids = {row["video_id"] for row in body["items"]}
        assert v_broken_id in ids
        assert v_ok_id not in ids

        bad_prev = client.post(
            "/api/ui/system/diagnostics/broken-videos/delete-preview",
            json={"video_ids": [v_ok_id]},
        )
        assert bad_prev.status_code == 400

        prev = client.post(
            "/api/ui/system/diagnostics/broken-videos/delete-preview",
            json={"video_ids": [v_broken_id]},
        )
        assert prev.status_code == 200
        assert prev.get_json()["confirmation_phrase"] == "delete_broken_video_rows"

        apply = client.post(
            "/api/ui/system/diagnostics/broken-videos/delete",
            json={
                "video_ids": [v_broken_id],
                "confirm_text": "delete_broken_video_rows",
            },
        )
        assert apply.status_code == 200
        assert apply.get_json()["deletedCount"] == 1

        with app.app_context():
            assert db.session.get(Video, v_broken_id) is None
            assert db.session.get(VideoSpecies, det_broken_id) is None
            assert db.session.get(Video, v_ok_id) is not None
            log = (
                db.session.query(ActivityLog)
                .filter(ActivityLog.type == "admin_diagnostics_cleanup")
                .order_by(ActivityLog.id.desc())
                .first()
            )
            assert log is not None
            assert "broken_video_rows_delete" in (log.data or "")

        app_config.set("general.settings_password", old_admin or "")
        app_config.set("general.contributor_password", old_contrib or "")

    def test_broken_video_zero_byte_and_purge_batch(self, app, client, tmp_path, monkeypatch):
        from app_config.app_config import app_config
        import util as util_mod
        from models import Species, Video, VideoSpecies, db

        def _fake_full_path(video_path: str | None):
            if not video_path:
                return None
            return str(tmp_path / video_path)

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            sp = Species(name="Empty File Species")
            db.session.add(sp)
            db.session.flush()
            v_empty = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 3, 8, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 3, 8, 0, 15, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/03/080000/video.mp4",
            )
            db.session.add(v_empty)
            db.session.flush()
            db.session.add(
                VideoSpecies(
                    video_id=v_empty.id,
                    species_id=sp.id,
                    species_visit_id=None,
                    start_time=0.0,
                    end_time=1.0,
                    confidence=0.8,
                    source="video",
                )
            )
            db.session.commit()
            empty_path = tmp_path / "data/recordings/2026/04/03/080000/video.mp4"
            empty_path.parent.mkdir(parents=True, exist_ok=True)
            empty_path.write_bytes(b"")
            v_empty_id = v_empty.id

        monkeypatch.setattr(util_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(data_paths_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(
            broken_videos_inventory_mod,
            "full_path_for_video",
            _fake_full_path,
        )

        dry = client.post(
            "/api/ui/system/diagnostics/broken-videos/purge",
            json={"dry_run": True, "max_scan": 5000},
        )
        assert dry.status_code == 200
        body = dry.get_json()
        assert body.get("broken_total", 0) >= 1
        assert "video_file_empty" in (body.get("by_reason") or {})

        purge = client.post(
            "/api/ui/system/diagnostics/broken-videos/purge",
            json={
                "dry_run": False,
                "confirm_text": "purge_all_broken_video_rows",
                "limit": 50,
            },
        )
        assert purge.status_code == 200
        assert purge.get_json()["deletedCount"] == 1

        with app.app_context():
            assert db.session.get(Video, v_empty_id) is None

        app_config.set("general.settings_password", old_admin or "")
        app_config.set("general.contributor_password", old_contrib or "")

    def test_no_species_videos_purge_dry_and_batch(self, app, client, tmp_path, monkeypatch):
        from app_config.app_config import app_config
        import util as util_mod
        from models import Species, Video, VideoSpecies, db

        def _fake_full_path(video_path: str | None):
            if not video_path:
                return None
            return str(tmp_path / video_path)

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            sp = Species(name="NoSpecies Purge Bird")
            db.session.add(sp)
            db.session.flush()
            v_empty = Video(
                processor_version="1",
                start_time=datetime(2026, 4, 4, 10, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 4, 10, 0, 20, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/04/100000/video.mp4",
            )
            v_ok = Video(
                processor_version="1",
                start_time=datetime(2026, 4, 4, 11, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 4, 11, 0, 20, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/04/110000/video.mp4",
            )
            db.session.add_all([v_empty, v_ok])
            db.session.flush()
            db.session.add(
                VideoSpecies(
                    video_id=v_ok.id,
                    species_id=sp.id,
                    species_visit_id=None,
                    start_time=0.0,
                    end_time=1.0,
                    confidence=0.7,
                    source="video",
                )
            )
            db.session.commit()
            (tmp_path / "data/recordings/2026/04/04/100000").mkdir(parents=True, exist_ok=True)
            (tmp_path / "data/recordings/2026/04/04/100000/video.mp4").write_bytes(b"x")
            (tmp_path / "data/recordings/2026/04/04/110000").mkdir(parents=True, exist_ok=True)
            (tmp_path / "data/recordings/2026/04/04/110000/video.mp4").write_bytes(b"ok")
            v_empty_id = v_empty.id
            v_ok_id = v_ok.id

        monkeypatch.setattr(util_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(data_paths_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(
            broken_videos_inventory_mod,
            "full_path_for_video",
            _fake_full_path,
        )

        dry = client.post(
            "/api/ui/system/diagnostics/no-species-videos/purge",
            json={"dry_run": True},
        )
        assert dry.status_code == 200
        body = dry.get_json()
        assert body.get("without_species_total", 0) >= 1
        assert v_empty_id in (body.get("sample_video_ids") or [])

        purge = client.post(
            "/api/ui/system/diagnostics/no-species-videos/purge",
            json={
                "dry_run": False,
                "confirm_text": "purge_videos_without_species",
                "limit": 50,
            },
        )
        assert purge.status_code == 200
        assert purge.get_json()["deletedCount"] == 1

        with app.app_context():
            assert db.session.get(Video, v_empty_id) is None
            assert db.session.get(Video, v_ok_id) is not None

        app_config.set("general.settings_password", old_admin or "")
        app_config.set("general.contributor_password", old_contrib or "")

    def test_review_only_noise_candidates_list(self, app, client, tmp_path, monkeypatch):
        from app_config.app_config import app_config
        import util as util_mod
        from models import Species, Video, VideoSpecies, db

        def _fake_full_path(video_path: str | None):
            if not video_path:
                return None
            return str(tmp_path / video_path)

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        with app.app_context():
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            bird = Species(name="Bird")
            db.session.add(bird)
            db.session.flush()
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 2, 12, 0, 10, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/02/120000/video.mp4",
            )
            db.session.add(video)
            db.session.flush()
            det = VideoSpecies(
                video_id=video.id,
                species_id=bird.id,
                species_visit_id=None,
                start_time=0.0,
                end_time=1.0,
                confidence=0.2,
                source="video",
                detection_provider="yolo",
            )
            db.session.add(det)
            db.session.commit()
            det_id = det.id
            vid = video.id

            full = tmp_path / "data/recordings/2026/04/02/120000/video.mp4"
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(b"x")

        monkeypatch.setattr(util_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(data_paths_mod, "full_path_for_video", _fake_full_path)
        monkeypatch.setattr(
            broken_videos_inventory_mod,
            "full_path_for_video",
            _fake_full_path,
        )

        r = client.get("/api/ui/system/diagnostics/review-only-noise-candidates?limit=50")
        assert r.status_code == 200
        payload = r.get_json()
        assert payload["bucket"] == "review_only_noise_candidate"
        row = next(x for x in payload["items"] if x["detection_id"] == det_id)
        assert row["video_id"] == vid
        assert row["species"] == "Bird"
        assert row["video_file_issue"] is None

        app_config.set("general.settings_password", old_admin or "")
        app_config.set("general.contributor_password", old_contrib or "")
