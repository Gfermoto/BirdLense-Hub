"""API integration tests for web service."""

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest


class TestMetrics:
    """Prometheus /metrics endpoint."""

    def test_metrics_returns_prometheus_format(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "text/plain" in (r.content_type or "")
        body = r.get_data(as_text=True)
        assert "birdlense_detections_total" in body
        assert "birdlense_species_count" in body
        assert "birdlense_videos_total" in body
        assert "birdlense_processor_heartbeat_age_seconds" in body
        assert "birdlense_processor_heartbeat_stale" in body
        assert "# HELP" in body
        assert "# TYPE" in body

    def test_metrics_values_are_numeric(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        for line in body.split("\n"):
            if line and not line.startswith("#"):
                parts = line.split()
                assert len(parts) >= 2
                try:
                    float(parts[1])
                except ValueError:
                    pytest.fail(f"Metric value not numeric: {parts[1]!r}")

    def test_api_metrics_same_as_metrics(self, client):
        """`/api/metrics` — отдельный эндпоинт для Grafana, тот же формат."""
        r = client.get("/api/metrics")
        assert r.status_code == 200
        assert "text/plain" in (r.content_type or "")
        body = r.get_data(as_text=True)
        assert "birdlense_cpu_usage_percent" in body
        assert "birdlense_memory_used_percent" in body
        assert "birdlense_disk_used_percent" in body
        assert "birdlense_detections_total" in body

    def test_metrics_expose_http_request_counters_and_histogram(self, client):
        assert client.get("/api/ui/health").status_code == 200
        # First scrape captures previous request stats.
        assert client.get("/metrics").status_code == 200
        body = client.get("/metrics").get_data(as_text=True)
        assert "birdlense_http_requests_total" in body
        assert "birdlense_http_request_duration_ms_bucket" in body

    def test_metrics_summary_json(self, client):
        r = client.get("/api/metrics/summary")
        assert r.status_code == 200
        assert r.is_json
        data = r.get_json()
        assert data.get("service") == "birdlense-hub"
        assert "notify_preview_24h" in data
        assert "notify_preview_generated_24h" in data
        assert "detections_total" in data
        assert isinstance(data["notify_preview_24h"], dict)

    def test_system_metrics_live_only(self, client):
        r = client.get("/api/ui/system/metrics")
        assert r.status_code == 200
        body = r.json
        assert "cpu" in body and "memory" in body and "disk" in body
        assert "visitors" not in body

    def test_system_visitors_endpoint_counts_anonymous_browsers(self, app, client):
        payload = {"browser_id": "11111111-1111-4111-8111-111111111111"}
        headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile"}
        r1 = client.post("/api/ui/system/visitors/track", json=payload, headers=headers)
        assert r1.status_code == 200

        r2 = client.post("/api/ui/system/visitors/track", json=payload, headers=headers)
        assert r2.status_code == 200

        r3 = client.post(
            "/api/ui/system/visitors/track",
            json={"browser_id": "22222222-2222-4222-8222-222222222222"},
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        )
        assert r3.status_code == 200

        r = client.get("/api/ui/system/visitors", query_string={"days": 7})
        assert r.status_code == 200
        assert r.json["period_days"] == 7
        assert r.json["method"] == "anonymous_browser_id"
        assert r.json["unique_visits"] == 2
        assert r.json["browser_count"] == 2
        assert r.json["device_breakdown"]["mobile"] == 1
        assert r.json["device_breakdown"]["desktop"] == 1
        assert isinstance(r.json["unique_visits"], int)
        assert "species_visit_count" not in r.json

    def test_system_visitors_counts_browser_days_as_unique_visits(self, app, client):
        from models import SiteVisitor, db
        from services.visitor_stats_service import browser_hash

        with app.app_context():
            db.session.add_all(
                [
                    SiteVisitor(
                        browser_hash=browser_hash("same-browser"),
                        seen_day="2026-04-01",
                        device_class="desktop",
                        first_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    ),
                    SiteVisitor(
                        browser_hash=browser_hash("same-browser"),
                        seen_day="2026-04-02",
                        device_class="desktop",
                        first_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    ),
                ]
            )
            db.session.commit()

        response = client.get("/api/ui/system/visitors", query_string={"days": 7})

        assert response.status_code == 200
        assert response.json["browser_count"] >= 1
        assert response.json["unique_visits"] >= 2

    def test_system_metrics_history_endpoint(self, app, client):
        from models import db, SystemResourceSample

        now = datetime.now(timezone.utc)
        with app.app_context():
            db.session.add(
                SystemResourceSample(
                    recorded_at=now,
                    cpu_percent=11.5,
                    memory_percent=44.0,
                    disk_percent=55.0,
                    gpu_percent=None,
                )
            )
            db.session.commit()
        r = client.get("/api/ui/system/metrics/history", query_string={"hours": 24})
        assert r.status_code == 200
        body = r.json
        assert "samples" in body
        assert len(body["samples"]) >= 1
        s0 = body["samples"][0]
        assert s0["cpu"] == 11.5
        assert "t" in s0
        assert "sample_interval_seconds" in body
        assert "retention_hours" in body


class TestLibraryDatasetFlow:
    """Smoke for critical Library dataset happy-path endpoints."""

    def test_library_dataset_endpoints_smoke(self, app, client, monkeypatch):
        from app_config.app_config import app_config

        monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
        monkeypatch.delenv("FLASK_ENV", raising=False)

        with app.app_context():
            old_admin = app_config.get("general.settings_password")
            old_contrib = app_config.get("general.contributor_password")
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            try:
                r_stats = client.get("/api/ui/storage/stats")
                assert r_stats.status_code == 200
                assert isinstance(r_stats.json, list)

                r_tracks_status = client.get("/api/ui/system/regenerate-tracks/status")
                assert r_tracks_status.status_code == 200
                assert "status" in r_tracks_status.json

                r_tracks_one_missing = client.post(
                    "/api/ui/videos/999999/regenerate-tracks",
                    json={},
                )
                assert r_tracks_one_missing.status_code == 404

                r_clean = client.post(
                    "/api/ui/dataset/clean",
                    json={
                        "dry_run": True,
                        "remove_fullframe": False,
                        "remove_orphaned": False,
                    },
                )
                assert r_clean.status_code == 200
                assert "dry_run" in r_clean.json
            finally:
                app_config.set("general.settings_password", old_admin)
                app_config.set("general.contributor_password", old_contrib)


class TestTrackRegenFallback:
    """Fast regen should escalate to a precise pass only when needed."""

    def test_precise_fallback_runs_after_empty_fast_pass(self):
        from services.track_regen_service import run_track_regen_with_precise_fallback

        calls = []

        def fake_process(video_path, **kwargs):
            calls.append((video_path, kwargs["frame_step"], kwargs["lores_size"]))
            if len(calls) == 1:
                return []
            return [{"species_name": "Eurasian Jay"}]

        detections, precise_used = run_track_regen_with_precise_fallback(
            "/tmp/test.mp4",
            fake_process,
            {
                "frame_step": 6,
                "lores_size": (512, 512),
            },
            lambda: {
                "frame_step": 2,
                "lores_size": (640, 640),
            },
        )

        assert precise_used is True
        assert detections == [{"species_name": "Eurasian Jay"}]
        assert calls == [
            ("/tmp/test.mp4", 6, (512, 512)),
            ("/tmp/test.mp4", 2, (640, 640)),
        ]

    def test_precise_fallback_skips_second_pass_when_fast_found_detections(self):
        from services.track_regen_service import run_track_regen_with_precise_fallback

        calls = []

        def fake_process(video_path, **kwargs):
            calls.append((video_path, kwargs["frame_step"]))
            return [{"species_name": "Great Tit"}]

        detections, precise_used = run_track_regen_with_precise_fallback(
            "/tmp/test.mp4",
            fake_process,
            {
                "frame_step": 6,
                "lores_size": (512, 512),
            },
            lambda: {
                "frame_step": 2,
                "lores_size": (640, 640),
            },
        )

        assert precise_used is False
        assert detections == [{"species_name": "Great Tit"}]
        assert calls == [("/tmp/test.mp4", 6)]

    def test_fast_kwargs_rejects_unknown_for_explicit_signature_process(self):
        """Лишний ключ в ``fast_kwargs`` — TypeError до входа в процессор."""
        from services.track_regen_service import run_track_regen_with_precise_fallback

        def strict_process(video_path: str, frame_step: int = 1):  # noqa: ARG001
            raise AssertionError("process should not be invoked")

        with pytest.raises(TypeError, match="bogus"):
            run_track_regen_with_precise_fallback(
                "/tmp/test.mp4",
                strict_process,
                {"frame_step": 6, "bogus": True},
                None,
            )

    def test_manual_conflict_filter_drops_unknown_same_track(self):
        from types import SimpleNamespace
        from services.system_track_regen_worker import manual_conflict_with_detection

        manual_rows = [
            SimpleNamespace(
                track_id=1,
                start_time=6.0,
                end_time=12.0,
                species=SimpleNamespace(name="Eurasian Jay"),
            )
        ]

        conflict = manual_conflict_with_detection(
            manual_rows,
            {
                "species_name": "Unknown",
                "track_id": 1,
                "start_time": 6.1,
                "end_time": 11.9,
            },
            lambda a, b: a.strip().lower() == b.strip().lower(),
        )
        same_species = manual_conflict_with_detection(
            manual_rows,
            {
                "species_name": "Eurasian Jay",
                "track_id": 1,
                "start_time": 6.1,
                "end_time": 11.9,
            },
            lambda a, b: a.strip().lower() == b.strip().lower(),
        )

        assert conflict is True
        assert same_species is False

    def test_derive_track_regen_species_scope_uses_mapping_and_prior_observed(self, app):
        from models import Species, Video, VideoSpecies, db
        from services.track_regen_service import derive_track_regen_species_scope
        from app_config.app_config import app_config
        from datetime import datetime

        with app.app_context():
            old_mapping = app_config.get("detection.species_mapping")
            app_config.set(
                "detection.species_mapping",
                {
                    "Corvus_cornix": "Hooded Crow",
                    "Sitta_europaea": "Eurasian Nuthatch",
                },
            )
            try:
                sp = Species(name="Eurasian Jay")
                db.session.add(sp)
                db.session.flush()
                video = Video(
                    processor_version="test",
                    start_time=datetime(2026, 3, 25, 8, 0, 0),
                    end_time=datetime(2026, 3, 25, 8, 0, 30),
                    video_path="data/recordings/2026/03/25/080000/video.mp4",
                )
                db.session.add(video)
                db.session.flush()
                db.session.add(
                    VideoSpecies(
                        species_id=sp.id,
                        video_id=video.id,
                        start_time=0.0,
                        end_time=12.0,
                        confidence=0.9,
                        source="video",
                    )
                )
                db.session.commit()

                names = derive_track_regen_species_scope(datetime(2026, 3, 26, 0, 0, 0))

                assert "Eurasian Jay" in names
                assert "Hooded Crow" in names
                assert "Eurasian Nuthatch" in names
            finally:
                app_config.set("detection.species_mapping", old_mapping)

    def test_remap_detection_to_local_scope_maps_exotics_to_unknown(self, app):
        from services.track_regen_service import remap_detection_to_local_scope

        with app.app_context():
            kept = remap_detection_to_local_scope(
                {"species_name": "Eurasian Jay"},
                {"eurasian jay", "great tit"},
            )
            remapped = remap_detection_to_local_scope(
                {"species_name": "Gyrfalcon"},
                {"eurasian jay", "great tit"},
            )

        assert kept["species_name"] == "Eurasian Jay"
        assert remapped["species_name"] == "Unknown"

    def test_single_video_regen_writes_fresh_decision_trace(self, app, monkeypatch):
        import json
        import sys
        import types

        from models import ActivityLog, Video, db
        import services.system_track_regen.worker_core as worker_mod
        from app_config.app_config import app_config

        old_match_live = app_config.get("processor.track_regen_match_live_pipeline")
        app_config.set("processor.track_regen_match_live_pipeline", False)
        try:
            with app.app_context():
                video = Video(
                    processor_version="test",
                    start_time=datetime(2026, 4, 18, 8, 21, 31, tzinfo=timezone.utc),
                    end_time=datetime(2026, 4, 18, 8, 22, 17, tzinfo=timezone.utc),
                    video_path="data/recordings/2026/04/18/082131/video.mp4",
                )
                db.session.add(video)
                db.session.flush()
                db.session.add(
                    ActivityLog(
                        type="decision_trace",
                        data=json.dumps(
                            {
                                "video_id": video.id,
                                "video_path": video.video_path,
                                "accepted_tracks": [{"track_id": -1, "species_name": "Eurasian Jay", "accepted": True}],
                                "rejected_tracks": [],
                            }
                        ),
                    )
                )
                db.session.commit()
                video_id = video.id

            monkeypatch.setattr(worker_mod, "resolve_recording_video_file", lambda _path: "/tmp/fake-regen.mp4")
            monkeypatch.setattr(worker_mod, "_derive_track_regen_species_scope", lambda *_args, **_kwargs: [])
            monkeypatch.setattr(
                worker_mod,
                "VisitProcessor",
                lambda *_args, **_kwargs: types.SimpleNamespace(
                    process_detections=lambda *_a, **_k: [],
                    _get_or_create_species=lambda *_a, **_k: None,
                ),
            )

            fake_track_regenerator = types.SimpleNamespace(
                build_detection_pipeline=lambda *args, **kwargs: ("fp", "dm"),
                process_video_for_tracks=lambda *args, **kwargs: [
                    {
                        "track_id": 1,
                        "species_name": "Bird",
                        "confidence": 0.61,
                        "start_time": 1.2,
                        "end_time": 3.0,
                        "detection_provider": "yolo",
                        "decision_reason": "fallback_bird",
                        "decision_kind": "accepted_generic",
                        "accepted": True,
                        "frames": [{"t": 1.2, "bbox": [0.1, 0.1, 0.2, 0.2]}],
                    }
                ],
            )
            fake_detection_fusion = types.SimpleNamespace(
                build_fused_video_detections=lambda detections, _mqtt_events, **kwargs: list(detections),
            )
            monkeypatch.setitem(sys.modules, "track_regenerator", fake_track_regenerator)
            monkeypatch.setitem(sys.modules, "detection_fusion", fake_detection_fusion)

            worker_mod.run_regenerate_tracks_worker(
                app,
                force=False,
                start_date=None,
                end_date=None,
                video_ids=[video_id],
            )

            with app.app_context():
                logs = (
                    db.session.query(ActivityLog)
                    .filter(ActivityLog.type == "decision_trace")
                    .order_by(ActivityLog.id.asc())
                    .all()
                )
                latest = json.loads(logs[-1].data)

            assert len(logs) == 2
            assert latest["video_id"] == video_id
            assert latest["persisted_tracks"][0]["track_id"] == 1
            assert latest["persisted_tracks"][0]["species_name"] == "Bird"
            assert latest["persisted_tracks"][0]["primary_provider"] == "yolo"
            assert latest["persisted_tracks"][0]["fallback_used"] is True
            assert latest["recording_context"]["triggered_by"] == "track_regen"
            assert latest["recording_context"]["runtime_signals"]["yolo_ran"] is True
            assert latest["recording_context"]["runtime_signals"]["yolo_track_found"] is True
            assert latest["recording_context"]["pipeline_policy"]["regen"]["profile"] == "single_video_quality"
            assert latest["recording_context"]["pipeline_policy"]["regen"]["scope_strategy"] in {
                "global_classifier_scope",
                "match_live_pipeline",
            }
        finally:
            app_config.set("processor.track_regen_match_live_pipeline", old_match_live)

    def test_single_video_regen_uses_quality_profile(self, app, monkeypatch):
        import sys
        import types

        from app_config.app_config import app_config
        from models import Video, db
        import services.system_track_regen.worker_core as worker_mod
        import routes.ui_system_jobs_state as job_state

        with app.app_context():
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 18, 8, 21, 31, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 18, 8, 22, 17, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/18/082131/video.mp4",
            )
            db.session.add(video)
            db.session.commit()
            video_id = video.id

        monkeypatch.setattr(worker_mod, "resolve_recording_video_file", lambda _path: "/tmp/fake-regen.mp4")
        monkeypatch.setattr(worker_mod, "_derive_track_regen_species_scope", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(
            worker_mod,
            "VisitProcessor",
            lambda *_args, **_kwargs: types.SimpleNamespace(
                process_detections=lambda *_a, **_k: [],
                _get_or_create_species=lambda *_a, **_k: None,
            ),
        )

        calls = []
        fake_track_regenerator = types.SimpleNamespace(
            build_detection_pipeline=lambda *args, **kwargs: ("fp", "dm"),
            process_video_for_tracks=lambda _video_path, **kwargs: calls.append(
                (kwargs["lores_size"], kwargs["frame_step"], kwargs["max_runtime_sec"])
            )
            or [
                {
                    "track_id": 1,
                    "species_name": "Bird",
                    "confidence": 0.61,
                    "start_time": 1.2,
                    "end_time": 3.0,
                    "detection_provider": "yolo",
                    "decision_reason": "fallback_bird",
                    "decision_kind": "accepted_generic",
                    "accepted": True,
                }
            ],
        )
        fake_detection_fusion = types.SimpleNamespace(
            build_fused_video_detections=lambda detections, _mqtt_events, **kwargs: list(detections),
        )
        monkeypatch.setitem(sys.modules, "track_regenerator", fake_track_regenerator)
        monkeypatch.setitem(sys.modules, "detection_fusion", fake_detection_fusion)

        old_frame_step = app_config.get("processor.track_regen_frame_step")
        old_lores = app_config.get("processor.track_regen_lores_px")
        old_live = app_config.get("processor.track_regen_match_live_pipeline")
        old_inference_lores = app_config.get("processor.inference_lores_px")
        old_timeout = app_config.get("processor.track_regen_video_timeout_sec")
        old_precise_timeout = app_config.get("processor.track_regen_precise_timeout_sec")
        try:
            app_config.set("processor.track_regen_frame_step", 6)
            app_config.set("processor.track_regen_lores_px", 512)
            app_config.set("processor.track_regen_match_live_pipeline", False)
            app_config.set("processor.inference_lores_px", 640)
            app_config.set("processor.track_regen_video_timeout_sec", 300)
            app_config.set("processor.track_regen_precise_timeout_sec", 420)

            worker_mod.run_regenerate_tracks_worker(
                app,
                force=False,
                start_date=None,
                end_date=None,
                video_ids=[video_id],
            )
        finally:
            app_config.set("processor.track_regen_frame_step", old_frame_step)
            app_config.set("processor.track_regen_lores_px", old_lores)
            app_config.set("processor.track_regen_match_live_pipeline", old_live)
            app_config.set("processor.inference_lores_px", old_inference_lores)
            app_config.set("processor.track_regen_video_timeout_sec", old_timeout)
            app_config.set("processor.track_regen_precise_timeout_sec", old_precise_timeout)

        regen_params = (job_state._regenerate_tracks_status.get("result") or {}).get("regen_params") or {}
        assert calls == [((640, 640), 2, 420)]
        assert regen_params["profile"] == "single_video_quality"
        assert regen_params["frame_step"] == 2
        assert regen_params["lores_px"] == 640
        assert regen_params["max_runtime_sec"] == 420
        assert regen_params["precise_fallback"]["frame_step"] == 1

    def test_single_video_regen_skips_species_wiki_enrichment(self, app, monkeypatch):
        import sys
        import types

        from models import Video, db
        import services.system_track_regen.worker_core as worker_mod
        import services.visit_processor as vp_mod

        with app.app_context():
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 18, 8, 21, 31, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 18, 8, 22, 17, tzinfo=timezone.utc),
                video_path="data/recordings/2026/04/18/082131/video.mp4",
            )
            db.session.add(video)
            db.session.commit()
            video_id = video.id

        monkeypatch.setattr(worker_mod, "resolve_recording_video_file", lambda _path: "/tmp/fake-regen.mp4")
        monkeypatch.setattr(worker_mod, "_derive_track_regen_species_scope", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(
            vp_mod,
            "update_species_info_from_wiki",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("wiki must not be called")),
            raising=False,
        )

        fake_track_regenerator = types.SimpleNamespace(
            build_detection_pipeline=lambda *args, **kwargs: ("fp", "dm"),
            process_video_for_tracks=lambda *args, **kwargs: [
                {
                    "track_id": 1,
                    "species_name": "Bird",
                    "confidence": 0.61,
                    "start_time": 1.2,
                    "end_time": 3.0,
                    "detection_provider": "yolo",
                    "decision_reason": "fallback_bird",
                    "decision_kind": "accepted_generic",
                    "accepted": True,
                }
            ],
        )
        fake_detection_fusion = types.SimpleNamespace(
            build_fused_video_detections=lambda detections, _mqtt_events, **kwargs: list(detections),
        )
        monkeypatch.setitem(sys.modules, "track_regenerator", fake_track_regenerator)
        monkeypatch.setitem(sys.modules, "detection_fusion", fake_detection_fusion)

        worker_mod.run_regenerate_tracks_worker(
            app,
            force=False,
            start_date=None,
            end_date=None,
            video_ids=[video_id],
        )


class TestTimelineExport:
    """Timeline export CSV/JSON."""

    def test_export_requires_params(self, client):
        r = client.get("/api/ui/timeline/export")
        assert r.status_code == 400
        assert "error" in r.json

    def test_export_requires_format(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get("/api/ui/timeline/export", query_string={"start_time": ts, "end_time": ts, "format": "xml"})
        assert r.status_code == 400
        assert "format" in r.json.get("error", "").lower()

    def test_export_json_returns_array(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get("/api/ui/timeline/export", query_string={"start_time": ts, "end_time": ts, "format": "json"})
        assert r.status_code == 200
        assert r.headers.get("Content-Disposition", "").endswith("birdlense_timeline.json")
        import json

        data = json.loads(r.get_data(as_text=True))
        assert isinstance(data, list)

    def test_export_csv_returns_text(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get("/api/ui/timeline/export", query_string={"start_time": ts, "end_time": ts, "format": "csv"})
        assert r.status_code == 200
        assert r.headers.get("Content-Disposition", "").endswith("birdlense_timeline.csv")
        body = r.get_data(as_text=True)
        assert "id" in body or "species_name" in body

    def test_export_ebird_returns_csv(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get("/api/ui/timeline/export", query_string={"start_time": ts, "end_time": ts, "format": "ebird"})
        assert r.status_code == 200
        assert r.headers.get("Content-Disposition", "").endswith("birdlense_ebird.csv")
        assert "text/csv" in (r.content_type or "")

    def test_export_rejects_interval_over_one_day(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            "/api/ui/timeline/export", query_string={"start_time": ts - 86400 * 2, "end_time": ts, "format": "json"}
        )
        assert r.status_code == 400
        assert "error" in r.json


class TestTimeline:
    """Timeline API."""

    def test_timeline_requires_params(self, client):
        r = client.get("/api/ui/timeline")
        assert r.status_code == 400
        assert "error" in r.json

    def test_timeline_returns_list(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get("/api/ui/timeline", query_string={"start_time": ts - 86400, "end_time": ts})
        assert r.status_code == 200
        assert isinstance(r.json, list)

    def test_timeline_rejects_interval_over_one_day(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get("/api/ui/timeline", query_string={"start_time": ts - 86400 * 2, "end_time": ts})
        assert r.status_code == 400

    def test_timeline_accepts_observer_local_date(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set("secrets.latitude", "55.7558")
            app_config.set("secrets.longitude", "37.6176")
            species = Species(name=f"Timeline Local {id(app)}")
            db.session.add(species)
            db.session.flush()
            species_name = species.name
            # Midday UTC on 2026-03-25 lies in observer-local calendar 2026-03-25 for both UTC
            # and Europe/Moscow (unlike late evening UTC on 2026-03-24, which is «next day» only in MSK).
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 25, 14, 0, 0),
                end_time=datetime(2026, 3, 25, 14, 10, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 25, 14, 0, 0),
                end_time=datetime(2026, 3, 25, 14, 0, 30),
                video_path="data/recordings/2026/03/25/140000/video.mp4",
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
        r = client.get(
            "/api/ui/timeline",
            query_string={"date": "2026-03-25"},
        )
        assert r.status_code == 200
        assert any(row.get("species", {}).get("name") == species_name for row in r.json)

    def test_timeline_dedupes_visit_with_multiple_video_species(self, app, client):
        """JOIN VideoSpecies must not duplicate one SpeciesVisit in the JSON list."""
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        with app.app_context():
            app_config.set("secrets.latitude", "55.7558")
            app_config.set("secrets.longitude", "37.6176")
            species = Species(name=f"Timeline Dedup {id(app)}")
            db.session.add(species)
            db.session.flush()
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 25, 14, 0, 0),
                end_time=datetime(2026, 3, 25, 14, 10, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 25, 14, 0, 0),
                end_time=datetime(2026, 3, 25, 14, 0, 30),
                video_path=f"data/recordings/2026/03/25/140001/dedup{id(app)}.mp4",
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
                        end_time=2.0,
                        confidence=0.9,
                        source="video",
                        detection_provider="yolo",
                    ),
                    VideoSpecies(
                        video_id=video.id,
                        species_id=species.id,
                        species_visit_id=visit.id,
                        start_time=3.0,
                        end_time=5.0,
                        confidence=0.85,
                        source="video",
                        detection_provider="frigate",
                    ),
                ]
            )
            db.session.commit()
            visit_id = visit.id

        from services.http_response_cache import bust_response_caches

        bust_response_caches()

        r = client.get(
            "/api/ui/timeline",
            query_string={"date": "2026-03-25"},
        )
        assert r.status_code == 200
        same_visit_rows = [row for row in r.json if row.get("id") == visit_id]
        assert len(same_visit_rows) == 1

    def test_timeline_visit_includes_scales_from_primary_video(self, app, client):
        """Дельта весов в payload визита — с «основного» (самого раннего) ролика (#228)."""
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        from services.http_response_cache import bust_response_caches

        with app.app_context():
            app_config.set("secrets.latitude", "55.7558")
            app_config.set("secrets.longitude", "37.6176")
            species = Species(name=f"Timeline Scales {id(app)}")
            db.session.add(species)
            db.session.flush()
            species_name = species.name
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 25, 14, 0, 0),
                end_time=datetime(2026, 3, 25, 14, 10, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 25, 14, 0, 0),
                end_time=datetime(2026, 3, 25, 14, 0, 30),
                video_path=f"data/recordings/2026/03/25/140002/scales_{id(app)}.mp4",
                scales_weight_delta_kg=0.015,
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
        r = client.get(
            "/api/ui/timeline",
            query_string={"date": "2026-03-25"},
        )
        assert r.status_code == 200
        row = next(
            (x for x in r.json if x.get("species", {}).get("name") == species_name),
            None,
        )
        assert row is not None
        sc = row.get("scales")
        assert sc is not None
        assert abs(float(sc["delta_kg"]) - 0.015) < 1e-6
        assert sc["display_unit"] == "g"
        assert sc["weight_change_grams"] == 15.0
        assert sc["weight_trend"] == "up"

    def test_timeline_visit_includes_nickname_and_model_behavior(self, app, client):
        """Visit payload keeps individual nickname and model behavior label."""
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        from services.http_response_cache import bust_response_caches

        with app.app_context():
            app_config.set("secrets.latitude", "55.7558")
            app_config.set("secrets.longitude", "37.6176")
            species = Species(name=f"Timeline Identity {id(app)}")
            db.session.add(species)
            db.session.flush()
            species_name = species.name
            visit = SpeciesVisit(
                species_id=species.id,
                start_time=datetime(2026, 3, 25, 15, 0, 0),
                end_time=datetime(2026, 3, 25, 15, 10, 0),
                max_simultaneous=1,
            )
            video = Video(
                processor_version="test",
                start_time=datetime(2026, 3, 25, 15, 0, 0),
                end_time=datetime(2026, 3, 25, 15, 0, 30),
                video_path=f"data/recordings/2026/03/25/150002/identity_{id(app)}.mp4",
                behavior_label="feeding",
                behavior_confidence=0.88,
            )
            db.session.add_all([visit, video])
            db.session.flush()
            db.session.add(
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=visit.id,
                    start_time=1.0,
                    end_time=6.0,
                    confidence=0.92,
                    source="video",
                    detection_provider="yolo",
                    track_id=101,
                    individual_nickname="Sparky",
                ),
            )
            db.session.commit()

        bust_response_caches()
        r = client.get("/api/ui/timeline", query_string={"date": "2026-03-25"})
        assert r.status_code == 200
        row = next(
            (x for x in r.json if x.get("species", {}).get("name") == species_name),
            None,
        )
        assert row is not None
        assert row.get("individual_nickname") == "Sparky"
        labels = [e.get("label") for e in row.get("behavior_events") or []]
        assert labels == ["feeding"]
        first_det = (row.get("detections") or [{}])[0]
        assert first_det.get("individual_nickname") == "Sparky"

    def test_timeline_includes_video_not_attached_to_any_visit(self, app, client):
        """Ролик за сутки без SpeciesVisit появляется как unlinked_video."""
        from datetime import datetime, timezone
        from models import Video, db
        from services.http_response_cache import bust_response_caches

        with app.app_context():
            st = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
            v = Video(
                processor_version="test",
                start_time=st,
                end_time=st.replace(minute=1),
                video_path=f"2026/03/24/120000/orphan_timeline_{id(app)}.mp4",
            )
            db.session.add(v)
            db.session.commit()

        bust_response_caches()
        ts_start = int(datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        ts_end = int(datetime(2026, 3, 24, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        r = client.get(
            "/api/ui/timeline",
            query_string={"start_time": ts_start, "end_time": ts_end},
        )
        assert r.status_code == 200
        assert any(row.get("timeline_kind") == "unlinked_video" for row in r.json)
        unlinked = [row for row in r.json if row.get("timeline_kind") == "unlinked_video"]
        assert unlinked and all(row["id"] < 0 for row in unlinked)
        assert all(row.get("detections") == [] for row in unlinked)

    def test_timeline_unlinked_video_keeps_nickname_and_model_behavior(self, app, client):
        """Unlinked video payload must keep nickname and model behavior contract parity."""
        from datetime import datetime, timezone
        from models import Species, Video, VideoSpecies, db
        from services.http_response_cache import bust_response_caches

        with app.app_context():
            species = Species(name=f"Unlinked Identity {id(app)}")
            db.session.add(species)
            db.session.flush()
            st = datetime(2026, 3, 24, 16, 0, 0, tzinfo=timezone.utc)
            v = Video(
                processor_version="test",
                start_time=st,
                end_time=st.replace(minute=1),
                behavior_label="feeding",
                behavior_confidence=0.91,
                video_path=f"2026/03/24/160000/orphan_identity_{id(app)}.mp4",
            )
            db.session.add(v)
            db.session.flush()
            db.session.add(
                VideoSpecies(
                    video_id=v.id,
                    species_id=species.id,
                    start_time=1.0,
                    end_time=8.0,
                    confidence=0.87,
                    source="video",
                    detection_provider="yolo",
                    track_id=77,
                    individual_nickname="Nova",
                ),
            )
            db.session.commit()
            video_id = int(v.id)

        bust_response_caches()
        ts_start = int(datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        ts_end = int(datetime(2026, 3, 24, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        r = client.get(
            "/api/ui/timeline",
            query_string={"start_time": ts_start, "end_time": ts_end},
        )
        assert r.status_code == 200
        row = next(
            (
                x
                for x in r.json
                if x.get("timeline_kind") == "unlinked_video"
                and any(d.get("video_id") == video_id for d in (x.get("detections") or []))
            ),
            None,
        )
        assert row is not None
        assert row.get("individual_nickname") == "Nova"
        labels = [e.get("label") for e in (row.get("behavior_events") or [])]
        assert labels == ["feeding"]
        first_det = (row.get("detections") or [{}])[0]
        assert first_det.get("individual_nickname") == "Nova"
        assert first_det.get("detection_provider") == "yolo"

    def test_timeline_favorite_only_filters_visits_and_orphans(self, app, client):
        """favorite_only=1: визиты без избранного ролика скрыты; осиротевшие favorite — в списке."""
        from datetime import datetime, timezone

        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        from services.http_response_cache import bust_response_caches

        with app.app_context():
            sp_nf = Species(name=f"NoFavTL {id(app)}")
            sp_f = Species(name=f"FavTL {id(app)}")
            db.session.add_all([sp_nf, sp_f])
            db.session.flush()
            nf_name = sp_nf.name
            fav_name = sp_f.name

            st = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
            et = datetime(2026, 3, 24, 12, 0, 30, tzinfo=timezone.utc)
            visit_nf = SpeciesVisit(
                species=sp_nf,
                start_time=st,
                end_time=et,
                max_simultaneous=1,
            )
            v_nf = Video(
                processor_version="test",
                start_time=st,
                end_time=et,
                favorite=False,
                video_path=f"data/recordings/2026/03/24/120001/nf_{id(app)}.mp4",
            )
            vs_nf = VideoSpecies(
                video=v_nf,
                species=sp_nf,
                species_visit=visit_nf,
                start_time=0.0,
                end_time=5.0,
                confidence=0.9,
                source="video",
            )
            st2 = datetime(2026, 3, 24, 13, 0, 0, tzinfo=timezone.utc)
            et2 = datetime(2026, 3, 24, 13, 0, 30, tzinfo=timezone.utc)
            visit_f = SpeciesVisit(
                species=sp_f,
                start_time=st2,
                end_time=et2,
                max_simultaneous=1,
            )
            v_f = Video(
                processor_version="test",
                start_time=st2,
                end_time=et2,
                favorite=True,
                video_path=f"data/recordings/2026/03/24/120002/f_{id(app)}.mp4",
            )
            vs_f = VideoSpecies(
                video=v_f,
                species=sp_f,
                species_visit=visit_f,
                start_time=0.0,
                end_time=5.0,
                confidence=0.91,
                source="video",
            )
            st3 = datetime(2026, 3, 24, 14, 0, 0, tzinfo=timezone.utc)
            et3 = datetime(2026, 3, 24, 14, 0, 30, tzinfo=timezone.utc)
            v_orphan = Video(
                processor_version="test",
                start_time=st3,
                end_time=et3,
                favorite=True,
                video_path=f"data/recordings/2026/03/24/120003/orphan_fav_{id(app)}.mp4",
            )
            db.session.add_all(
                [visit_nf, v_nf, vs_nf, visit_f, v_f, vs_f, v_orphan],
            )
            db.session.commit()

        bust_response_caches()
        ts_start = int(datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        ts_end = int(datetime(2026, 3, 24, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        r = client.get(
            "/api/ui/timeline",
            query_string={"start_time": ts_start, "end_time": ts_end, "favorite_only": "1"},
        )
        assert r.status_code == 200
        names = [row.get("species", {}).get("name") for row in r.json]
        assert nf_name not in names
        assert fav_name in names
        kinds = [row.get("timeline_kind") for row in r.json]
        assert kinds.count("unlinked_video") == 1
        assert len(r.json) == 2

        r_alias = client.get(
            "/api/ui/timeline",
            query_string={"start_time": ts_start, "end_time": ts_end, "favorites": "1"},
        )
        assert r_alias.status_code == 200
        assert len(r_alias.json) == 2

        r_all = client.get(
            "/api/ui/timeline",
            query_string={"start_time": ts_start, "end_time": ts_end},
        )
        assert r_all.status_code == 200
        assert len(r_all.json) >= 3

    def test_favorites_by_species_groups_active_favorite_videos(self, app, client):
        """Catalog view: all favorite videos grouped by detected species; no calendar required."""
        from datetime import datetime, timezone

        from models import Species, Video, VideoSpecies, db
        from services.http_response_cache import bust_response_caches

        with app.app_context():
            sp_a = Species(name=f"Fav Catalog A {id(app)}", image_url="data/images/a.jpg")
            sp_b = Species(name=f"Fav Catalog B {id(app)}", image_url="data/images/b.jpg")
            db.session.add_all([sp_a, sp_b])
            db.session.flush()

            v_a_new = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 10, 15, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 10, 15, 0, 20, tzinfo=timezone.utc),
                favorite=True,
                video_path=f"data/recordings/2026/04/10/150000/fav_a_new_{id(app)}.mp4",
            )
            v_a_old = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 9, 9, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 9, 9, 0, 10, tzinfo=timezone.utc),
                favorite=True,
                video_path=f"data/recordings/2026/04/09/090000/fav_a_old_{id(app)}.mp4",
            )
            v_b = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 8, 8, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 8, 8, 0, 30, tzinfo=timezone.utc),
                favorite=True,
                video_path=f"data/recordings/2026/04/08/080000/fav_b_{id(app)}.mp4",
            )
            v_unlinked = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 7, 7, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 7, 7, 0, 30, tzinfo=timezone.utc),
                favorite=True,
                video_path=f"data/recordings/2026/04/07/070000/fav_unlinked_{id(app)}.mp4",
            )
            v_deleted = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 6, 7, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 6, 7, 0, 30, tzinfo=timezone.utc),
                favorite=True,
                deleted_at=datetime(2026, 4, 6, 8, 0, 0, tzinfo=timezone.utc),
                video_path=f"data/recordings/2026/04/06/070000/fav_deleted_{id(app)}.mp4",
            )
            v_not_fav = Video(
                processor_version="test",
                start_time=datetime(2026, 4, 5, 7, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 5, 7, 0, 30, tzinfo=timezone.utc),
                favorite=False,
                video_path=f"data/recordings/2026/04/05/070000/not_fav_{id(app)}.mp4",
            )
            db.session.add_all([v_a_new, v_a_old, v_b, v_unlinked, v_deleted, v_not_fav])
            db.session.flush()
            db.session.add_all(
                [
                    VideoSpecies(
                        video=v_a_new,
                        species=sp_a,
                        start_time=0,
                        end_time=4,
                        confidence=0.91,
                        source="video",
                    ),
                    VideoSpecies(
                        video=v_a_old,
                        species=sp_a,
                        start_time=0,
                        end_time=3,
                        confidence=0.82,
                        source="video",
                    ),
                    VideoSpecies(
                        video=v_b,
                        species=sp_b,
                        start_time=0,
                        end_time=5,
                        confidence=0.88,
                        source="video",
                    ),
                    VideoSpecies(
                        video=v_not_fav,
                        species=sp_a,
                        start_time=0,
                        end_time=3,
                        confidence=0.99,
                        source="video",
                    ),
                ]
            )
            db.session.commit()
            a_name = sp_a.name
            b_name = sp_b.name
            a_new_id = v_a_new.id
            a_old_id = v_a_old.id
            deleted_id = v_deleted.id
            not_fav_id = v_not_fav.id

        bust_response_caches()
        r = client.get("/api/ui/favorites/by-species")
        assert r.status_code == 200
        body = r.json
        assert body["total_videos"] == 4
        assert body["total_species"] == 2

        groups = {group["species"]["name"]: group for group in body["groups"]}
        assert list(groups)[:2] == [a_name, b_name]
        assert [video["id"] for video in groups[a_name]["videos"]] == [a_new_id, a_old_id]
        assert groups[a_name]["latest_start_time"].startswith("2026-04-10T15:00:00")
        assert groups[a_name]["videos"][0]["species"][0]["confidence"] == 0.91
        assert groups[a_name]["species"]["image_url"] == "data/images/a.jpg"
        assert all(not video["deleted"] for group in body["groups"] for video in group["videos"])
        assert deleted_id not in [video["id"] for group in body["groups"] for video in group["videos"]]
        assert not_fav_id not in [video["id"] for group in body["groups"] for video in group["videos"]]
        assert body["unclassified"]["count"] == 1
        assert body["unclassified"]["videos"][0]["species"] == []


class TestOverview:
    """Overview API with lastDetection."""

    def test_overview_returns_last_detection_key(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        start = ts - 86400  # 1 day ago
        r = client.get("/api/ui/overview", query_string={"start_time": start, "end_time": ts})
        assert r.status_code == 200
        data = r.json
        assert "lastDetection" in data
        assert "topSpecies" in data
        assert "stats" in data

    def test_overview_rejects_invalid_timestamp(self, client):
        r = client.get("/api/ui/overview", query_string={"start_time": "invalid", "end_time": "123"})
        assert r.status_code == 400


class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/api/ui/health")
        assert r.status_code == 200
        assert r.json == {"status": "ok"}

    def test_readiness_returns_checks_and_components(self, client):
        r = client.get("/api/ui/readiness")
        assert r.status_code == 200
        data = r.json
        assert data["status"] == "ok"
        assert data["ready"] is True
        assert "checked_at" in data
        assert data["checks"]["database"]["status"] == "ok"
        assert data["checks"]["data_dir"]["status"] == "ok"
        assert data["checks"]["app_config_dir"]["status"] == "ok"
        assert data["components"]["web"] == "ok"
        sg = data["security_gates"]
        assert sg["runtime"] in ("development", "production")
        assert len(sg["items"]) == 3
        assert {x["id"] for x in sg["items"]} == {
            "strict_api_auth",
            "flask_secret_key",
            "processor_secret",
        }

    def test_readiness_returns_503_when_database_check_fails(self, client, monkeypatch):
        from models import db

        def _boom(*_args, **_kwargs):
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(db.session, "execute", _boom)

        r = client.get("/api/ui/readiness")

        assert r.status_code == 503
        assert r.json["ready"] is False
        assert r.json["checks"]["database"]["status"] == "error"
        assert r.json["checks"]["database"]["error"] == "database_unavailable"

    def test_readiness_survives_component_status_exception(self, client, monkeypatch):
        import services.component_status_service as cs

        def _boom(_session):
            raise RuntimeError("boom components")

        monkeypatch.setattr(cs, "build_component_status_payload", _boom)
        r = client.get("/api/ui/readiness")
        assert r.status_code == 200
        data = r.json
        assert data["ready"] is True
        assert data["components"]["web"] == "ok"
        assert data["components"]["processor"] == "unknown"

    def test_readiness_returns_503_when_processor_heartbeat_check_fails_in_production(
        self,
        client,
        monkeypatch,
    ):
        import services.readiness_service as rs

        monkeypatch.setenv("BIRDLENSE_ENV", "production")

        def _stale(_session):
            return {
                "status": "error",
                "reason": "stale_heartbeat",
                "max_age_seconds": 180,
            }

        monkeypatch.setattr(rs, "_processor_heartbeat_readiness", _stale)

        r = client.get("/api/ui/readiness")

        assert r.status_code == 503
        assert r.json["ready"] is False
        assert r.json["checks"]["processor_heartbeat"]["status"] == "error"
        assert r.json["checks"]["processor_heartbeat"]["reason"] == "stale_heartbeat"


class TestStatus:
    def test_status_returns_component_status(self, client):
        r = client.get("/api/ui/status")
        assert r.status_code == 200
        data = r.json
        assert data["web"] == "ok"
        assert data["processor"] in ("ok", "offline")
        assert data["video"] in ("ok", "unknown", "error", "not_configured")
        assert data["mqtt"] in ("ok", "error", "not_configured", "not_used", "unknown")
        assert data["esphome"] in ("ok", "error", "not_configured", "not_used")
        assert data["yolo"] in ("ok", "unknown")
        assert "active_triggers" in data
        assert isinstance(data["active_triggers"], list)
        assert all(isinstance(x, str) for x in data["active_triggers"])

    def test_status_mqtt_reflects_feed_source(self, client):
        """MQTT status is real when feed.source=mqtt, else not_used."""
        r = client.get("/api/ui/status")
        assert r.status_code == 200
        # Without MQTT broker configured, mqtt is not_configured, not_used, or unknown (timeout)
        assert r.json["mqtt"] in ("ok", "error", "not_configured", "not_used", "unknown")

    def test_status_esphome_reflects_feed_source(self, client):
        """ESPHome status is real when feed.source=esphome, else not_used."""
        r = client.get("/api/ui/status")
        assert r.status_code == 200
        assert r.json["esphome"] in ("ok", "error", "not_configured", "not_used")

    def test_status_survives_component_status_exception(self, client, monkeypatch):
        from services.cache import cache_delete

        import services.component_status_service as cs

        def _boom(_session):
            raise RuntimeError("boom components")

        cache_delete("component_status:v1")
        monkeypatch.setattr(cs, "build_component_status_payload", _boom)
        r = client.get("/api/ui/status")
        assert r.status_code == 200
        assert r.json["web"] == "ok"
        assert r.json["processor"] == "unknown"


class TestSettings:
    def test_settings_get_returns_config(self, client):
        r = client.get("/api/ui/settings")
        # 200 без пароля или с сессией; 403 если пароль задан и сессии нет
        assert r.status_code in (200, 403)
        if r.status_code == 200:
            assert isinstance(r.json, dict)

    def test_settings_with_mcp_token(self, app, client):
        """MCP token в Authorization даёт доступ к settings без сессии."""
        from app_config.app_config import app_config

        old = app_config.get("mcp.token")
        token = "test-mcp-token-ci"
        app_config.set("mcp.token", token)
        try:
            r = client.get("/api/ui/settings", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            assert isinstance(r.json, dict)
        finally:
            app_config.set("mcp.token", old)


class TestFeed:
    def test_feed_dispense_returns_200_or_403_or_500(self, client):
        """Feed dispense route exists; 403 if password required, 500 if MQTT/ESPHome not configured."""
        r = client.post("/api/ui/feed/dispense")
        assert r.status_code in (200, 403, 500)
        if r.status_code == 200:
            assert "message" in r.json
        elif r.status_code in (403, 500):
            assert "error" in r.json


class TestCameras:
    def test_cameras_returns_list(self, client):
        r = client.get("/api/ui/cameras")
        assert r.status_code == 200
        assert "cameras" in r.json
        assert isinstance(r.json["cameras"], list)


class TestWeather:
    def test_weather_returns_dict(self, client):
        r = client.get("/api/ui/weather")
        assert r.status_code == 200
        assert isinstance(r.json, dict)

    def test_weather_includes_source_metadata(self, app, client, monkeypatch):
        import routes.ui_status_push_routes as ui_status_push
        from app_config.app_config import app_config

        monkeypatch.setattr(
            ui_status_push,
            "fetch_weather",
            lambda: {
                "weather_main": "Rain",
                "weather_description": "steady rain",
                "weather_temp": 7,
                "weather_humidity": 100,
                "weather_pressure": 1000,
                "weather_clouds": 100,
                "weather_wind_speed": 3,
            },
        )
        with app.app_context():
            app_config.set("weather.source", "homeassistant")
            r = client.get("/api/ui/weather")

        assert r.status_code == 200
        assert r.json["source"] == "homeassistant"
        assert isinstance(r.json.get("fetched_at"), str)


class TestVideos:
    def test_videos_not_found_returns_404(self, client):
        r = client.get("/api/ui/videos/999999")
        assert r.status_code == 404
        assert "error" in r.json

    def test_video_neighbors_not_found_returns_404(self, client):
        r = client.get("/api/ui/videos/999999/neighbors")
        assert r.status_code == 404
        assert "error" in r.json

    def test_video_neighbors_prev_next_same_utc_day(self, app, client):
        from datetime import datetime, timedelta
        from models import db, Video

        with app.app_context():
            base = datetime(2025, 3, 19, 8, 0, 0)
            videos = []
            for off_hours in (0, 2, 4):
                st = base + timedelta(hours=off_hours)
                v = Video(
                    processor_version="test",
                    start_time=st,
                    end_time=st + timedelta(minutes=1),
                    video_path=f"2025/03/19/{80000 + off_hours}/v.mp4",
                )
                db.session.add(v)
                videos.append(v)
            db.session.commit()
            v1_id, v2_id, v3_id = videos[0].id, videos[1].id, videos[2].id

        r = client.get(f"/api/ui/videos/{v2_id}/neighbors")
        assert r.status_code == 200
        j = r.json
        assert j["day_scope"] == "utc"
        assert j["day_label"] == "2025-03-19"
        assert j["previous_id"] == v1_id
        assert j["next_id"] == v3_id
        assert j["index"] == 1
        assert j["total"] == 3

        r0 = client.get(f"/api/ui/videos/{v1_id}/neighbors")
        assert r0.status_code == 200
        assert r0.json["previous_id"] is None
        assert r0.json["next_id"] == v2_id

        r2 = client.get(f"/api/ui/videos/{v3_id}/neighbors")
        assert r2.status_code == 200
        assert r2.json["previous_id"] == v2_id
        assert r2.json["next_id"] is None

    def test_video_neighbors_local_scope_and_cross_day(self, app, client):
        from datetime import datetime, timedelta
        from models import db, Video

        with app.app_context():
            day1_late = datetime(2025, 3, 19, 22, 30, 0)  # UTC
            day2_early = datetime(2025, 3, 20, 0, 30, 0)  # UTC
            v1 = Video(
                processor_version="test",
                start_time=day1_late,
                end_time=day1_late + timedelta(minutes=1),
                video_path="2025/03/19/223000/v.mp4",
            )
            v2 = Video(
                processor_version="test",
                start_time=day2_early,
                end_time=day2_early + timedelta(minutes=1),
                video_path="2025/03/20/003000/v.mp4",
            )
            db.session.add(v1)
            db.session.add(v2)
            db.session.commit()
            v1_id = v1.id
            v2_id = v2.id

        # UTC+3 browser: 22:30 UTC => 01:30 local next day
        local = client.get(
            f"/api/ui/videos/{v1_id}/neighbors",
            query_string={
                "day_scope": "local",
                "tz_offset_minutes": -180,
                "cross_day": "1",
            },
        )
        assert local.status_code == 200
        data = local.json
        assert data["day_scope"] == "local"
        assert data["day_label"] == "2025-03-20"
        assert data["timezone_offset_minutes"] == -180
        # В local-дне оба ролика: сосед справа есть
        assert data["next_id"] == v2_id

    def test_video_neighbors_can_follow_primary_videos_of_visits(self, app, client):
        from datetime import datetime, timedelta
        from models import db, Video, Species, SpeciesVisit, VideoSpecies

        with app.app_context():
            species = Species(name="Visit Neighbor Bird")
            db.session.add(species)
            db.session.flush()

            base = datetime(2025, 3, 21, 8, 0, 0)

            def make_video(offset_minutes: int):
                st = base + timedelta(minutes=offset_minutes)
                video = Video(
                    processor_version="test",
                    start_time=st,
                    end_time=st + timedelta(minutes=1),
                    video_path=f"2025/03/21/{80000 + offset_minutes}/v.mp4",
                )
                db.session.add(video)
                db.session.flush()
                return video

            v1a = make_video(0)
            v1b = make_video(5)
            v2a = make_video(60)
            v2b = make_video(65)
            v3a = make_video(120)
            v3b = make_video(125)

            visits = []
            for idx, (primary, extra) in enumerate(((v1a, v1b), (v2a, v2b), (v3a, v3b)), start=1):
                visit = SpeciesVisit(
                    species_id=species.id,
                    start_time=primary.start_time,
                    end_time=extra.end_time,
                    max_simultaneous=1,
                )
                db.session.add(visit)
                db.session.flush()
                db.session.add(
                    VideoSpecies(
                        video_id=primary.id,
                        species_id=species.id,
                        species_visit_id=visit.id,
                        start_time=0.0,
                        end_time=30.0,
                        confidence=0.9,
                        source="video",
                        track_id=idx * 10,
                    ),
                )
                db.session.add(
                    VideoSpecies(
                        video_id=extra.id,
                        species_id=species.id,
                        species_visit_id=visit.id,
                        start_time=0.0,
                        end_time=30.0,
                        confidence=0.8,
                        source="video",
                        track_id=idx * 10 + 1,
                    ),
                )
                visits.append((visit, primary, extra))

            db.session.commit()
            target_visit_id = visits[1][0].id
            target_extra_id = visits[1][2].id
            prev_primary_id = visits[0][1].id
            next_primary_id = visits[2][1].id

        r = client.get(
            f"/api/ui/videos/{target_extra_id}/neighbors",
            query_string={
                "day_scope": "utc",
                "cross_day": "1",
                "visit_id": target_visit_id,
                "neighbor_mode": "visit_primary",
            },
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["previous_id"] == prev_primary_id
        assert data["next_id"] == next_primary_id
        assert data["total"] == 3
        assert data["index"] == 1

    def test_video_neighbors_visit_primary_requires_visit_id(self, app, client):
        from models import db, Video

        with app.app_context():
            video = Video(
                processor_version="test",
                start_time=datetime(2025, 3, 21, 8, 0, 0),
                end_time=datetime(2025, 3, 21, 8, 1, 0),
                video_path="2025/03/21/080000/v.mp4",
            )
            db.session.add(video)
            db.session.commit()
            video_id = video.id

        response = client.get(
            f"/api/ui/videos/{video_id}/neighbors",
            query_string={"neighbor_mode": "visit_primary"},
        )

        assert response.status_code == 400
        assert "visit_id" in response.get_json()["error"]

    def test_video_neighbors_visit_primary_uses_primary_video_inside_current_day(
        self,
        app,
        client,
    ):
        from models import db, Video, Species, SpeciesVisit, VideoSpecies

        with app.app_context():
            species = Species(name="Cross Midnight Visit Neighbor Bird")
            db.session.add(species)
            db.session.flush()

            cross_primary = Video(
                processor_version="test",
                start_time=datetime(2025, 3, 20, 23, 58, 0),
                end_time=datetime(2025, 3, 21, 0, 0, 0),
                video_path="2025/03/20/235800/v.mp4",
            )
            same_day_extra = Video(
                processor_version="test",
                start_time=datetime(2025, 3, 21, 0, 2, 0),
                end_time=datetime(2025, 3, 21, 0, 3, 0),
                video_path="2025/03/21/000200/v.mp4",
            )
            next_visit_primary = Video(
                processor_version="test",
                start_time=datetime(2025, 3, 21, 1, 0, 0),
                end_time=datetime(2025, 3, 21, 1, 1, 0),
                video_path="2025/03/21/010000/v.mp4",
            )
            db.session.add_all([cross_primary, same_day_extra, next_visit_primary])
            db.session.flush()

            visit1 = SpeciesVisit(
                species_id=species.id,
                start_time=cross_primary.start_time,
                end_time=same_day_extra.end_time,
                max_simultaneous=1,
            )
            visit2 = SpeciesVisit(
                species_id=species.id,
                start_time=next_visit_primary.start_time,
                end_time=next_visit_primary.end_time,
                max_simultaneous=1,
            )
            db.session.add_all([visit1, visit2])
            db.session.flush()

            db.session.add_all(
                [
                    VideoSpecies(
                        video_id=cross_primary.id,
                        species_id=species.id,
                        species_visit_id=visit1.id,
                        start_time=0.0,
                        end_time=10.0,
                        confidence=0.9,
                        source="video",
                    ),
                    VideoSpecies(
                        video_id=same_day_extra.id,
                        species_id=species.id,
                        species_visit_id=visit1.id,
                        start_time=0.0,
                        end_time=10.0,
                        confidence=0.88,
                        source="video",
                    ),
                    VideoSpecies(
                        video_id=next_visit_primary.id,
                        species_id=species.id,
                        species_visit_id=visit2.id,
                        start_time=0.0,
                        end_time=10.0,
                        confidence=0.91,
                        source="video",
                    ),
                ]
            )
            db.session.commit()

            same_day_video_id = same_day_extra.id
            visit1_id = visit1.id
            next_primary_id = next_visit_primary.id

        response = client.get(
            f"/api/ui/videos/{same_day_video_id}/neighbors",
            query_string={
                "neighbor_mode": "visit_primary",
                "visit_id": visit1_id,
                "day_scope": "utc",
            },
        )

        assert response.status_code == 200
        assert response.get_json()["next_id"] == next_primary_id

    def test_video_neighbors_includes_clip_starting_before_day_but_overlapping(
        self,
        app,
        client,
    ):
        """Локальный день UTC−5: клип с start до day_start UTC, но пересекающий сутки — в списке."""
        from datetime import datetime
        from models import db, Video

        with app.app_context():
            # tz_offset +300 (JS): local = UTC − 5h. Локальные 2025-03-20 → [Mar20 05:00, Mar21 05:00) UTC.
            overlap_early_start = datetime(2025, 3, 20, 4, 0, 0)
            overlap_early_end = datetime(2025, 3, 21, 4, 0, 0)
            anchor_start = datetime(2025, 3, 21, 3, 0, 0)
            anchor_end = datetime(2025, 3, 21, 3, 30, 0)
            overlap = Video(
                processor_version="test",
                start_time=overlap_early_start,
                end_time=overlap_early_end,
                video_path="2025/03/20/040000/overlap.mp4",
            )
            anchor = Video(
                processor_version="test",
                start_time=anchor_start,
                end_time=anchor_end,
                video_path="2025/03/21/030000/v.mp4",
            )
            db.session.add_all([overlap, anchor])
            db.session.commit()
            overlap_id, anchor_id = overlap.id, anchor.id

        r = client.get(
            f"/api/ui/videos/{anchor_id}/neighbors",
            query_string={
                "day_scope": "local",
                "tz_offset_minutes": 300,
            },
        )
        assert r.status_code == 200
        j = r.json
        assert j["day_label"] == "2025-03-20"
        assert j["total"] == 2
        assert j["index"] == 1
        assert j["previous_id"] == overlap_id
        assert j["next_id"] is None

    def test_storage_nearest_recording_day_skips_empty_days(self, app, client):
        import os
        from pathlib import Path
        import util as util_mod

        with app.app_context():
            tmp_root = Path(app.instance_path) / "storage-nearest-day-test"
            rec_root = tmp_root / "recordings"
            (rec_root / "2025" / "03" / "19" / "120000").mkdir(parents=True, exist_ok=True)
            (rec_root / "2025" / "03" / "22" / "130000").mkdir(parents=True, exist_ok=True)
            (rec_root / "2025" / "03" / "19" / "120000" / "video.mp4").write_bytes(b"x")
            (rec_root / "2025" / "03" / "22" / "130000" / "video.mp4").write_bytes(b"x")

            original_recordings_dir = util_mod.recordings_dir
            util_mod.recordings_dir = lambda: os.fspath(rec_root)
            try:
                prev_r = client.get(
                    "/api/ui/storage/nearest-recording-day",
                    query_string={"date": "2025-03-21", "direction": "prev"},
                )
                next_r = client.get(
                    "/api/ui/storage/nearest-recording-day",
                    query_string={"date": "2025-03-20", "direction": "next"},
                )
            finally:
                util_mod.recordings_dir = original_recordings_dir

        assert prev_r.status_code == 200
        assert prev_r.get_json() == {"date": "2025-03-19", "direction": "prev", "found": True}
        assert next_r.status_code == 200
        assert next_r.get_json() == {"date": "2025-03-22", "direction": "next", "found": True}

    def test_delete_video_requires_access(self, client):
        """Delete returns 403 without contributor/admin access when password is set."""
        r = client.delete("/api/ui/videos/1")
        # 403 if password required and no session; 404 if video not found; 200 if no password
        assert r.status_code in (200, 403, 404)

    def test_patch_video_favorite_updates_and_blocks_deleted(self, app, client):
        """PATCH favorite: toggles DB flag; 410 when deleted_at is set (FLASK_TESTING: open access)."""
        from datetime import datetime, timezone

        from app_config.app_config import app_config
        from models import Video, db

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")
        try:
            with app.app_context():
                v = Video(
                    processor_version="test",
                    start_time=datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
                    end_time=datetime(2025, 6, 1, 10, 0, 30, tzinfo=timezone.utc),
                    video_path="data/recordings/2025/06/01/100000/video.mp4",
                    favorite=False,
                )
                db.session.add(v)
                db.session.commit()
                vid = v.id

            r0 = client.patch(f"/api/ui/videos/{vid}", json={"favorite": True})
            assert r0.status_code == 200
            assert r0.get_json().get("favorite") is True

            with app.app_context():
                row = db.session.get(Video, vid)
                assert row is not None
                assert row.favorite is True
                row.favorite = False
                row.deleted_at = datetime.now(timezone.utc)
                db.session.commit()

            r1 = client.patch(f"/api/ui/videos/{vid}", json={"favorite": True})
            assert r1.status_code == 410
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)

    def test_patch_video_behavior_and_get_detail(self, app, client):
        """PATCH behavior_label/confidence; GET detail includes behavior_* (#416)."""
        from datetime import datetime, timezone

        from app_config.app_config import app_config
        from models import Video, db

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")
        try:
            with app.app_context():
                v = Video(
                    processor_version="test",
                    start_time=datetime(2025, 7, 1, 10, 0, 0, tzinfo=timezone.utc),
                    end_time=datetime(2025, 7, 1, 10, 0, 30, tzinfo=timezone.utc),
                    video_path="data/recordings/2025/07/01/100000/video.mp4",
                    favorite=False,
                )
                db.session.add(v)
                db.session.commit()
                vid = v.id

            rp = client.patch(
                f"/api/ui/videos/{vid}",
                json={"behavior_label": "feeding", "behavior_confidence": 0.82},
            )
            assert rp.status_code == 200
            body = rp.get_json()
            assert body.get("behavior_label") == "feeding"
            assert abs(float(body.get("behavior_confidence") or 0) - 0.82) < 1e-6

            rg = client.get(f"/api/ui/videos/{vid}")
            assert rg.status_code == 200
            detail = rg.get_json()
            assert detail.get("behavior_label") == "feeding"
            assert abs(float(detail.get("behavior_confidence") or 0) - 0.82) < 1e-6

            rc = client.patch(f"/api/ui/videos/{vid}", json={"behavior_label": ""})
            assert rc.status_code == 200
            cleared = rc.get_json()
            assert not cleared.get("behavior_label")
            assert cleared.get("behavior_confidence") in (None, 0, 0.0)

            rg2 = client.get(f"/api/ui/videos/{vid}")
            assert rg2.status_code == 200
            d2 = rg2.get_json()
            assert not d2.get("behavior_label")
            assert d2.get("behavior_confidence") in (None, 0, 0.0)
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)


class TestBirdfood:
    def test_birdfood_get_returns_list(self, client):
        r = client.get("/api/ui/birdfood")
        assert r.status_code == 200
        assert isinstance(r.json, list)


class TestSpecies:
    def test_species_returns_list(self, client):
        r = client.get("/api/ui/species")
        assert r.status_code == 200
        assert isinstance(r.json, list)

    def test_species_observed_returns_list(self, client):
        r = client.get("/api/ui/species/observed")
        assert r.status_code == 200
        assert isinstance(r.json, list)
        for item in r.json:
            assert "id" in item and "name" in item and "count" in item

    def test_species_track_regen_options_returns_list(self, client):
        r = client.get("/api/ui/species/track-regen-options")
        assert r.status_code == 200
        assert isinstance(r.json, list)
        for item in r.json:
            assert "id" in item and "name" in item and "count" in item


class TestCorrectionsHistory:
    def test_recent_corrections_endpoint_shape(self, client):
        r = client.get("/api/ui/corrections/recent", query_string={"limit": 5})
        assert r.status_code in (200, 403)
        if r.status_code == 200:
            assert isinstance(r.json, list)
            for row in r.json:
                assert "id" in row
                assert "created_at" in row
                assert "action" in row
                assert "source" in row
                assert "apply_scope" in row


class TestDetectionSpeciesPatch:
    def test_patch_default_single_track_only_one_row(self, app, client):
        """Без apply_scope обновляется одна строка (Unknowns / быстрый путь)."""
        from datetime import datetime

        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")
        try:
            with app.app_context():
                sp_a = Species(name="PatchOldBird")
                sp_b = Species(name="PatchNewBird")
                visit = SpeciesVisit(
                    species=sp_a,
                    start_time=datetime(2026, 4, 10, 12, 0, 0),
                    end_time=datetime(2026, 4, 10, 12, 0, 30),
                    max_simultaneous=2,
                )
                video = Video(
                    processor_version="test",
                    start_time=datetime(2026, 4, 10, 12, 0, 0),
                    end_time=datetime(2026, 4, 10, 12, 1, 0),
                    video_path="data/recordings/2026/04/10/120000/video.mp4",
                )
                d1 = VideoSpecies(
                    video=video,
                    species=sp_a,
                    species_visit=visit,
                    start_time=0.0,
                    end_time=5.0,
                    confidence=0.5,
                    source="video",
                    track_id=1,
                )
                d2 = VideoSpecies(
                    video=video,
                    species=sp_a,
                    species_visit=visit,
                    start_time=6.0,
                    end_time=10.0,
                    confidence=0.6,
                    source="video",
                    track_id=2,
                )
                db.session.add_all([sp_a, sp_b, visit, video, d1, d2])
                db.session.commit()
                d1_id, d2_id = d1.id, d2.id
                sp_a_id, sp_b_id = sp_a.id, sp_b.id

            r = client.patch(
                f"/api/ui/detections/{d1_id}",
                json={"species_id": sp_b_id, "source": "unknowns"},
            )
            assert r.status_code == 200
            assert r.json.get("updated_count") == 1
            assert r.json.get("apply_scope") == "single_track"

            with app.app_context():
                row1 = db.session.get(VideoSpecies, d1_id)
                row2 = db.session.get(VideoSpecies, d2_id)
                assert row1.species_id == sp_b_id
                assert row2.species_id == sp_a_id
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)

    def test_patch_video_source_defaults_legacy_fanout(self, app, client):
        """Без apply_scope при source=video — прежний fanout по старому виду на ролике."""
        from datetime import datetime

        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")
        try:
            with app.app_context():
                sp_a = Species(name="VideoFanOld")
                sp_b = Species(name="VideoFanNew")
                visit = SpeciesVisit(
                    species=sp_a,
                    start_time=datetime(2026, 4, 10, 12, 0, 0),
                    end_time=datetime(2026, 4, 10, 12, 0, 30),
                    max_simultaneous=2,
                )
                video = Video(
                    processor_version="test",
                    start_time=datetime(2026, 4, 10, 12, 0, 0),
                    end_time=datetime(2026, 4, 10, 12, 1, 0),
                    video_path="data/recordings/2026/04/10/120001/video2.mp4",
                )
                d1 = VideoSpecies(
                    video=video,
                    species=sp_a,
                    species_visit=visit,
                    start_time=0.0,
                    end_time=5.0,
                    confidence=0.5,
                    source="video",
                    track_id=1,
                )
                d2 = VideoSpecies(
                    video=video,
                    species=sp_a,
                    species_visit=visit,
                    start_time=6.0,
                    end_time=10.0,
                    confidence=0.6,
                    source="video",
                    track_id=2,
                )
                db.session.add_all([sp_a, sp_b, visit, video, d1, d2])
                db.session.commit()
                d1_id, d2_id = d1.id, d2.id
                sp_b_id = sp_b.id

            r = client.patch(
                f"/api/ui/detections/{d1_id}",
                json={"species_id": sp_b_id, "source": "video"},
            )
            assert r.status_code == 200
            assert r.json.get("updated_count") == 2
            assert r.json.get("apply_scope") == "legacy_fanout"

            with app.app_context():
                row1 = db.session.get(VideoSpecies, d1_id)
                row2 = db.session.get(VideoSpecies, d2_id)
                assert row1.species_id == sp_b_id
                assert row2.species_id == sp_b_id
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)


class TestBirdFamilies:
    def test_bird_families_returns_list(self, client):
        r = client.get("/api/ui/bird_families")
        # Пустая in-memory БД без категории «Birds» даёт 404 (см. ui_species_catalog_routes).
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(r.json, list)


class TestSettingsEndpoints:
    def test_settings_requires_password_returns_bool(self, client):
        r = client.get("/api/ui/settings/requires-password")
        assert r.status_code == 200
        assert "requires" in r.json
        assert isinstance(r.json["requires"], bool)

    def test_settings_check_access_returns_status(self, client):
        r = client.get("/api/ui/settings/check-access")
        assert r.status_code == 200
        assert "unlocked" in r.json
        assert r.json["unlocked"] in (True, False)


class TestStatusDebug:
    def test_status_debug_requires_access(self, client):
        from app_config.app_config import app_config

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        app_config.set("general.settings_password", "test-admin-password")
        app_config.set("general.contributor_password", "")
        try:
            r = client.get("/api/ui/status/debug")
            assert r.status_code == 403
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)

    def test_status_debug_returns_diagnostics_when_unlocked(self, client):
        with client.session_transaction() as sess:
            sess["access_role"] = "admin"
            sess["settings_unlocked"] = True
        r = client.get("/api/ui/status/debug")
        assert r.status_code == 200
        data = r.json
        assert "last_heartbeat" in data or "cutoff_utc" in data


class TestDatabaseBackupRestore:
    def test_db_backup_endpoint_exists(self, client):
        r = client.get("/api/ui/system/db/backup")
        # 200 when unlocked and file DB is available; 403 if locked; 404 for in-memory test DB.
        assert r.status_code in (200, 403, 404)
        if r.status_code == 200:
            cd = r.headers.get("Content-Disposition", "")
            assert "attachment" in cd.lower()
            assert ".db" in cd

    def test_db_restore_requires_file(self, client):
        r = client.post("/api/ui/system/db/restore", data={}, content_type="multipart/form-data")
        # 400 when endpoint reachable and file is missing; 403 if locked.
        assert r.status_code in (400, 403)
        if r.status_code == 400:
            assert "error" in r.json

    def test_sqlite_backup_helper_captures_live_database(self, tmp_path):
        from services.sqlite_admin_service import backup_sqlite_to_file as _sqlite_backup_to_file

        live_db = tmp_path / "live.db"
        snapshot_db = tmp_path / "snapshot.db"

        with sqlite3.connect(live_db) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE sample (value TEXT)")
            conn.execute("INSERT INTO sample(value) VALUES (?)", ("from-live-db",))
            conn.commit()

        _sqlite_backup_to_file(str(live_db), str(snapshot_db))

        with sqlite3.connect(snapshot_db) as conn:
            row = conn.execute("SELECT value FROM sample").fetchone()
        assert row == ("from-live-db",)

    def test_sqlite_replace_live_db_swaps_file_and_removes_sidecars(self, tmp_path):
        from services.sqlite_admin_service import replace_live_sqlite_db as _sqlite_replace_live_db

        live_db = tmp_path / "live.db"
        restored_db = tmp_path / "restored.db"
        wal_path = tmp_path / "live.db-wal"
        shm_path = tmp_path / "live.db-shm"

        with sqlite3.connect(live_db) as conn:
            conn.execute("CREATE TABLE sample (value TEXT)")
            conn.execute("INSERT INTO sample(value) VALUES (?)", ("old-value",))
            conn.commit()

        with sqlite3.connect(restored_db) as conn:
            conn.execute("CREATE TABLE sample (value TEXT)")
            conn.execute("INSERT INTO sample(value) VALUES (?)", ("new-value",))
            conn.commit()

        wal_path.write_bytes(b"legacy wal")
        shm_path.write_bytes(b"legacy shm")

        _sqlite_replace_live_db(str(live_db), str(restored_db))

        with sqlite3.connect(live_db) as conn:
            row = conn.execute("SELECT value FROM sample").fetchone()
        assert row == ("new-value",)
        assert wal_path.exists() is False
        assert shm_path.exists() is False


class TestStoragePurge:
    def test_purge_storage_deletes_db_rows_and_files(self, app, client, tmp_path, monkeypatch):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        import util as util_mod

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")

        recordings_root = tmp_path / "app" / "data" / "recordings"
        clip_dir = recordings_root / "2026" / "03" / "26" / "031309"
        clip_dir.mkdir(parents=True, exist_ok=True)
        (clip_dir / "video.mp4").write_bytes(b"video-bytes")
        monkeypatch.setattr(util_mod, "recordings_dir", lambda: str(recordings_root))

        try:
            with app.app_context():
                species = Species(name="Eurasian Jay")
                visit = SpeciesVisit(
                    species=species,
                    start_time=datetime(2026, 3, 26, 3, 13, 9),
                    end_time=datetime(2026, 3, 26, 3, 13, 21),
                    max_simultaneous=1,
                )
                video = Video(
                    processor_version="test",
                    start_time=datetime(2026, 3, 26, 3, 13, 9),
                    end_time=datetime(2026, 3, 26, 3, 13, 39),
                    video_path="data/recordings/2026/03/26/031309/video.mp4",
                )
                detection = VideoSpecies(
                    video=video,
                    species=species,
                    species_visit=visit,
                    start_time=0.0,
                    end_time=12.0,
                    confidence=0.91,
                    source="video",
                )
                db.session.add_all([species, visit, video, detection])
                db.session.commit()

            response = client.post("/api/ui/storage/purge", json={"date": "2026-03-26"})
            assert response.status_code == 200

            with app.app_context():
                assert Video.query.count() == 0
                assert VideoSpecies.query.count() == 0
                assert SpeciesVisit.query.count() == 0

            assert not clip_dir.exists()
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)

    def test_purge_storage_skips_favorite_when_protect_favorites_enabled(self, app, client, tmp_path, monkeypatch):
        """Ручной purge не удаляет избранные ролики и каталог сессии при protect_favorites."""
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        import util as util_mod

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        old_prot = app_config.get("retention.protect_favorites", True)
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")
        app_config.set("retention.protect_favorites", True)

        recordings_root = tmp_path / "app" / "data" / "recordings"
        clip_nf = recordings_root / "2026" / "03" / "26" / "031309"
        clip_f = recordings_root / "2026" / "03" / "26" / "031310"
        clip_nf.mkdir(parents=True, exist_ok=True)
        clip_f.mkdir(parents=True, exist_ok=True)
        (clip_nf / "video.mp4").write_bytes(b"nf-bytes")
        (clip_f / "video.mp4").write_bytes(b"fav-bytes")
        monkeypatch.setattr(util_mod, "recordings_dir", lambda: str(recordings_root))

        try:
            with app.app_context():
                species = Species(name="Purge Fav Bird")
                visit_nf = SpeciesVisit(
                    species=species,
                    start_time=datetime(2026, 3, 26, 3, 13, 9),
                    end_time=datetime(2026, 3, 26, 3, 13, 21),
                    max_simultaneous=1,
                )
                visit_f = SpeciesVisit(
                    species=species,
                    start_time=datetime(2026, 3, 26, 4, 0, 0),
                    end_time=datetime(2026, 3, 26, 4, 0, 30),
                    max_simultaneous=1,
                )
                video_nf = Video(
                    processor_version="test",
                    start_time=datetime(2026, 3, 26, 3, 13, 9),
                    end_time=datetime(2026, 3, 26, 3, 13, 39),
                    favorite=False,
                    video_path="data/recordings/2026/03/26/031309/video.mp4",
                )
                video_f = Video(
                    processor_version="test",
                    start_time=datetime(2026, 3, 26, 4, 0, 0),
                    end_time=datetime(2026, 3, 26, 4, 0, 30),
                    favorite=True,
                    video_path="data/recordings/2026/03/26/031310/video.mp4",
                )
                db.session.add_all([species, visit_nf, visit_f, video_nf, video_f])
                db.session.flush()
                db.session.add_all(
                    [
                        VideoSpecies(
                            video=video_nf,
                            species=species,
                            species_visit=visit_nf,
                            start_time=0.0,
                            end_time=12.0,
                            confidence=0.91,
                            source="video",
                        ),
                        VideoSpecies(
                            video=video_f,
                            species=species,
                            species_visit=visit_f,
                            start_time=0.0,
                            end_time=12.0,
                            confidence=0.92,
                            source="video",
                        ),
                    ]
                )
                db.session.commit()

            response = client.post("/api/ui/storage/purge", json={"date": "2026-03-26"})
            assert response.status_code == 200

            with app.app_context():
                assert Video.query.count() == 1
                remaining = Video.query.one()
                assert remaining.favorite is True
                assert VideoSpecies.query.count() == 1
                assert SpeciesVisit.query.count() == 1

            assert not clip_nf.exists()
            assert clip_f.exists()
            assert (clip_f / "video.mp4").read_bytes() == b"fav-bytes"
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)
            app_config.set("retention.protect_favorites", old_prot)

    def test_purge_storage_skips_non_favorite_in_session_with_favorite(self, app, client, tmp_path, monkeypatch):
        """Один каталог сессии с избранным: соседний ролик не трогается (ни БД, ни файлы)."""
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        import util as util_mod

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        old_prot = app_config.get("retention.protect_favorites", True)
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")
        app_config.set("retention.protect_favorites", True)

        recordings_root = tmp_path / "app" / "data" / "recordings"
        sess = recordings_root / "2026" / "03" / "26" / "031309"
        sess.mkdir(parents=True, exist_ok=True)
        (sess / "video.mp4").write_bytes(b"fav-bytes")
        (sess / "other.mp4").write_bytes(b"nf-bytes")
        monkeypatch.setattr(util_mod, "recordings_dir", lambda: str(recordings_root))

        try:
            with app.app_context():
                species = Species(name="Shared Session Bird")
                visit_f = SpeciesVisit(
                    species=species,
                    start_time=datetime(2026, 3, 26, 3, 13, 9),
                    end_time=datetime(2026, 3, 26, 3, 13, 21),
                    max_simultaneous=1,
                )
                visit_nf = SpeciesVisit(
                    species=species,
                    start_time=datetime(2026, 3, 26, 3, 14, 0),
                    end_time=datetime(2026, 3, 26, 3, 14, 20),
                    max_simultaneous=1,
                )
                video_f = Video(
                    processor_version="test",
                    start_time=datetime(2026, 3, 26, 3, 13, 9),
                    end_time=datetime(2026, 3, 26, 3, 13, 39),
                    favorite=True,
                    video_path="data/recordings/2026/03/26/031309/video.mp4",
                )
                video_nf = Video(
                    processor_version="test",
                    start_time=datetime(2026, 3, 26, 3, 14, 0),
                    end_time=datetime(2026, 3, 26, 3, 14, 15),
                    favorite=False,
                    video_path="data/recordings/2026/03/26/031309/other.mp4",
                )
                db.session.add_all([species, visit_f, visit_nf, video_f, video_nf])
                db.session.flush()
                db.session.add_all(
                    [
                        VideoSpecies(
                            video=video_f,
                            species=species,
                            species_visit=visit_f,
                            start_time=0.0,
                            end_time=12.0,
                            confidence=0.91,
                            source="video",
                        ),
                        VideoSpecies(
                            video=video_nf,
                            species=species,
                            species_visit=visit_nf,
                            start_time=0.0,
                            end_time=12.0,
                            confidence=0.9,
                            source="video",
                        ),
                    ]
                )
                db.session.commit()

            response = client.post("/api/ui/storage/purge", json={"date": "2026-03-26"})
            assert response.status_code == 200

            with app.app_context():
                assert Video.query.count() == 2
                assert sum(1 for v in Video.query.all() if v.favorite) == 1

            assert sess.exists()
            assert (sess / "video.mp4").exists()
            assert (sess / "video.mp4").read_bytes() == b"fav-bytes"
            assert (sess / "other.mp4").exists()
            assert (sess / "other.mp4").read_bytes() == b"nf-bytes"
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)
            app_config.set("retention.protect_favorites", old_prot)

    def test_purge_storage_range_deletes_only_in_range(self, app, client, tmp_path, monkeypatch):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, Video, VideoSpecies, db
        import util as util_mod

        old_admin = app_config.get("general.settings_password")
        old_contrib = app_config.get("general.contributor_password")
        app_config.set("general.settings_password", "")
        app_config.set("general.contributor_password", "")

        recordings_root = tmp_path / "app" / "data" / "recordings"
        for day in ("25", "26", "27"):
            clip = recordings_root / "2026" / "03" / day / "120000"
            clip.mkdir(parents=True, exist_ok=True)
            (clip / "video.mp4").write_bytes(b"v")
        monkeypatch.setattr(util_mod, "recordings_dir", lambda: str(recordings_root))

        try:
            with app.app_context():
                species = Species(name="Range Test Bird")
                db.session.add(species)
                db.session.flush()
                for start_d, suf in (
                    (25, "25/120000/video.mp4"),
                    (26, "26/120000/video.mp4"),
                    (27, "27/120000/video.mp4"),
                ):
                    st = datetime(2026, 3, start_d, 12, 0, 0)
                    et = datetime(2026, 3, start_d, 12, 0, 30)
                    visit = SpeciesVisit(
                        species=species,
                        start_time=st,
                        end_time=et,
                        max_simultaneous=1,
                    )
                    video = Video(
                        processor_version="test",
                        start_time=st,
                        end_time=et,
                        video_path=f"data/recordings/2026/03/{suf}",
                    )
                    detection = VideoSpecies(
                        video=video,
                        species=species,
                        species_visit=visit,
                        start_time=0.0,
                        end_time=1.0,
                        confidence=0.9,
                        source="video",
                    )
                    db.session.add_all([visit, video, detection])
                db.session.commit()

            response = client.post(
                "/api/ui/storage/purge",
                json={"start_date": "2026-03-26", "end_date": "2026-03-26"},
            )
            assert response.status_code == 200

            with app.app_context():
                assert Video.query.count() == 2
                remaining_days = {v.start_time.day for v in Video.query.all()}
                assert remaining_days == {25, 27}

            assert (recordings_root / "2026" / "03" / "25" / "120000").exists()
            assert not (recordings_root / "2026" / "03" / "26" / "120000").exists()
            assert (recordings_root / "2026" / "03" / "27" / "120000").exists()
        finally:
            app_config.set("general.settings_password", old_admin)
            app_config.set("general.contributor_password", old_contrib)


class TestRetentionFavoriteSession:
    def test_retention_cascade_skips_coworker_in_favorite_session(self, app, tmp_path, monkeypatch):
        """Cascade retention: рядом с избранным в той же сессии неизбранный ролик и файлы не трогаются."""
        from app_config.app_config import app_config
        from models import Species, Video, db
        from services.retention_service import run_retention
        import util as util_mod

        old_days = app_config.get("retention.days")
        old_mode = app_config.get("retention.mode")
        old_max = app_config.get("retention.max_gb")
        old_prot = app_config.get("retention.protect_favorites", True)
        app_config.set("retention.days", 1)
        app_config.set("retention.max_gb", None)
        app_config.set("retention.mode", "cascade")
        app_config.set("retention.protect_favorites", True)

        recordings_root = tmp_path / "app" / "data" / "recordings"
        sess = recordings_root / "2020" / "01" / "01" / "120000"
        sess.mkdir(parents=True, exist_ok=True)
        (sess / "video.mp4").write_bytes(b"a")
        (sess / "other.mp4").write_bytes(b"b")
        monkeypatch.setattr(util_mod, "recordings_dir", lambda: str(recordings_root))

        try:
            with app.app_context():
                sp = Species(name="RetFavSess")
                db.session.add(sp)
                db.session.flush()
                vf = Video(
                    processor_version="test",
                    start_time=datetime(2020, 1, 1, 12, 0, 0),
                    end_time=datetime(2020, 1, 1, 12, 0, 30),
                    favorite=True,
                    video_path="data/recordings/2020/01/01/120000/video.mp4",
                )
                vnf = Video(
                    processor_version="test",
                    start_time=datetime(2020, 1, 1, 12, 1, 0),
                    end_time=datetime(2020, 1, 1, 12, 1, 30),
                    favorite=False,
                    video_path="data/recordings/2020/01/01/120000/other.mp4",
                )
                db.session.add_all([vf, vnf])
                db.session.commit()

                run_retention(dry_run=False, mode="cascade")

                assert Video.query.count() == 2
            assert (sess / "video.mp4").exists()
            assert (sess / "other.mp4").exists()
        finally:
            app_config.set("retention.days", old_days)
            app_config.set("retention.mode", old_mode)
            app_config.set("retention.max_gb", old_max)
            app_config.set("retention.protect_favorites", old_prot)


class TestReportPdf:
    def test_report_requires_params(self, client):
        r = client.get("/api/ui/report/pdf")
        assert r.status_code == 400
        assert "error" in r.json

    def test_report_month_returns_pdf(self, client):
        r = client.get("/api/ui/report/pdf", query_string={"month": "2026-03"})
        assert r.status_code == 200
        assert "application/pdf" in (r.content_type or "")
        assert r.data[:4] == b"%PDF"

    def test_report_rejects_invalid_month(self, client):
        r = client.get("/api/ui/report/pdf", query_string={"month": "invalid"})
        assert r.status_code == 400


class TestSpeciesRegionalScope:
    def test_species_list_includes_regional_scope_boolean(self, client):
        r = client.get("/api/ui/species")
        assert r.status_code == 200
        data = r.json
        assert isinstance(data, list)
        for row in data[:5]:
            assert "regional_scope" in row
            assert isinstance(row["regional_scope"], bool)

    def test_regional_scope_true_for_birdnet_detection(self, app, client):
        from datetime import datetime, timezone
        from models import Species, Video, VideoSpecies, db

        vid = sid = pid = None
        with app.app_context():
            parent = Species(name="Test Parent Finch Regional", parent_id=None, active=True)
            db.session.add(parent)
            db.session.flush()
            pid = parent.id
            sp = Species(name="Test Leaf Finch Regional", parent_id=parent.id, active=True)
            db.session.add(sp)
            db.session.flush()
            sid = sp.id
            v = Video(
                processor_version="test",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                video_path="contract/test_clip.mp4",
            )
            db.session.add(v)
            db.session.flush()
            vid = v.id
            db.session.add(
                VideoSpecies(
                    video_id=v.id,
                    species_id=sp.id,
                    start_time=0.0,
                    end_time=1.0,
                    confidence=0.95,
                    source="audio",
                    detection_provider="birdnet_mqtt",
                )
            )
            db.session.commit()

        try:
            # Прямой commit в БД минует processor — сбросить TTL-кэш списка видов
            from services.http_response_cache import bust_response_caches

            bust_response_caches()

            r = client.get("/api/ui/species", query_string={"scope": "all"})
            assert r.status_code == 200
            row = next((x for x in r.json if x["id"] == sid), None)
            assert row is not None
            assert row["regional_scope"] is True
        finally:
            with app.app_context():
                if vid is not None:
                    VideoSpecies.query.filter_by(video_id=vid).delete()
                    Video.query.filter_by(id=vid).delete()
                if sid is not None:
                    Species.query.filter_by(id=sid).delete()
                if pid is not None:
                    Species.query.filter_by(id=pid).delete()
                db.session.commit()


class TestSpeciesXenoCanto:
    def test_xeno_canto_404_for_unknown_species(self, client):
        r = client.get("/api/ui/species/999999/xeno-canto")
        assert r.status_code == 404

    def test_xeno_canto_returns_recordings_or_empty(self, client, monkeypatch):
        # Depends on seed data - get first species from /species; no real Xeno-canto HTTP.
        from routes import ui_species_media_routes

        fake = [
            {
                "id": "1",
                "file": "https://xeno-canto.org/1/test.mp3",
                "en": "song",
                "type": "call",
                "rec": "r",
                "cnt": "c",
            }
        ]
        monkeypatch.setattr(ui_species_media_routes, "fetch_recordings", lambda species_name, limit=5: fake)

        species_r = client.get("/api/ui/species")
        assert species_r.status_code == 200
        species_list = species_r.json
        if species_list:
            sid = species_list[0]["id"]
            r = client.get(f"/api/ui/species/{sid}/xeno-canto")
            assert r.status_code == 200
            assert "recordings" in r.json
            assert "species_name" in r.json
            assert "xeno_canto_search_url" in r.json
            assert isinstance(r.json["recordings"], list)
            assert r.json["recordings"] == fake


class TestPush:
    """Web Push endpoints."""

    def test_push_vapid_returns_key_or_503(self, client):
        """vapid-public returns key when py-vapid available, else 503."""
        r = client.get("/api/ui/push/vapid-public")
        if r.status_code == 200:
            assert "vapid_public_key" in r.json
        else:
            assert r.status_code == 503
            assert "error" in r.json

    def test_push_subscribe_rejects_empty_or_invalid(self, client, monkeypatch):
        """Subscribe returns 400 when notifications disabled or payload invalid."""
        from app_config.app_config import app_config

        general = dict(app_config.config.get("general") or {})
        general["settings_password"] = ""
        general["contributor_password"] = ""
        monkeypatch.setitem(app_config.config, "general", general)
        r = client.post(
            "/api/ui/push/subscribe",
            json={},
            content_type="application/json",
        )
        assert r.status_code == 400
        err = r.json.get("error", "").lower()
        assert "notifications" in err or "subscription" in err

    def test_push_subscribe_requires_keys(self, client, monkeypatch):
        from app_config.app_config import app_config

        general = dict(app_config.config.get("general") or {})
        general["settings_password"] = ""
        general["contributor_password"] = ""
        monkeypatch.setitem(app_config.config, "general", general)
        r = client.post(
            "/api/ui/push/subscribe",
            json={"subscription": {"endpoint": "https://example.com/push"}},
            content_type="application/json",
        )
        assert r.status_code == 400


class TestMigrationCalendar:
    """Migration calendar: species activity by month."""

    def test_migration_calendar_returns_200(self, client):
        r = client.get("/api/ui/migration-calendar")
        assert r.status_code == 200
        data = r.json
        assert "species" in data
        assert "month_labels" in data
        assert isinstance(data["species"], list)
        assert data["month_labels"] == [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]

    def test_migration_calendar_species_structure(self, client):
        r = client.get("/api/ui/migration-calendar")
        assert r.status_code == 200
        species = r.json["species"]
        for item in species:
            assert "id" in item and "name" in item
            assert "monthly_counts" in item
            assert len(item["monthly_counts"]) == 12
            assert "total" in item
            assert item["total"] == sum(item["monthly_counts"])

    def test_migration_calendar_filter_by_year(self, client):
        r = client.get("/api/ui/migration-calendar", query_string={"start_year": 2024, "end_year": 2025})
        assert r.status_code == 200
        assert "species" in r.json
        assert "month_labels" in r.json

    def test_migration_calendar_filter_by_date(self, client):
        r = client.get(
            "/api/ui/migration-calendar",
            query_string={"start_date": "2024-01-01", "end_date": "2025-12-31"},
        )
        assert r.status_code == 200
        assert "species" in r.json
        assert "month_labels" in r.json

    def test_migration_calendar_rejects_invalid_start_date(self, client):
        r = client.get("/api/ui/migration-calendar", query_string={"start_date": "2024/01/01"})
        assert r.status_code == 400
        assert "error" in r.json

    def test_migration_calendar_rejects_reversed_date_range(self, client):
        r = client.get(
            "/api/ui/migration-calendar",
            query_string={"start_date": "2025-01-01", "end_date": "2024-01-01"},
        )
        assert r.status_code == 400
        assert "error" in r.json

    def test_migration_calendar_catalog_full_and_evidence_video(self, client):
        r = client.get(
            "/api/ui/migration-calendar",
            query_string={"catalog": "full", "evidence": "video"},
        )
        assert r.status_code == 200
        assert "species" in r.json

    def test_migration_calendar_evidence_param_ignored(self, app, client):
        from models import db, Species, SpeciesVisit, VideoSpecies

        with app.app_context():
            camera_species = Species(name="Camera only species")
            birdnet_species = Species(name="BirdNET only species")
            db.session.add_all([camera_species, birdnet_species])
            db.session.flush()

            visit_camera = SpeciesVisit(
                species_id=camera_species.id,
                start_time=datetime(2025, 3, 1, 10, 0, 0),
                end_time=datetime(2025, 3, 1, 10, 1, 0),
                max_simultaneous=1,
            )
            visit_birdnet = SpeciesVisit(
                species_id=birdnet_species.id,
                start_time=datetime(2025, 3, 2, 10, 0, 0),
                end_time=datetime(2025, 3, 2, 10, 1, 0),
                max_simultaneous=1,
            )
            db.session.add_all([visit_camera, visit_birdnet])
            db.session.flush()

            db.session.add(
                VideoSpecies(
                    video_id=1,
                    species_id=camera_species.id,
                    species_visit_id=visit_camera.id,
                    start_time=0,
                    end_time=1,
                    confidence=0.99,
                    source="video",
                    detection_provider="yolo",
                )
            )
            db.session.add(
                VideoSpecies(
                    video_id=2,
                    species_id=birdnet_species.id,
                    species_visit_id=visit_birdnet.id,
                    start_time=0,
                    end_time=1,
                    confidence=0.99,
                    source="audio",
                    detection_provider="birdnet_mqtt",
                )
            )
            db.session.commit()

        r_camera = client.get("/api/ui/migration-calendar", query_string={"evidence": "camera"})
        r_birdnet = client.get("/api/ui/migration-calendar", query_string={"evidence": "birdnet"})
        assert r_camera.status_code == 200
        assert r_birdnet.status_code == 200
        assert r_camera.json == r_birdnet.json

    def test_migration_calendar_rejects_bad_catalog(self, client):
        r = client.get("/api/ui/migration-calendar", query_string={"catalog": "maybe"})
        assert r.status_code == 400

    def test_migration_calendar_accepts_catalog_all_alias(self, client):
        r = client.get("/api/ui/migration-calendar", query_string={"catalog": "all"})
        assert r.status_code == 200
        assert r.json.get("catalog") == "full_eu"

    def test_migration_calendar_rejects_bad_metric(self, client):
        r = client.get("/api/ui/migration-calendar", query_string={"metric": "events"})
        assert r.status_code == 400
        assert "metric" in (r.json or {}).get("error", "")

    def test_migration_calendar_default_metric_is_encounters(self, app, client, monkeypatch):
        from models import db, Species, SpeciesVisit
        import services.migration_calendar_service as mc_service

        monkeypatch.setattr(mc_service, "species_ids_to_exclude_from_bird_catalog", lambda _s: set())

        with app.app_context():
            species = Species(name="Default metric species")
            db.session.add(species)
            db.session.flush()
            db.session.add(
                SpeciesVisit(
                    species_id=species.id,
                    start_time=datetime(2025, 4, 2, 10, 0, 0),
                    end_time=datetime(2025, 4, 2, 10, 10, 0),
                    max_simultaneous=3,
                )
            )
            db.session.commit()

        r = client.get("/api/ui/migration-calendar", query_string={"catalog": "observed"})
        assert r.status_code == 200
        assert r.json.get("metric_used") == "encounters"

        for row in r.json.get("species", []):
            if row.get("name") == "Default metric species":
                assert int(row.get("total") or 0) == 1
                break
        else:
            raise AssertionError("Default metric species not found")

    def test_migration_calendar_metric_switch(self, app, client, monkeypatch):
        from models import db, Species, SpeciesVisit
        import services.migration_calendar_service as mc_service

        monkeypatch.setattr(mc_service, "species_ids_to_exclude_from_bird_catalog", lambda _s: set())

        with app.app_context():
            species = Species(name="Metric switch species")
            db.session.add(species)
            db.session.flush()
            db.session.add(
                SpeciesVisit(
                    species_id=species.id,
                    start_time=datetime(2025, 4, 1, 10, 0, 0),
                    end_time=datetime(2025, 4, 1, 10, 10, 0),
                    max_simultaneous=4,
                )
            )
            db.session.commit()

        r_visits = client.get(
            "/api/ui/migration-calendar",
            query_string={"metric": "visits", "catalog": "observed"},
        )
        r_max = client.get(
            "/api/ui/migration-calendar",
            query_string={"metric": "max_simultaneous", "catalog": "observed"},
        )
        assert r_visits.status_code == 200
        assert r_max.status_code == 200
        assert r_visits.json.get("metric_used") == "visits"
        assert r_max.json.get("metric_used") == "max_simultaneous"

        def _find_total(payload):
            for row in payload.get("species", []):
                if row.get("name") == "Metric switch species":
                    return int(row.get("total") or 0)
            return 0

        assert _find_total(r_visits.json) == 1
        assert _find_total(r_max.json) == 4

    def test_migration_calendar_compare_endpoint(self, app, client, monkeypatch):
        from models import db, Species, SpeciesVisit
        import services.migration_calendar_service as mc_service

        monkeypatch.setattr(mc_service, "species_ids_to_exclude_from_bird_catalog", lambda _s: set())

        with app.app_context():
            species = Species(name="Compare metric species")
            db.session.add(species)
            db.session.flush()
            db.session.add(
                SpeciesVisit(
                    species_id=species.id,
                    start_time=datetime(2025, 5, 1, 9, 0, 0),
                    end_time=datetime(2025, 5, 1, 9, 5, 0),
                    max_simultaneous=4,
                )
            )
            db.session.commit()

        r = client.get("/api/ui/migration-calendar/compare", query_string={"catalog": "observed"})
        assert r.status_code == 200
        totals = (r.json or {}).get("totals") or {}
        assert int(totals.get("encounters") or 0) >= 1
        assert int(totals.get("max_simultaneous") or 0) >= 4
        assert int(totals.get("delta") or 0) >= 3
        target = None
        for row in (r.json or {}).get("species", []):
            if row.get("name") == "Compare metric species":
                target = row
                break
        assert target is not None
        assert int(target.get("encounters_total") or 0) == 1
        assert int(target.get("max_simultaneous_total") or 0) == 4
        assert int(target.get("delta") or 0) == 3


class TestUnknowns:
    def test_unknowns_requires_params(self, client):
        r = client.get("/api/ui/unknowns")
        assert r.status_code == 400
        assert "error" in r.json

    def test_unknowns_returns_list(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get("/api/ui/unknowns", query_string={"start_time": ts - 86400, "end_time": ts})
        assert r.status_code == 200
        assert isinstance(r.json, list)

    def test_unknowns_rejects_interval_over_one_day(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get("/api/ui/unknowns", query_string={"start_time": ts - 86400 * 2, "end_time": ts})
        assert r.status_code == 400

    def test_unknowns_limit_is_capped(self, client):
        ts = int(datetime.now(timezone.utc).timestamp())
        r = client.get(
            "/api/ui/unknowns",
            query_string={
                "start_time": ts - 86400,
                "end_time": ts,
                "limit": 999999,
            },
        )
        assert r.status_code == 200
        assert isinstance(r.json, list)
        assert len(r.json) <= 500

    def test_unknowns_excludes_legacy_import_placeholders(self, app, client):
        from models import db, Species, SpeciesVisit, Video, VideoSpecies

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with app.app_context():
            unknown = Species.query.filter_by(name="Unknown").first()
            if unknown is None:
                unknown = Species(name="Unknown", active=False)
                db.session.add(unknown)
                db.session.flush()

            video = Video(
                processor_version="1",
                start_time=now,
                end_time=now + timedelta(seconds=30),
                video_path="data/recordings/2026/03/30/120000/video.mp4",
                spectrogram_path=None,
            )
            db.session.add(video)
            db.session.flush()

            visit = SpeciesVisit(
                species_id=unknown.id,
                start_time=now,
                end_time=now + timedelta(seconds=30),
                max_simultaneous=1,
            )
            db.session.add(visit)
            db.session.flush()

            db.session.add(
                VideoSpecies(
                    video_id=video.id,
                    species_id=unknown.id,
                    species_visit_id=visit.id,
                    start_time=0,
                    end_time=30,
                    confidence=0,
                    source="video",
                    detection_provider="legacy",
                    created_at=now,
                )
            )
            db.session.commit()

        ts = int(now.replace(tzinfo=timezone.utc).timestamp())
        r = client.get(
            "/api/ui/unknowns",
            query_string={"start_time": ts - 60, "end_time": ts + 60},
        )
        assert r.status_code == 200
        assert r.json == []

    def test_unknowns_include_clip_that_overlaps_window(self, app, client):
        from models import db, Species, SpeciesVisit, Video, VideoSpecies

        with app.app_context():
            unknown = Species.query.filter_by(name="Unknown").first()
            if unknown is None:
                unknown = Species(name="Unknown", active=False)
                db.session.add(unknown)
                db.session.flush()

            video = Video(
                processor_version="1",
                start_time=datetime(2026, 3, 24, 23, 59, 50),
                end_time=datetime(2026, 3, 25, 0, 0, 20),
                video_path="data/recordings/2026/03/24/235950/video.mp4",
                spectrogram_path=None,
            )
            visit = SpeciesVisit(
                species_id=unknown.id,
                start_time=video.start_time,
                end_time=video.end_time,
                max_simultaneous=1,
            )
            db.session.add_all([video, visit])
            db.session.flush()
            detection = VideoSpecies(
                video_id=video.id,
                species_id=unknown.id,
                species_visit_id=visit.id,
                start_time=12.0,
                end_time=18.0,
                confidence=0.1,
                source="video",
                detection_provider="yolo",
                created_at=datetime(2026, 3, 25, 0, 0, 5),
            )
            db.session.add(detection)
            db.session.commit()
            detection_id = detection.id

        response = client.get(
            "/api/ui/unknowns",
            query_string={"date": "2026-03-25", "time_of_day": "all"},
        )

        assert response.status_code == 200
        assert any(row["id"] == detection_id for row in response.get_json())


class TestScanRecordings:
    def test_scan_import_avoids_new_legacy_unknowns_and_cleans_old_ones(
        self,
        app,
        client,
        monkeypatch,
        tmp_path,
    ):
        from app_config.app_config import app_config
        from models import db, Species, SpeciesVisit, Video, VideoSpecies

        general = dict(app_config.config.get("general") or {})
        general["settings_password"] = ""
        general["contributor_password"] = ""
        monkeypatch.setitem(app_config.config, "general", general)

        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        rec_dir = tmp_path / "recordings" / "2026" / "03" / "30" / "131825"
        rec_dir.mkdir(parents=True)
        (rec_dir / "video.mp4").write_bytes(b"fake-video")

        now = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc).replace(
            tzinfo=None,
        )
        with app.app_context():
            unknown = Species.query.filter_by(name="Unknown").first()
            if unknown is None:
                unknown = Species(name="Unknown", active=False)
                db.session.add(unknown)
                db.session.flush()

            old_video = Video(
                processor_version="1",
                start_time=now,
                end_time=now + timedelta(seconds=30),
                video_path="data/recordings/2026/03/29/120000/video.mp4",
                spectrogram_path=None,
            )
            db.session.add(old_video)
            db.session.flush()

            old_visit = SpeciesVisit(
                species_id=unknown.id,
                start_time=now,
                end_time=now + timedelta(seconds=30),
                max_simultaneous=1,
            )
            db.session.add(old_visit)
            db.session.flush()

            db.session.add(
                VideoSpecies(
                    video_id=old_video.id,
                    species_id=unknown.id,
                    species_visit_id=old_visit.id,
                    start_time=0,
                    end_time=30,
                    confidence=0,
                    source="video",
                    detection_provider="legacy",
                    created_at=now,
                )
            )
            db.session.commit()

        response = client.post("/api/ui/system/recordings/scan")
        assert response.status_code == 200
        assert response.json["imported"] == 1
        assert response.json["cleaned_legacy_placeholders"] == 1

        with app.app_context():
            paths = {row.video_path for row in Video.query.all()}
            assert "data/recordings/2026/03/30/131825/video.mp4" in paths
            assert VideoSpecies.query.count() == 0
            assert SpeciesVisit.query.count() == 0


class TestVerifyPasswordRateLimit:
    """POST /api/ui/settings/verify-password — brute-force throttle (issue #46)."""

    @pytest.fixture(autouse=True)
    def _clear_buckets(self, client):
        """Depends on ``client`` so the app loads before touching rate-limit state."""
        import auth as auth_mod

        with auth_mod._verify_password_lock:
            auth_mod._verify_password_attempts.clear()
        yield
        with auth_mod._verify_password_lock:
            auth_mod._verify_password_attempts.clear()

    def test_five_wrong_then_429(self, client, monkeypatch):
        from app_config.app_config import app_config

        general = dict(app_config.config.get("general") or {})
        general["settings_password"] = "correct-horse-battery-staple"
        monkeypatch.setitem(app_config.config, "general", general)

        for _ in range(5):
            r = client.post(
                "/api/ui/settings/verify-password",
                json={"password": "wrong"},
            )
            assert r.status_code == 401
        r = client.post(
            "/api/ui/settings/verify-password",
            json={"password": "wrong"},
        )
        assert r.status_code == 429
        assert r.json.get("error")
        import auth as auth_mod

        assert r.headers.get("Retry-After") == str(auth_mod.VERIFY_PASSWORD_WINDOW)

    def test_success_clears_counter(self, client, monkeypatch):
        from app_config.app_config import app_config

        general = dict(app_config.config.get("general") or {})
        general["settings_password"] = "good-secret"
        monkeypatch.setitem(app_config.config, "general", general)

        for _ in range(4):
            client.post("/api/ui/settings/verify-password", json={"password": "nope"})
        r_ok = client.post(
            "/api/ui/settings/verify-password",
            json={"password": "good-secret"},
        )
        assert r_ok.status_code == 200
        for _ in range(5):
            r = client.post(
                "/api/ui/settings/verify-password",
                json={"password": "x"},
            )
            assert r.status_code == 401
        assert (
            client.post(
                "/api/ui/settings/verify-password",
                json={"password": "x"},
            ).status_code
            == 429
        )

    def test_x_real_ip_separate_buckets(self, client, monkeypatch):
        """За доверенным прокси разные X-Real-IP — разные бакеты (см. TRUSTED_PROXY)."""
        monkeypatch.setenv("TRUSTED_PROXY", "1")
        from app_config.app_config import app_config

        general = dict(app_config.config.get("general") or {})
        general["settings_password"] = "s"
        monkeypatch.setitem(app_config.config, "general", general)

        for _ in range(5):
            client.post(
                "/api/ui/settings/verify-password",
                json={"password": "bad"},
                headers={"X-Real-IP": "198.51.100.22"},
            )
        assert (
            client.post(
                "/api/ui/settings/verify-password",
                json={"password": "bad"},
                headers={"X-Real-IP": "198.51.100.22"},
            ).status_code
            == 429
        )
        r = client.post(
            "/api/ui/settings/verify-password",
            json={"password": "bad"},
            headers={"X-Real-IP": "198.51.100.33"},
        )
        assert r.status_code == 401


class TestConfigAudit:
    def test_config_audit_ignores_valid_dynamic_and_schema_keys(self, client, tmp_path, monkeypatch):
        import yaml
        from app_config.app_config import app_config

        user_cfg = {
            "camera": {"stream_name": "legacy"},
            "mqtt": {"username": "user", "password": "secret"},
            "video": {"go2rtc_username": "go2rtc-user", "go2rtc_password": "go2rtc-pass"},
            "species": {"tuning_target_species_ids": [1, 2, 3]},
            "ebird": {
                "species_mapping": {
                    "Gray-headed Woodpecker": "Grey-headed Woodpecker",
                },
            },
            "processor": {
                "species_confidence_overrides": {
                    "Bird": 0.2,
                },
                "camera_overrides": {
                    "BirdBox": {
                        "min_box_size_px": 10,
                        "definitely_unknown_camera_override_key": 1,
                    }
                },
                "adaptive_profiles": {
                    "night": {
                        "overrides": {
                            "max_box_area_norm": 0.9,
                            "definitely_unknown_profile_override_key": 1,
                        }
                    }
                },
            },
            "secrets": {"zip": "12345"},
        }
        user_config = tmp_path / "user_config.yaml"
        user_config.write_text(yaml.safe_dump(user_cfg), encoding="utf-8")
        monkeypatch.setattr(app_config, "user_config_file", str(user_config))
        with client.session_transaction() as sess:
            sess["access_role"] = "admin"
            sess["settings_unlocked"] = True

        response = client.get("/api/ui/system/config-audit")

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data.get("processor_runtime_hints"), list)
        assert isinstance(data.get("config_presets"), list)
        assert isinstance(data.get("preflight"), dict)
        assert isinstance(data.get("runtime_parity"), dict)
        assert "camera" not in data["deprecated_keys_present"]
        assert "camera" not in data["unknown_keys"]
        assert "mqtt.username" not in data["unknown_keys"]
        assert "mqtt.password" not in data["unknown_keys"]
        assert "video.go2rtc_username" not in data["unknown_keys"]
        assert "video.go2rtc_password" not in data["unknown_keys"]
        assert "species.tuning_target_species_ids" not in data["unknown_keys"]
        assert "ebird.species_mapping.Gray-headed Woodpecker" not in data["unknown_keys"]
        assert "processor.species_confidence_overrides.Bird" not in data["unknown_keys"]
        assert "processor.camera_overrides.BirdBox.min_box_size_px" not in data["unknown_keys"]
        assert "processor.adaptive_profiles.night.overrides.max_box_area_norm" not in data["unknown_keys"]
        assert "processor.camera_overrides.BirdBox.definitely_unknown_camera_override_key" in data["unknown_keys"]
        assert (
            "processor.adaptive_profiles.night.overrides.definitely_unknown_profile_override_key"
            in data["unknown_keys"]
        )
        assert "secrets.zip" not in data["unknown_keys"]

    def test_config_audit_preflight_and_runtime_parity(self, client, tmp_path, monkeypatch):
        import json
        import yaml
        from app_config.app_config import app_config

        user_cfg = {
            "triggers": {"frigate": {"enabled": True}},
            "mqtt": {"broker": ""},
            "video": {"encoding": "cpu"},
            "processor": {
                "inference_backend": "openvino",
                "inference_device": "intel:gpu",
            },
        }
        user_config = tmp_path / "user_config.yaml"
        user_config.write_text(yaml.safe_dump(user_cfg), encoding="utf-8")
        monkeypatch.setattr(app_config, "user_config_file", str(user_config))
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        diagnostics = tmp_path / "diagnostics"
        diagnostics.mkdir(parents=True, exist_ok=True)
        (diagnostics / "processor_runtime_stats.json").write_text(
            json.dumps(
                {
                    "counters": {},
                    "gauges": {
                        "trigger_cfg_frigate_enabled": 1,
                        "trigger_configured_paths_count": 2,
                        "trigger_effective_paths_count": 1,
                        "trigger_degraded_effective_lt_configured": 1,
                        "trigger_frigate_degraded_no_mqtt": 1,
                        "trigger_mqtt_live": 0,
                        "last_session_runtime_profile": "low_light",
                    },
                    "latency_ms": {},
                }
            ),
            encoding="utf-8",
        )
        with client.session_transaction() as sess:
            sess["access_role"] = "admin"
            sess["settings_unlocked"] = True

        response = client.get("/api/ui/system/config-audit")
        assert response.status_code == 200
        data = response.get_json() or {}
        preflight = data.get("preflight") or {}
        runtime_parity = data.get("runtime_parity") or {}
        runtime = runtime_parity.get("runtime") or {}
        parity_alerts = runtime_parity.get("parity_alerts") or {}
        assert preflight.get("status") in {"fail", "warn"}
        assert runtime.get("trigger_degraded_effective_lt_configured") is True
        assert runtime.get("trigger_frigate_degraded_no_mqtt") is True
        assert runtime.get("last_session_runtime_profile") == "low_light"
        assert parity_alerts.get("effective_trigger_paths_dropped") is True
        assert parity_alerts.get("frigate_degraded_no_mqtt") is True

    def test_update_settings_does_not_persist_transient_zip_field(self, client, tmp_path, monkeypatch):
        import yaml
        from app_config.app_config import app_config

        user_config = tmp_path / "user_config.yaml"
        user_config.write_text(
            yaml.safe_dump({"secrets": {"zip": "99999"}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(app_config, "user_config_file", str(user_config))
        with client.session_transaction() as sess:
            sess["access_role"] = "admin"
            sess["settings_unlocked"] = True

        response = client.patch(
            "/api/ui/settings",
            json={
                "secrets": {
                    "zip": "12345",
                    "latitude": "55.75",
                    "longitude": "37.61",
                },
            },
        )

        assert response.status_code == 200
        assert "zip" not in ((response.get_json() or {}).get("secrets") or {})
        assert "zip" not in (app_config.config.get("secrets") or {})
        saved = yaml.safe_load(user_config.read_text(encoding="utf-8")) or {}
        assert "zip" not in (saved.get("secrets") or {})


class TestSpeciesSummaryReadOnly:
    """GET /api/ui/species/:id/summary не обязан мутировать БД (containment)."""

    def test_summary_includes_metadata_trust(self, app, client):
        from models import Species, db

        unique = f"API Summary Trust Lark {id(app)}"
        with app.app_context():
            sp = Species(name=unique, metadata_status="ok")
            db.session.add(sp)
            db.session.commit()
            sid = sp.id
        r = client.get(f"/api/ui/species/{sid}/summary")
        assert r.status_code == 200
        data = r.get_json()
        assert data["species"]["metadata_trust"] == "unbound"
        assert data["species"]["metadata_status"] == "ok"

    def test_summary_hourly_activity_uses_observer_local_hour(self, app, client):
        from app_config.app_config import app_config
        from models import Species, SpeciesVisit, db
        from observer_time import observer_local_hour

        unique = f"API Summary Time Owl {id(app)}"
        # Rolling last_30d window uses real "now"; fixed March dates fall out of range in April+.
        now_utc = datetime.now(timezone.utc)
        visit_start = (now_utc - timedelta(hours=2)).replace(tzinfo=None, microsecond=0)
        visit_end = visit_start + timedelta(minutes=10)
        with app.app_context():
            app_config.set("secrets.latitude", "55.7558")
            app_config.set("secrets.longitude", "37.6176")
            sp = Species(name=unique, metadata_status="ok")
            db.session.add(sp)
            db.session.flush()
            db.session.add(
                SpeciesVisit(
                    species_id=sp.id,
                    start_time=visit_start,
                    end_time=visit_end,
                    max_simultaneous=4,
                ),
            )
            db.session.commit()
            sid = sp.id
            expected_hour = observer_local_hour(visit_start.replace(tzinfo=timezone.utc))
        from services.http_response_cache import bust_response_caches

        bust_response_caches()
        r = client.get(f"/api/ui/species/{sid}/summary")
        assert r.status_code == 200
        data = r.get_json()
        assert data["stats"]["hourlyActivity"][expected_hour] == 4

    def test_refresh_metadata_requires_settings_password(self, app, client, monkeypatch):
        from app_config.app_config import app_config
        from models import Species, db

        general = dict(app_config.config.get("general") or {})
        general["settings_password"] = "test-secret-refresh-metadata"
        general["contributor_password"] = ""
        monkeypatch.setitem(app_config.config, "general", general)

        unique = f"API Refresh Meta Finch {id(app)}"
        with app.app_context():
            sp = Species(name=unique, metadata_status="ok")
            db.session.add(sp)
            db.session.commit()
            sid = sp.id
        r = client.post(f"/api/ui/species/{sid}/refresh-metadata", json={})
        assert r.status_code == 403


class TestVideoStreamAccess:
    """Поток видео для плеера: по умолчанию без пароля (Viewer)."""

    def test_stream_allows_guest_when_not_locked(self, app, client, tmp_path, monkeypatch):
        from models import Video, db

        fake = tmp_path / "clip.mp4"
        fake.write_bytes(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2")
        monkeypatch.setattr("util.full_path_for_video", lambda _p: str(fake))

        vp = "data/recordings/2026/03/31/120000/video.mp4"
        with app.app_context():
            v = Video(
                processor_version="t",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                video_path=vp,
            )
            db.session.add(v)
            db.session.commit()
            vid = v.id

        from app_config.app_config import app_config

        general = dict(app_config.config.get("general") or {})
        general["require_auth_for_video_stream"] = False
        monkeypatch.setitem(app_config.config, "general", general)

        r = client.get(f"/api/ui/videos/{vid}/stream")
        assert r.status_code == 200
        assert "video" in (r.content_type or "").lower()

    def test_stream_requires_password_when_locked(self, app, client, tmp_path, monkeypatch):
        from models import Video, db

        fake = tmp_path / "clip2.mp4"
        fake.write_bytes(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2")
        monkeypatch.setattr("util.full_path_for_video", lambda _p: str(fake))

        vp = "data/recordings/2026/03/31/130000/video.mp4"
        with app.app_context():
            v = Video(
                processor_version="t",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                video_path=vp,
            )
            db.session.add(v)
            db.session.commit()
            vid = v.id

        from app_config.app_config import app_config

        general = dict(app_config.config.get("general") or {})
        general["require_auth_for_video_stream"] = True
        general["settings_password"] = "secret-stream-test"
        general["contributor_password"] = ""
        monkeypatch.setitem(app_config.config, "general", general)

        r = client.get(f"/api/ui/videos/{vid}/stream")
        assert r.status_code == 403
