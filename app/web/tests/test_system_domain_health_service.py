"""Domain health snapshot strict-quality and ingest-gate metrics."""

import json
from datetime import datetime, timedelta, timezone

from models import ActivityLog, Species, Video, VideoSpecies, db


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
    reliability = payload.get("reliability_alerts") or {}
    assert "thresholds" in reliability
    assert "metrics" in reliability
    assert "alerts" in reliability


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


def test_domain_health_includes_track_stability_metrics(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        species = Species(name="DomainHealth Track Stability Finch")
        db.session.add(species)
        db.session.flush()
        video = Video(
            processor_version="pytest",
            start_time=now,
            end_time=now + timedelta(seconds=12),
            video_path="data/recordings/2026/05/03/151000/video.mp4",
            idempotency_key="pytest-domain-health-track-stability-key",
        )
        db.session.add(video)
        db.session.flush()
        db.session.add_all(
            [
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=None,
                    start_time=0.0,
                    end_time=3.0,
                    confidence=0.91,
                    source="video",
                    detection_provider="yolo",
                    track_id=101,
                    frames=json.dumps(
                        [
                            {"t": 0.0, "bbox": [10, 10, 20, 20]},
                            {"t": 0.2, "bbox": [10.5, 10.1, 20.5, 20.1]},
                            {"t": 0.4, "bbox": [11.0, 10.2, 21.0, 20.2]},
                        ]
                    ),
                ),
                VideoSpecies(
                    video_id=video.id,
                    species_id=species.id,
                    species_visit_id=None,
                    start_time=4.0,
                    end_time=6.0,
                    confidence=0.74,
                    source="video",
                    detection_provider="yolo",
                    track_id=102,
                    frames=json.dumps(
                        [
                            {"t": 0.0, "bbox": [100, 100, 120, 120]},
                            {"t": 1.9, "bbox": [170, 170, 190, 190]},
                        ]
                    ),
                ),
            ]
        )
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    metrics = payload.get("metrics") or {}
    samples = payload.get("samples") or {}
    assert int(metrics.get("track_rows_with_id_24h") or 0) >= 2
    assert int(metrics.get("track_rows_fragmented_24h") or 0) >= 1
    assert metrics.get("track_stability_score_avg_24h") is not None
    assert isinstance(samples.get("track_unstable_examples_24h"), list)


def test_domain_health_includes_lifecycle_and_regression_metrics(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        prev_trace = {
            "video_id": 9001,
            "persisted_tracks": [
                {"track_id": 1, "species_name": "Bird", "confidence": 0.9}
            ],
            "rejected_tracks": [],
        }
        current_trace = {
            "video_id": 9002,
            "persisted_tracks": [],
            "rejected_tracks": [
                {
                    "track_id": 2,
                    "species_name": "Bird",
                    "reject_reason_code": "FUSION_NO_ACCEPTED",
                }
            ],
        }
        db.session.add_all(
            [
                ActivityLog(
                    type="decision_trace",
                    data=json.dumps(prev_trace),
                    created_at=now - timedelta(hours=30),
                ),
                ActivityLog(
                    type="decision_trace",
                    data=json.dumps(current_trace),
                    created_at=now - timedelta(minutes=20),
                ),
            ]
        )
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    metrics = payload.get("metrics") or {}
    samples = payload.get("samples") or {}

    assert int(metrics.get("lifecycle_windows_24h") or 0) >= 1
    assert metrics.get("lifecycle_enter_rate_24h") is not None
    assert metrics.get("lifecycle_rejected_only_rate_24h") is not None
    assert "track_stability_score_delta_prev_24h" in metrics
    assert "track_quality_regression_24h" in metrics

    lifecycle_counts = samples.get("lifecycle_outcome_counts_24h") or {}
    reject_reasons = samples.get("lifecycle_top_reject_reasons_24h") or {}
    regression = samples.get("track_quality_regression_24h") or {}
    assert "entered" in lifecycle_counts
    assert "rejected_only" in lifecycle_counts
    assert isinstance(reject_reasons, dict)
    assert "current_sample" in regression


def test_domain_health_includes_ingest_gate_reason_metrics(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        rows = [
            ActivityLog(
                type="ingest_gate",
                data=json.dumps(
                    {
                        "reason": "video_file_missing",
                        "reason_code": "REC_FILE_UNPLAYABLE",
                    }
                ),
                created_at=now - timedelta(minutes=5),
            ),
            ActivityLog(
                type="ingest_gate",
                data=json.dumps(
                    {
                        "reason": "no_persisted_detections",
                        "reason_code": "FUSION_NO_ACCEPTED",
                    }
                ),
                created_at=now - timedelta(minutes=4),
            ),
            ActivityLog(
                type="ingest_gate",
                data=json.dumps(
                    {
                        "reason": "no_persisted_detections",
                    }
                ),
                created_at=now - timedelta(minutes=3),
            ),
        ]
        db.session.add_all(rows)
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    metrics = payload.get("metrics") or {}
    samples = payload.get("samples") or {}
    reason_counts = samples.get("ingest_gate_reason_code_counts_24h") or {}

    assert int(metrics.get("ingest_gate_rows_24h") or 0) >= 3
    assert int(metrics.get("ingest_gate_known_reason_rows_24h") or 0) >= 2
    assert int(metrics.get("ingest_gate_unknown_reason_rows_24h") or 0) >= 1
    assert int(reason_counts.get("REC_FILE_UNPLAYABLE") or 0) >= 1
    assert int(reason_counts.get("FUSION_NO_ACCEPTED") or 0) >= 1


def test_domain_health_reliability_alerts_for_artifact_failures_and_unknown_reasons(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        db.session.add_all(
            [
                ActivityLog(
                    type="ingest_gate",
                    data=json.dumps(
                        {
                            "reason": "video_file_missing",
                            "reason_code": "REC_FILE_MISSING",
                        }
                    ),
                    created_at=now - timedelta(minutes=6),
                ),
                ActivityLog(
                    type="ingest_gate",
                    data=json.dumps(
                        {
                            "reason": "video_file_missing",
                            "reason_code": "REC_FILE_UNPLAYABLE",
                        }
                    ),
                    created_at=now - timedelta(minutes=5),
                ),
                ActivityLog(
                    type="ingest_gate",
                    data=json.dumps({"reason": "no_persisted_detections"}),
                    created_at=now - timedelta(minutes=4),
                ),
            ]
        )
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    reliability = payload.get("reliability_alerts") or {}
    metrics = reliability.get("metrics") or {}
    alerts = reliability.get("alerts") or {}

    assert int(metrics.get("recording_artifact_failures_24h") or 0) >= 2
    assert int(metrics.get("recording_file_missing_24h") or 0) >= 1
    assert int(metrics.get("recording_file_unplayable_24h") or 0) >= 1
    assert int(metrics.get("unknown_ingest_gate_rows_24h") or 0) >= 1
    assert alerts.get("recording_artifact_failures") is True
    assert alerts.get("unknown_ingest_gate_reasons") is True


def test_domain_health_data_stagnation_alert_when_sessions_without_visits(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        db.session.add_all(
            [
                ActivityLog(
                    type="recording_session_summary",
                    data=json.dumps(
                        {
                            "video_file_ok": True,
                            "post_fusion_persisted": 0,
                            "frames_seen": 120,
                            "yolo_frames_ran": 120,
                        }
                    ),
                    created_at=now - timedelta(minutes=2),
                ),
                ActivityLog(
                    type="recording_session_summary",
                    data=json.dumps(
                        {
                            "video_file_ok": True,
                            "post_fusion_persisted": 0,
                            "frames_seen": 90,
                            "yolo_frames_ran": 90,
                        }
                    ),
                    created_at=now - timedelta(minutes=1),
                ),
            ]
        )
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    reliability = payload.get("reliability_alerts") or {}
    metrics = reliability.get("metrics") or {}
    alerts = reliability.get("alerts") or {}
    assert int(metrics.get("recording_sessions_5m") or 0) >= 2
    assert int(metrics.get("post_fusion_persisted_sum_5m") or 0) == 0
    assert int(metrics.get("species_visits_5m") or 0) == 0
    assert alerts.get("data_stagnation") is True


def test_domain_health_includes_parity_diagnostics_daily_split(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        matched_payload = {
            "start_time": now.replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
            "video_path": "data/recordings/2026/05/16/100000/cam1.mp4",
            "recording_context": {
                "triggered_by": "frigate",
                "triggered_camera": "cam-front",
                "active_triggers": ["frigate"],
            },
            "outcome_summary": {"persisted_track_count": 2},
        }
        mismatched_payload = {
            "start_time": now.replace(hour=23, minute=0, second=0, microsecond=0).isoformat(),
            "video_path": "data/recordings/2026/05/16/230000/cam2.mp4",
            "recording_context": {
                "triggered_by": "frigate",
                "triggered_camera": "cam-back",
                "active_triggers": ["frigate"],
            },
            "outcome_summary": {"persisted_track_count": 0},
        }
        db.session.add_all(
            [
                ActivityLog(
                    type="decision_trace",
                    data=json.dumps(matched_payload),
                    created_at=now - timedelta(minutes=9),
                ),
                ActivityLog(
                    type="decision_trace",
                    data=json.dumps(mismatched_payload),
                    created_at=now - timedelta(minutes=8),
                ),
                ActivityLog(
                    type="ingest_gate",
                    data=json.dumps(
                        {
                            "reason": "no_persisted_detections",
                            "reason_code": "FUSION_NO_ACCEPTED",
                            "video_path": "data/recordings/2026/05/16/230000/cam2.mp4",
                        }
                    ),
                    created_at=now - timedelta(minutes=7),
                ),
            ]
        )
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    metrics = payload.get("metrics") or {}
    samples = payload.get("samples") or {}
    causes = samples.get("parity_top_mismatch_reasons_24h") or {}
    camera_split = samples.get("parity_camera_split_24h") or []

    assert int(metrics.get("parity_frigate_windows_24h") or 0) >= 2
    assert int(metrics.get("parity_hub_matched_windows_24h") or 0) >= 1
    assert int(metrics.get("parity_mismatched_windows_24h") or 0) >= 1
    assert float(metrics.get("parity_mismatch_rate_24h") or 0.0) > 0.0
    assert int(causes.get("FUSION_NO_ACCEPTED") or 0) >= 1
    assert any(str(row.get("camera") or "") == "cam-front" for row in camera_split)
    assert any(str(row.get("camera") or "") == "cam-back" for row in camera_split)


def test_domain_health_parity_uses_rejected_track_reason_when_ingest_gate_absent(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        mismatched_payload = {
            "start_time": now.replace(hour=9, minute=0, second=0, microsecond=0).isoformat(),
            "video_path": "data/recordings/2026/05/16/090000/camx.mp4",
            "recording_context": {
                "triggered_by": "frigate",
                "triggered_camera": "cam-x",
                "active_triggers": ["frigate"],
                "runtime_signals": {"yolo_ran": True, "yolo_track_found": False},
            },
            "outcome_summary": {"persisted_track_count": 0, "rejected_track_count": 1},
            "rejected_tracks": [{"decision_reason": "rejected_short_track"}],
        }
        db.session.add(
            ActivityLog(
                type="decision_trace",
                data=json.dumps(mismatched_payload),
                created_at=now - timedelta(minutes=3),
            )
        )
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    causes = (payload.get("samples") or {}).get("parity_top_mismatch_reasons_24h") or {}
    assert int(causes.get("REJECT_REJECTED_SHORT_TRACK") or 0) >= 1


def test_domain_health_parity_uses_yolo_no_track_reason_without_rejected_rows(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        mismatched_payload = {
            "start_time": now.replace(hour=8, minute=30, second=0, microsecond=0).isoformat(),
            "video_path": "data/recordings/2026/05/16/083000/camy.mp4",
            "recording_context": {
                "triggered_by": "frigate",
                "triggered_camera": "cam-y",
                "active_triggers": ["frigate"],
                "runtime_signals": {"yolo_ran": True, "yolo_track_found": False},
            },
            "outcome_summary": {"persisted_track_count": 0, "rejected_track_count": 0},
            "rejected_tracks": [],
        }
        db.session.add(
            ActivityLog(
                type="decision_trace",
                data=json.dumps(mismatched_payload),
                created_at=now - timedelta(minutes=2),
            )
        )
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    causes = (payload.get("samples") or {}).get("parity_top_mismatch_reasons_24h") or {}
    assert int(causes.get("YOLO_NO_TRACK") or 0) >= 1


def test_domain_health_reports_parity_hotspot_for_camera_with_high_mismatch_rate(app, client):
    with app.app_context():
        now = datetime.now(timezone.utc)
        rows = []
        for idx in range(12):
            rows.append(
                ActivityLog(
                    type="decision_trace",
                    data=json.dumps(
                        {
                            "start_time": (
                                now.replace(hour=11, minute=0, second=0, microsecond=0) - timedelta(minutes=idx)
                            ).isoformat(),
                            "video_path": f"data/recordings/2026/05/16/1100{idx:02d}/hot.mp4",
                            "recording_context": {
                                "triggered_by": "frigate",
                                "triggered_camera": "cam-hot",
                                "active_triggers": ["frigate"],
                                "runtime_signals": {"yolo_ran": True, "yolo_track_found": False},
                            },
                            "outcome_summary": {"persisted_track_count": 0, "rejected_track_count": 0},
                        }
                    ),
                    created_at=now - timedelta(minutes=idx),
                )
            )
        db.session.add_all(rows)
        db.session.commit()

    res = client.get("/api/ui/system/domain-health", headers=_auth_headers())
    assert res.status_code == 200, res.get_data(as_text=True)
    payload = res.get_json() or {}
    metrics = payload.get("metrics") or {}
    hotspots = (payload.get("samples") or {}).get("parity_hotspots_24h") or []

    assert int(metrics.get("parity_hotspot_count_24h") or 0) >= 1
    assert any(str(row.get("camera") or "") == "cam-hot" for row in hotspots)
