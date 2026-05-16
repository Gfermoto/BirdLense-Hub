import json
from datetime import datetime, timedelta, timezone


def test_build_detection_quality_baseline_summarizes_traces_and_slices(app):
    from models import ActivityLog, Species, Video, VideoSpecies, db
    from services.detection_quality_baseline_service import (
        build_detection_quality_baseline,
    )

    with app.app_context():
        great_tit = Species(name="Great Tit")
        bird = Species(name="Bird")
        db.session.add_all([great_tit, bird])
        db.session.flush()

        now_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        day_start = (now_utc - timedelta(days=1)).replace(hour=10)
        night_start = day_start.replace(hour=22)
        day_video = Video(
            processor_version="t",
            start_time=day_start,
            end_time=day_start + timedelta(seconds=20),
            video_path="data/recordings/2026/04/10/day/video.mp4",
        )
        night_video = Video(
            processor_version="t",
            start_time=night_start,
            end_time=night_start + timedelta(seconds=20),
            video_path="data/recordings/2026/04/10/night/video.mp4",
        )
        db.session.add_all([day_video, night_video])
        db.session.flush()

        db.session.add_all(
            [
                VideoSpecies(
                    video_id=day_video.id,
                    species_id=great_tit.id,
                    start_time=1.0,
                    end_time=6.0,
                    confidence=0.91,
                    source="video",
                    detection_provider="yolo",
                    track_id=11,
                    frames=json.dumps([{"t": 3.5, "bbox": [0.1, 0.1, 0.4, 0.4]}]),
                ),
                VideoSpecies(
                    video_id=night_video.id,
                    species_id=bird.id,
                    start_time=2.0,
                    end_time=8.0,
                    confidence=0.62,
                    source="video",
                    detection_provider="frigate",
                    track_id=-1,
                    manually_corrected=True,
                    frames=json.dumps([{"t": 5.0, "bbox": [0.2, 0.2, 0.28, 0.3]}]),
                ),
            ]
        )

        db.session.add(
            ActivityLog(
                type="decision_trace",
                created_at=day_start,
                data=json.dumps(
                    {
                        "video_id": day_video.id,
                        "start_time": day_start.isoformat(),
                        "persisted_tracks": [
                            {
                                "track_id": 11,
                                "species_name": "Great Tit",
                                "accepted": True,
                                "decision_kind": "accepted_species",
                                "primary_provider": "yolo",
                                "yolo_track_present": True,
                            }
                        ],
                        "recording_context": {
                            "triggered_by": "live",
                            "runtime_signals": {
                                "frames_seen": 40,
                                "yolo_frames_ran": 35,
                                "yolo_frames_with_tracks": 8,
                                "low_light_blocked_frames": 0,
                                "session_extended_by_frigate": False,
                            },
                        },
                    }
                ),
            )
        )
        db.session.add(
            ActivityLog(
                type="decision_trace",
                created_at=night_start,
                data=json.dumps(
                    {
                        "video_id": night_video.id,
                        "start_time": night_start.isoformat(),
                        "persisted_tracks": [
                            {
                                "track_id": -1,
                                "species_name": "Bird",
                                "accepted": True,
                                "decision_kind": "frigate_standalone",
                                "primary_provider": "frigate",
                                "frigate_standalone": True,
                                "yolo_track_present": False,
                            }
                        ],
                        "recording_context": {
                            "triggered_by": "live",
                            "runtime_signals": {
                                "frames_seen": 25,
                                "yolo_frames_ran": 4,
                                "yolo_frames_with_tracks": 0,
                                "low_light_blocked_frames": 9,
                                "session_extended_by_frigate": True,
                            },
                        },
                    }
                ),
            )
        )
        db.session.add(
            ActivityLog(
                type="species_correction",
                created_at=night_start,
                data=json.dumps(
                    {
                        "action": "correct_species",
                        "from_species_name": "Bird",
                        "to_species_name": "Great Tit",
                    }
                ),
            )
        )
        db.session.commit()

        report = build_detection_quality_baseline(
            days=30,
            runtime_snapshot={"latency_ms": {"frame_processor_detect_p50": 24.0, "frame_processor_detect_p95": 55.0}},
        )

    assert report["window_days"] == 30
    assert report["trace_summary"]["clip_count"] == 2
    assert report["trace_summary"]["persisted_track_count"] == 2
    assert report["trace_summary"]["decision_kind_counts"]["accepted_species"] == 1
    assert report["trace_summary"]["decision_kind_counts"]["frigate_standalone"] == 1
    assert report["trace_summary"]["primary_provider_counts"]["yolo"] == 1
    assert report["trace_summary"]["primary_provider_counts"]["frigate"] == 1
    assert report["trace_summary"]["low_light_clip_rate"] == 0.5
    assert report["trace_summary"]["frigate_rescue_clip_rate"] == 0.5
    assert report["trace_summary"]["yolo_silent_clip_rate"] == 0.5

    assert report["correction_proxies"]["species_change_actions"] == 1
    assert report["correction_proxies"]["manual_annotation_rate"] == 0.5

    assert report["detection_slices"]["time_of_day"]["day"] == 1
    assert report["detection_slices"]["time_of_day"]["night"] == 1
    assert report["detection_slices"]["object_scale"]["medium"] == 1
    assert report["detection_slices"]["object_scale"]["small"] == 1

    assert report["runtime_observability"]["latency_ms"]["frame_processor_detect_p95"] == 55.0
