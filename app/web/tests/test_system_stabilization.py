"""Regression tests for stabilization work across system maintenance and overview."""

from datetime import datetime, timedelta, timezone

from services.http_response_cache import bust_response_caches


class TestSystemMaintenanceEndpoints:
    def test_clean_orphaned_visits_preview_and_apply(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set('general.settings_password', '')
            app_config.set('general.contributor_password', '')
            sp_visit = Species(name='Preview Visit Species')
            sp_detection = Species(name='Preview Detection Species')
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
                processor_version='test',
                start_time=datetime(2026, 3, 24, 11, 0, 0),
                end_time=datetime(2026, 3, 24, 11, 1, 0),
                video_path='data/recordings/2026/03/24/110000/video.mp4',
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
                source='video',
            )
            db.session.add(detection)
            db.session.commit()

            sp_detection_id = sp_detection.id
            orphan_id = orphan.id
            linked_id = linked.id
            detection_id = detection.id

        preview = client.post('/api/ui/system/clean-orphaned-visits', json={'dry_run': True})
        assert preview.status_code == 200
        assert preview.json['dry_run'] is True
        assert preview.json['orphaned'] == 1
        assert preview.json['synced_would_update'] == 1

        with app.app_context():
            assert db.session.get(SpeciesVisit, orphan_id) is not None
            persisted = db.session.get(VideoSpecies, detection_id)
            assert persisted is not None
            assert persisted.species_visit_id == linked_id
            assert persisted.species_id == sp_detection_id

        apply = client.post('/api/ui/system/clean-orphaned-visits', json={'dry_run': False})
        assert apply.status_code == 200
        assert apply.json['dry_run'] is False
        assert apply.json['orphaned'] == 1
        assert apply.json['synced'] == 1

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
            app_config.set('general.settings_password', '')
            app_config.set('general.contributor_password', '')
            species = Species(name='Realign Species')
            db.session.add(species)
            db.session.flush()

            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 24, 9, 0, 0),
                end_time=datetime(2026, 3, 24, 9, 30, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version='test',
                start_time=datetime(2026, 3, 24, 9, 10, 0),
                end_time=datetime(2026, 3, 24, 9, 12, 0),
                video_path='data/recordings/2026/03/24/091000/video.mp4',
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
                source='video',
            )
            db.session.add(detection)
            db.session.commit()
            visit_id = visit.id

        preview = client.post('/api/ui/system/realign-visit-times', json={'dry_run': True})
        assert preview.status_code == 200
        assert preview.json['dry_run'] is True
        assert preview.json['updated'] == 1

        with app.app_context():
            visit = db.session.get(SpeciesVisit, visit_id)
            assert visit.start_time == datetime(2026, 3, 24, 9, 0, 0)
            assert visit.end_time == datetime(2026, 3, 24, 9, 30, 0)

        apply = client.post('/api/ui/system/realign-visit-times', json={'dry_run': False})
        assert apply.status_code == 200
        assert apply.json['dry_run'] is False
        assert apply.json['updated'] == 1

        with app.app_context():
            visit = db.session.get(SpeciesVisit, visit_id)
            assert visit.start_time == datetime(2026, 3, 24, 9, 10, 15)
            assert visit.end_time == datetime(2026, 3, 24, 9, 10, 45)

    def test_split_large_gap_visits_preview_and_apply(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set('general.settings_password', '')
            app_config.set('general.contributor_password', '')
            species = Species(name='Gap Split Species')
            db.session.add(species)
            db.session.flush()

            broken_visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 25, 7, 13, 0),
                end_time=datetime(2026, 4, 1, 8, 47, 26),
                max_simultaneous=1,
            )
            early_video = Video(
                processor_version='test',
                start_time=datetime(2026, 3, 25, 7, 13, 0),
                end_time=datetime(2026, 3, 25, 7, 13, 30),
                video_path='data/recordings/2026/03/25/071300/video.mp4',
            )
            late_video = Video(
                processor_version='test',
                start_time=datetime(2026, 4, 1, 8, 47, 0),
                end_time=datetime(2026, 4, 1, 8, 47, 30),
                video_path='data/recordings/2026/04/01/084700/video.mp4',
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
                source='video',
            )
            late_detection = VideoSpecies(
                video_id=late_video.id,
                species_id=species.id,
                species_visit_id=broken_visit.id,
                start_time=14.0,
                end_time=26.3,
                confidence=0.98,
                source='video',
            )
            db.session.add_all([late_detection, early_detection])
            db.session.commit()
            species_id = species.id
            broken_visit_id = broken_visit.id
            late_detection_id = late_detection.id

        preview = client.post('/api/ui/system/split-large-gap-visits', json={'dry_run': True})
        assert preview.status_code == 200
        assert preview.json['dry_run'] is True
        assert preview.json['affected_visits'] == 1
        assert preview.json['created_visits'] == 1
        assert preview.json['reassigned_detections'] == 1

        with app.app_context():
            assert SpeciesVisit.query.count() == 1

        apply = client.post('/api/ui/system/split-large-gap-visits', json={'dry_run': False})
        assert apply.status_code == 200
        assert apply.json['dry_run'] is False
        assert apply.json['affected_visits'] == 1
        assert apply.json['created_visits'] == 1
        assert apply.json['reassigned_detections'] == 1

        with app.app_context():
            visits = (
                SpeciesVisit.query
                .filter_by(species_id=species_id)
                .order_by(SpeciesVisit.start_time.asc())
                .all()
            )
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
        from models import Species, SpeciesVisit, db

        with app.app_context():
            species = Species(name='Midnight Species')
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
        response = client.get('/api/ui/overview', query_string={'start_time': start, 'end_time': end})

        assert response.status_code == 200
        body = response.get_json()
        assert body['stats']['uniqueSpecies'] == 1
        assert body['stats']['totalDetections'] == 2
        assert body['stats']['busiestHour'] == 3
        assert body['topSpecies'][0]['detections'][3] == 2
        assert body['lastDetection']['species_name'] == 'Midnight Species'

    def test_overview_date_uses_observer_local_day_and_local_hour(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, db

        with app.app_context():
            app_config.set('secrets.latitude', '55.7558')
            app_config.set('secrets.longitude', '37.6176')
            species = Species(name='Local Time Species')
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

        response = client.get('/api/ui/overview', query_string={'date': '2026-03-25'})

        assert response.status_code == 200
        body = response.get_json()
        assert body['stats']['uniqueSpecies'] == 1
        assert body['stats']['busiestHour'] == 0
        assert body['topSpecies'][0]['detections'][0] == 3

    def test_overview_date_counts_overlapping_video_duration_and_local_temperature(
        self, app, client,
    ):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set('secrets.latitude', '55.7558')
            app_config.set('secrets.longitude', '37.6176')
            species = Species(name='Overlap Video Species')
            db.session.add(species)
            db.session.flush()
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 24, 21, 2, 0),
                end_time=datetime(2026, 3, 24, 21, 4, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version='test',
                start_time=datetime(2026, 3, 24, 20, 55, 0),
                end_time=datetime(2026, 3, 24, 21, 5, 0),
                video_path='data/recordings/2026/03/24/205500/video.mp4',
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
                    source='video',
                    detection_provider='yolo',
                ),
            )
            db.session.commit()

        bust_response_caches()

        response = client.get('/api/ui/overview', query_string={'date': '2026-03-25'})

        assert response.status_code == 200
        body = response.get_json()
        assert body['stats']['videoDuration'] == 600
        assert body['hourlyTemperature'][0] == 5.5

    def test_overview_detection_by_provider_counts_detection_rows_not_visit_size(
        self, app, client,
    ):
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            species = Species(name='Provider Count Species')
            db.session.add(species)
            db.session.flush()
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 25, 8, 0, 0),
                end_time=datetime(2026, 3, 25, 8, 10, 0),
                max_simultaneous=5,
            )
            video = Video(
                processor_version='test',
                start_time=datetime(2026, 3, 25, 8, 0, 0),
                end_time=datetime(2026, 3, 25, 8, 0, 30),
                video_path='data/recordings/2026/03/25/080000/video.mp4',
            )
            db.session.add_all([visit, video])
            db.session.flush()
            db.session.add_all([
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=visit.id,
                    start_time=0.0,
                    end_time=3.0,
                    confidence=0.9,
                    source='video',
                    detection_provider='yolo',
                ),
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=visit.id,
                    start_time=4.0,
                    end_time=6.0,
                    confidence=0.88,
                    source='video',
                    detection_provider='yolo',
                ),
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=visit.id,
                    start_time=7.0,
                    end_time=9.0,
                    confidence=0.82,
                    source='video',
                    detection_provider='frigate',
                ),
            ])
            db.session.commit()

        bust_response_caches()

        start = int(datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        end = int(datetime(2026, 3, 25, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        response = client.get('/api/ui/overview', query_string={'start_time': start, 'end_time': end})

        assert response.status_code == 200
        body = response.get_json()
        assert body['stats']['detectionByProvider']['yolo'] == 2


class TestObserverLocalRanges:
    def test_observer_local_night_covers_early_morning_of_selected_date(self, app):
        from app_config.app_config import app_config
        from util import observer_local_range

        with app.app_context():
            app_config.set('secrets.latitude', '55.7558')
            app_config.set('secrets.longitude', '37.6176')
            start_dt, end_dt = observer_local_range('2026-03-25', time_of_day='night')

        assert start_dt == datetime(2026, 3, 24, 21, 0, 0)
        assert end_dt == datetime(2026, 3, 25, 2, 59, 59, 999999)
